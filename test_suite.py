import unittest
from app import app, init_db, db, User, Expense, Income, Bill, Goal, Budget, limiter

class KashFlowV2TestSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        limiter.enabled = False
        init_db()

    def setUp(self):
        self.client = app.test_client()
        with app.app_context():
            test_users = User.query.filter(User.email.in_(['suite_user@example.com', 'suite_user2@example.com'])).all()
            for u in test_users:
                Expense.query.filter_by(user_id=u.id).delete()
                Income.query.filter_by(user_id=u.id).delete()
                Bill.query.filter_by(user_id=u.id).delete()
                Goal.query.filter_by(user_id=u.id).delete()
                Budget.query.filter_by(user_id=u.id).delete()
                db.session.delete(u)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            test_users = User.query.filter(User.email.in_(['suite_user@example.com', 'suite_user2@example.com'])).all()
            for u in test_users:
                Expense.query.filter_by(user_id=u.id).delete()
                Income.query.filter_by(user_id=u.id).delete()
                Bill.query.filter_by(user_id=u.id).delete()
                Goal.query.filter_by(user_id=u.id).delete()
                Budget.query.filter_by(user_id=u.id).delete()
                db.session.delete(u)
            db.session.commit()

    def test_01_registration_and_login(self):
        res = self.client.post('/register', data={
            'name': 'Suite Tester',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Suite Tester', res.data)

        # Logout so we can test duplicate registration as a guest
        res_logout = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)

        # Duplicate registration fails
        res2 = self.client.post('/register', data={
            'name': 'Suite Duplicate',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertIn(b'already exists', res2.data)

        # Login again
        res_login = self.client.post('/login', data={
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b'Suite Tester', res_login.data)

    def test_02_expense_crud(self):
        self.client.post('/register', data={
            'name': 'Expense Tester',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)

        res_add = self.client.post('/add', data={
            'description': 'Team Lunch',
            'amount': '42.50',
            'category': 'Food',
            'date': '2026-11-20',
            'payment_method': 'Card',
            'notes': 'Great pizza'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b'Team Lunch', res_add.data)

        with app.app_context():
            user = User.query.filter_by(email='suite_user@example.com').first()
            exp = Expense.query.filter_by(user_id=user.id, description='Team Lunch').first()
            self.assertIsNotNone(exp)
            self.assertEqual(exp.amount, 42.50)
            exp_id = exp.id

        res_edit = self.client.post(f'/edit/{exp_id}', data={
            'description': 'Team Banquet',
            'amount': '85.00',
            'category': 'Food',
            'date': '2026-11-20',
            'payment_method': 'Card',
            'notes': 'Updated'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'Team Banquet', res_edit.data)

        res_del = self.client.post(f'/delete/{exp_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        with app.app_context():
            self.assertIsNone(Expense.query.get(exp_id))

    def test_03_income_crud(self):
        self.client.post('/register', data={
            'name': 'Income Tester',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)

        res_add = self.client.post('/add-income', data={
            'description': 'Client Milestone',
            'amount': '1200.00',
            'category': 'Freelance',
            'date': '2026-11-20',
            'source': 'Bank Transfer',
            'notes': 'Website project'
        }, follow_redirects=True)
        self.assertEqual(res_add.status_code, 200)
        self.assertIn(b'Client Milestone', res_add.data)

        with app.app_context():
            user = User.query.filter_by(email='suite_user@example.com').first()
            inc = Income.query.filter_by(user_id=user.id, description='Client Milestone').first()
            self.assertIsNotNone(inc)
            inc_id = inc.id

        res_edit = self.client.post(f'/edit-income/{inc_id}', data={
            'description': 'Client Milestone Final',
            'amount': '1500.00',
            'category': 'Freelance',
            'date': '2026-11-20',
            'source': 'Bank Transfer',
            'notes': 'Updated note'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        self.assertIn(b'Client Milestone Final', res_edit.data)

        res_del = self.client.post(f'/delete-income/{inc_id}', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        with app.app_context():
            self.assertIsNone(Income.query.get(inc_id))

    def test_04_bills_goals_budgets(self):
        self.client.post('/register', data={
            'name': 'Finance Planner',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)

        # Add Bill
        res_bill = self.client.post('/add-bill', data={
            'name': 'Internet Fiber',
            'amount': '60.00',
            'category': 'Utilities',
            'due_date': '2026-12-01',
            'recurring': 'Monthly'
        }, follow_redirects=True)
        self.assertEqual(res_bill.status_code, 200)
        self.assertIn(b'Internet Fiber', res_bill.data)

        with app.app_context():
            bill = Bill.query.filter_by(name='Internet Fiber').first()
            self.assertIsNotNone(bill)
            self.assertFalse(bill.is_paid)
            bill_id = bill.id

        res_toggle = self.client.post(f'/toggle-bill/{bill_id}', follow_redirects=True)
        self.assertEqual(res_toggle.status_code, 200)
        with app.app_context():
            bill = Bill.query.get(bill_id)
            self.assertTrue(bill.is_paid)

        # Add Goal
        res_goal = self.client.post('/add-goal', data={
            'title': 'Emergency Fund',
            'target_amount': '5000',
            'current_amount': '1000',
            'category': 'Emergency Fund',
            'target_date': '2027-01-01'
        }, follow_redirects=True)
        self.assertEqual(res_goal.status_code, 200)
        self.assertIn(b'Emergency Fund', res_goal.data)

        with app.app_context():
            goal = Goal.query.filter_by(title='Emergency Fund').first()
            self.assertIsNotNone(goal)
            goal_id = goal.id

        # Update Goal
        res_goal_up = self.client.post(f'/update-goal/{goal_id}', data={
            'current_amount': '1500'
        }, follow_redirects=True)
        self.assertEqual(res_goal_up.status_code, 200)
        with app.app_context():
            goal = Goal.query.get(goal_id)
            self.assertEqual(goal.current_amount, 1500.0)

        # Add Budget
        res_bgt = self.client.post('/add-budget', data={
            'category': 'Food',
            'monthly_limit': '400'
        }, follow_redirects=True)
        self.assertEqual(res_bgt.status_code, 200)
        self.assertIn(b'Food', res_bgt.data)

    def test_05_csv_export(self):
        self.client.post('/register', data={
            'name': 'Exporter',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)

        self.client.post('/add', data={
            'description': 'Coffee Break',
            'amount': '5.50',
            'category': 'Food',
            'date': '2026-11-20',
            'payment_method': 'Cash'
        })

        res_csv = self.client.get('/export-csv')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')
        self.assertIn(b'Coffee Break', res_csv.data)
        self.assertIn(b'5.50', res_csv.data)

    def test_06_account_settings_and_deletion(self):
        self.client.post('/register', data={
            'name': 'Delete Me',
            'email': 'suite_user@example.com',
            'password': 'SecurePassword123!',
            'confirm_password': 'SecurePassword123!'
        }, follow_redirects=True)

        res_profile = self.client.post('/settings', data={
            'action': 'update_profile',
            'name': 'Delete Me Renamed',
            'email': 'suite_user@example.com'
        }, follow_redirects=True)
        self.assertEqual(res_profile.status_code, 200)
        self.assertIn(b'Delete Me Renamed', res_profile.data)

        # Wrong password deletion attempt
        res_wrong_pw = self.client.post('/settings', data={
            'action': 'delete_account',
            'password_confirm': 'WrongPassword!'
        }, follow_redirects=True)
        self.assertIn(b'Incorrect password', res_wrong_pw.data)

        # Correct password deletion
        res_del_acc = self.client.post('/settings', data={
            'action': 'delete_account',
            'password_confirm': 'SecurePassword123!'
        }, follow_redirects=True)
        self.assertEqual(res_del_acc.status_code, 200)
        self.assertIn(b'permanently deleted', res_del_acc.data)

        with app.app_context():
            user = User.query.filter_by(email='suite_user@example.com').first()
            self.assertIsNone(user)

if __name__ == '__main__':
    unittest.main()
