import unittest
import io
from app import app, init_db, db, User, Expense, Income, limiter

class EdgeCaseTestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        limiter.enabled = False
        init_db()

    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            old = User.query.filter_by(email='edge_tester@kashflow.app').first()
            if old:
                Expense.query.filter_by(user_id=old.id).delete()
                Income.query.filter_by(user_id=old.id).delete()
                db.session.delete(old)
                db.session.commit()

        self.client.post('/register', data={
            'name': 'Edge Tester',
            'email': 'edge_tester@kashflow.app',
            'password': 'SecurePass123!',
            'confirm_password': 'SecurePass123!'
        }, follow_redirects=True)

    def tearDown(self):
        with app.app_context():
            old = User.query.filter_by(email='edge_tester@kashflow.app').first()
            if old:
                Expense.query.filter_by(user_id=old.id).delete()
                Income.query.filter_by(user_id=old.id).delete()
                db.session.delete(old)
                db.session.commit()

    def test_negative_and_zero_amounts_rejected(self):
        # Negative amount
        res_neg = self.client.post('/add', data={
            'description': 'Negative Expense',
            'amount': '-15.50',
            'category': 'Food',
            'date': '2026-11-20'
        }, follow_redirects=True)
        self.assertIn(b'valid positive amount', res_neg.data)

        # Zero amount
        res_zero = self.client.post('/add', data={
            'description': 'Zero Expense',
            'amount': '0.00',
            'category': 'Food',
            'date': '2026-11-20'
        }, follow_redirects=True)
        self.assertIn(b'valid positive amount', res_zero.data)

    def test_nan_inf_huge_amounts_rejected(self):
        # NaN
        res_nan = self.client.post('/add', data={
            'description': 'NaN Expense',
            'amount': 'NaN',
            'category': 'Food',
            'date': '2026-11-20'
        }, follow_redirects=True)
        self.assertIn(b'valid positive amount', res_nan.data)

        # Inf
        res_inf = self.client.post('/add', data={
            'description': 'Inf Expense',
            'amount': 'inf',
            'category': 'Food',
            'date': '2026-11-20'
        }, follow_redirects=True)
        self.assertIn(b'valid positive amount', res_inf.data)

        # Huge Overflow (> 100M)
        res_huge = self.client.post('/add', data={
            'description': 'Huge Expense',
            'amount': '999999999999',
            'category': 'Food',
            'date': '2026-11-20'
        }, follow_redirects=True)
        self.assertIn(b'valid positive amount', res_huge.data)

    def test_leap_year_and_invalid_dates(self):
        # Valid leap year date (Feb 29, 2024)
        res_leap = self.client.post('/add', data={
            'description': 'Leap Year Dinner',
            'amount': '45.00',
            'category': 'Food',
            'date': '2024-02-29'
        }, follow_redirects=True)
        self.assertIn(b'Leap Year Dinner', res_leap.data)

        # Invalid non-leap year date (Feb 29, 2023)
        res_bad_leap = self.client.post('/add', data={
            'description': 'Bad Leap Day',
            'amount': '45.00',
            'category': 'Food',
            'date': '2023-02-29'
        }, follow_redirects=True)
        self.assertIn(b'valid date in YYYY-MM-DD format', res_bad_leap.data)

    def test_xss_special_characters_and_emojis(self):
        # Special characters & XSS payload
        res_xss = self.client.post('/add', data={
            'description': '<script>alert("hack")</script>',
            'amount': '12.50',
            'category': 'General',
            'date': '2026-11-20',
            'notes': 'Test & " \' < > 🚀 Special Chars 💰'
        }, follow_redirects=True)
        self.assertEqual(res_leap_status := res_xss.status_code, 200)
        # Verify script tag is safely escaped in response HTML
        self.assertNotIn(b'<script>alert("hack")</script>', res_xss.data)
        self.assertIn(b'&lt;script&gt;alert(&#34;hack&#34;)&lt;/script&gt;', res_xss.data)

    def test_csv_export_and_restore_roundtrip(self):
        # Add expense & income
        self.client.post('/add', data={
            'description': 'Cloud Backup Subscription',
            'amount': '19.99',
            'category': 'Utilities',
            'date': '2026-11-20'
        })
        self.client.post('/add-income', data={
            'description': 'Consulting Fee',
            'amount': '500.00',
            'category': 'Freelance',
            'date': '2026-11-20'
        })

        # Export CSV
        res_exp = self.client.get('/export-csv')
        self.assertEqual(res_exp.status_code, 200)
        csv_data = res_exp.data

        # Restore from this CSV
        data = {
            'csv_file': (io.BytesIO(csv_data), 'backup.csv')
        }
        res_imp = self.client.post('/import-csv', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_imp.status_code, 200)
        # Duplicate detection will skip re-adding identical entries
        self.assertIn(b'Successfully restored 0 financial transactions', res_imp.data)

        # Now test with brand-new rows in CSV
        new_csv = "Type,Date,Description,Category,Amount,Payment Method / Source,Notes\nExpense,2026-11-19,New Restored Book,Shopping,29.99,Card,Imported note\nIncome,2026-11-19,Bonus Award,Other,350.00,Bank Transfer,Quarterly bonus\n"
        data_new = {
            'csv_file': (io.BytesIO(new_csv.encode('utf-8')), 'new_backup.csv')
        }
        res_imp_new = self.client.post('/import-csv', data=data_new, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res_imp_new.status_code, 200)
        self.assertIn(b'Successfully restored 2 financial transactions', res_imp_new.data)

if __name__ == '__main__':
    unittest.main()
