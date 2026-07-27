import os
import unittest
from app import app, db, User, Expense, Income, Bill, Goal, Budget

class FullAppAudit(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        with app.app_context():
            db.create_all()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def register(self, name="Test User", email="test@example.com", password="password123"):
        return self.client.post('/register', data={
            'name': name,
            'email': email,
            'password': password,
            'confirm_password': password
        }, follow_redirects=True)

    def login(self, email="test@example.com", password="password123"):
        return self.client.post('/login', data={
            'email': email,
            'password': password
        }, follow_redirects=True)

    def test_01_auth_flow(self):
        res = self.register()
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Welcome to KashFlow", res.data)

        res = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        res = self.login()
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Financial Health Score", res.data)

    def test_02_expenses_and_incomes(self):
        self.register()
        res = self.client.post('/add-income', data={
            'description': 'Salary Check',
            'amount': '3500.00',
            'category': 'Salary',
            'date': '2026-07-27',
            'source': 'Bank Transfer'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Salary Check", res.data)

        res = self.client.post('/add', data={
            'description': 'Supermarket Groceries',
            'amount': '150.00',
            'category': 'Food',
            'date': '2026-07-27',
            'payment_method': 'Card'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Supermarket Groceries", res.data)

    def test_03_bills_goals_budgets(self):
        self.register()
        with app.app_context():
            u = User.query.first()
            u.is_premium = True
            db.session.commit()

        res = self.client.post('/add-bill', data={
            'name': 'Electric Bill',
            'amount': '85.00',
            'category': 'Utilities',
            'due_date': '2026-08-01',
            'recurring': 'Monthly'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Electric Bill", res.data)

        res = self.client.post('/add-goal', data={
            'title': 'Emergency Fund',
            'target_amount': '2000.00',
            'current_amount': '500.00',
            'category': 'Emergency Fund'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Emergency Fund", res.data)

        res = self.client.post('/add-budget', data={
            'category': 'Food',
            'monthly_limit': '500.00'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Food", res.data)

    def test_04_scenarios_and_export(self):
        self.register()
        res = self.client.get('/simulate-healthy', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Healthy Scenario loaded", res.data)

        with app.app_context():
            u = User.query.first()
            u.is_premium = True
            db.session.commit()
        res = self.client.get('/export-csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, 'text/csv')

if __name__ == '__main__':
    unittest.main()
