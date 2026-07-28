import os

# Complete, beautifully commented app.py
commented_app = '''import os
import json
import sqlite3
import calendar
import csv
import io
import stripe
from datetime import datetime, timedelta

from collections import defaultdict
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import secrets

# ───────────────────────────────────────────────────────────────
# 1. ENVIRONMENT & FLASK CONFIGURATION
# ───────────────────────────────────────────────────────────────
# Load environment variables from local .env file if available
load_dotenv()

app = Flask(__name__)

# Flask Secret Key for encrypting session cookies. Fallback keeps user logged in across server restarts.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "kashflow-persistent-secret-key-prod-2026")

# Database Configuration (SQLite stored locally in instance/expenses.db)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Security Hardening for Session Cookies:
# - HTTPONLY: Prevents JavaScript/XSS scripts from reading session cookies.
# - SAMESITE=Lax: Protects against Cross-Site Request Forgery (CSRF) attacks.
# - PERMANENT_SESSION_LIFETIME: Keeps user logged in for 365 days (1 full year) on mobile/desktop.
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)

# Enforce HTTPS Secure cookies in production cloud environments (Railway / Production WSGI)
if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('RAILWAY_ENVIRONMENT'):
    app.config['SESSION_COOKIE_SECURE'] = True

# Initialize SQLAlchemy Database ORM
db = SQLAlchemy(app)

# ───────────────────────────────────────────────────────────────
# 2. STRIPE PAYMENT GATEWAY CONFIGURATION
# ───────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY      = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PRICE_ID        = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_ANNUAL_PRICE_ID = os.environ.get("STRIPE_ANNUAL_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_URL                = os.environ.get("APP_URL", "http://127.0.0.1:5000")

stripe.api_key = STRIPE_SECRET_KEY

# ───────────────────────────────────────────────────────────────
# 3. GLOBAL CATEGORIES & FINANCIAL CLASSIFICATIONS
# ───────────────────────────────────────────────────────────────
EXPENSE_CATEGORIES = ['Food', 'Transportation', 'Housing', 'Shopping', 'Utilities', 'Health', 'General']
INCOME_CATEGORIES  = ['Salary', 'Freelance', 'Investments', 'Business', 'Gifts & Grants', 'Rental', 'Other']
PAYMENT_METHODS    = ['Card', 'Cash', 'Bank Transfer', 'Check', 'Crypto']

# Category classifications for the 50/30/20 Budgeting Rule:
# - Needs (50% target): Housing, Utilities, Food, Health, Transportation
# - Wants (30% target): Shopping, General
NEEDS_CATEGORIES   = {'Housing', 'Utilities', 'Food', 'Health', 'Transportation'}
WANTS_CATEGORIES   = {'Shopping', 'General'}

# ───────────────────────────────────────────────────────────────
# 4. DATABASE SCHEMAS & ORM MODELS
# ───────────────────────────────────────────────────────────────

class User(db.Model):
    """Stores registered user accounts, passwords, and subscription status."""
    id                     = db.Column(db.Integer, primary_key=True)
    name                   = db.Column(db.String(100), nullable=False)
    email                  = db.Column(db.String(150), nullable=False, unique=True)
    password_hash          = db.Column(db.String(255), nullable=False)
    is_premium             = db.Column(db.Boolean, default=False)
    stripe_customer_id     = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    created_at             = db.Column(db.String(20), default=lambda: datetime.now().strftime('%Y-%m-%d'))


class Expense(db.Model):
    """Stores individual spending items logged by users."""
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    description    = db.Column(db.String(100), nullable=False)
    amount         = db.Column(db.Float, nullable=False)
    category       = db.Column(db.String(50), nullable=False, default='General')
    date           = db.Column(db.String(10), nullable=False, default=lambda: datetime.now().strftime('%Y-%m-%d'))
    payment_method = db.Column(db.String(50), nullable=False, default='Card')
    notes          = db.Column(db.Text, nullable=True, default='')


class Income(db.Model):
    """Stores income sources logged by users (Salary, Freelance, Business, etc.)."""
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    description = db.Column(db.String(100), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    category    = db.Column(db.String(50), nullable=False, default='Salary')
    date        = db.Column(db.String(10), nullable=False, default=lambda: datetime.now().strftime('%Y-%m-%d'))
    source      = db.Column(db.String(50), nullable=False, default='Bank Transfer')
    notes       = db.Column(db.Text, nullable=True, default='')


class Bill(db.Model):
    """Stores recurring bills and payment due dates."""
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name      = db.Column(db.String(100), nullable=False)
    amount    = db.Column(db.Float, nullable=False)
    category  = db.Column(db.String(50), nullable=False, default='Utilities')
    due_date  = db.Column(db.String(10), nullable=False)
    is_paid   = db.Column(db.Boolean, default=False)
    recurring = db.Column(db.String(50), default='Monthly')


class Goal(db.Model):
    """Stores user savings goals (Emergency Fund, Vacation, Car, etc.)."""
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title          = db.Column(db.String(100), nullable=False)
    target_amount  = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date    = db.Column(db.String(10), nullable=True)
    category       = db.Column(db.String(50), default='Emergency Fund')


class Budget(db.Model):
    """Stores monthly spending caps for individual categories."""
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    category      = db.Column(db.String(50), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)
    month         = db.Column(db.String(7), nullable=False, default=lambda: datetime.now().strftime('%Y-%m'))

# ───────────────────────────────────────────────────────────────
# 5. DATABASE MIGRATION & AUTO-SEEDING HELPER
# ───────────────────────────────────────────────────────────────

def init_db():
    """
    Initializes database tables, performs column migrations safely on SQLite,
    and auto-seeds primary account credentials to preserve logins across cloud deployments.
    """
    with app.app_context():
        try:
            db.create_all()
            db_file = os.path.join(app.root_path, 'instance', 'expenses.db')
            if not os.path.exists(db_file):
                db_file = os.path.join(app.root_path, 'expenses.db')

            if os.path.exists(db_file):
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()

                # Ensure Expense table has all required columns
                cursor.execute("PRAGMA table_info(expense)")
                exp_cols = [r[1] for r in cursor.fetchall()]
                for col, defn in [('category', "VARCHAR(50) DEFAULT 'General'"), ('date', "VARCHAR(10) DEFAULT ''"),
                                   ('payment_method', "VARCHAR(50) DEFAULT 'Card'"), ('notes', "TEXT DEFAULT ''"),
                                   ('user_id', "INTEGER")]:
                    if col not in exp_cols:
                        cursor.execute(f"ALTER TABLE expense ADD COLUMN {col} {defn}")

                # Ensure Income table has all required columns
                cursor.execute("PRAGMA table_info(income)")
                inc_cols = [r[1] for r in cursor.fetchall()]
                for col, defn in [('source', "VARCHAR(50) DEFAULT 'Bank Transfer'"), ('notes', "TEXT DEFAULT ''"),
                                   ('user_id', "INTEGER")]:
                    if col not in inc_cols:
                        cursor.execute(f"ALTER TABLE income ADD COLUMN {col} {defn}")

                # Ensure user_id column exists on auxiliary tables
                for table in ['bill', 'goal', 'budget']:
                    cursor.execute(f"PRAGMA table_info({table})")
                    cols = [r[1] for r in cursor.fetchall()]
                    if 'user_id' not in cols:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")

                # Ensure User table has Stripe subscription columns
                cursor.execute("PRAGMA table_info(user)")
                user_cols = [r[1] for r in cursor.fetchall()]
                for col, defn in [('stripe_customer_id', "VARCHAR(255)"),
                                   ('stripe_subscription_id', "VARCHAR(255)")]:
                    if col not in user_cols:
                        cursor.execute(f"ALTER TABLE user ADD COLUMN {col} {defn}")

                conn.commit()
                conn.close()
        except Exception as e:
            print("DB migration check:", e)

        try:
            # Auto-seed & sync primary user account so logins persist across Railway cloud deploys
            user = User.query.filter_by(email="jawadkaeik@gmail.com").first()
            if not user:
                user = User(
                    name="Jawad",
                    email="jawadkaeik@gmail.com",
                    password_hash=generate_password_hash("jawad1234"),
                    is_premium=True
                )
                db.session.add(user)
            else:
                user.password_hash = generate_password_hash("jawad1234")
                user.is_premium = True
            db.session.commit()
            print("[OK] Primary user 'jawadkaeik@gmail.com' synced.")
        except Exception as se:
            print("Auto-seed check:", se)

# ───────────────────────────────────────────────────────────────
# 6. AUTHENTICATION HELPERS & DECORATORS
# ───────────────────────────────────────────────────────────────

def get_current_user():
    """Fetches the active logged-in User object from the session ID safely."""
    uid = session.get('user_id')
    if uid:
        try:
            return db.session.get(User, uid)
        except Exception:
            return None
    return None


def current_uid():
    """Returns the current user ID integer from Flask session."""
    return session.get('user_id')


def login_required(f):
    """Decorator: Redirects unauthenticated requests to the login page."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.clear()
            flash("Please log in to access KashFlow.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def is_premium():
    """Checks whether the currently logged-in user has Premium status."""
    user = get_current_user()
    return user.is_premium if user else False


def premium_required(f):
    """Decorator: Enforces Premium subscription requirement for PRO features."""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.clear()
            flash("Please log in to access KashFlow.", "error")
            return redirect(url_for('login'))
        if not is_premium():
            flash("This feature requires a Premium PRO subscription. Upgrade to unlock full access!", "error")
            return redirect(url_for('pricing'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    """Injects user authentication status globally into all Jinja HTML templates."""
    user = get_current_user()
    return {'is_premium': user.is_premium if user else False, 'current_user': user}

# ───────────────────────────────────────────────────────────────
# 7. AUTHENTICATION ROUTES (LOGIN, REGISTER, LOGOUT)
# ───────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles user login with email & password authentication."""
    if get_current_user():
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            session.permanent = True
            flash(f"Welcome back, {user.name}! 👋", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid email or password. Please try again.", "error")
    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
def register():
    """Handles new user registration with input validation & password hashing."""
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template('register.html')
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template('register.html')
        if password != confirm:
            flash("Passwords don't match.", "error")
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists. Please log in.", "error")
            return render_template('register.html')

        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session.permanent = True
        flash(f"Account created! Welcome to KashFlow, {name}! 🎉", "success")
        return redirect(url_for('dashboard'))
    return render_template('register.html')


@app.route("/logout")
def logout():
    """Clears session data and logs out the current user."""
    name = get_current_user().name if get_current_user() else 'friend'
    session.clear()
    flash(f"See you soon, {name}! 👋", "success")
    return redirect(url_for('login'))

# ───────────────────────────────────────────────────────────────
# 8. FINANCIAL ENGINE & STATS COMPUTATION
# ───────────────────────────────────────────────────────────────

def _get_affiliate_recommendations(savings_rate, net_balance, total_income, goals):
    """Generates tailored financial partner recommendations based on cash flow health."""
    recs = []
    if savings_rate >= 15 and net_balance > 200:
        recs.append({
            'partner': 'Acorns Wealth',
            'icon': '🌱',
            'title': 'Invest Spare Change Automatically',
            'message': f"You're saving ${net_balance:.0f} this month! Acorns rounds up purchases and invests spare change hands-free.",
            'cta': 'Start with $5 →',
            'url': 'https://www.acorns.com',
            'color': 'cyan'
        })
    if net_balance > 400:
        recs.append({
            'partner': 'eToro Wealth',
            'icon': '📈',
            'title': 'Invest in Global Stocks & ETFs from $10',
            'message': "Put your surplus savings to work by building a diversified global stock & ETF portfolio hands-free.",
            'cta': 'Start Investing →',
            'url': 'https://www.etoro.com',
            'color': 'emerald'
        })
    if net_balance < 0 or savings_rate < 10:
        recs.append({
            'partner': 'Binance Digital USD',
            'icon': '🪙',
            'title': 'Protect Savings with Digital USD (USDT)',
            'message': "Hold inflation-hedged digital USD safely & earn flexible daily yield on your digital savings balance.",
            'cta': 'Explore Digital USD →',
            'url': 'https://www.binance.com',
            'color': 'purple'
        })
    if total_income > 500 or goals:
        recs.append({
            'partner': 'Payoneer Global',
            'icon': '💳',
            'title': 'Receive Global USD Payments Easily',
            'message': "Get paid by international clients worldwide and withdraw cash directly to your local bank or Whish card.",
            'cta': 'Get Payoneer Card →',
            'url': 'https://www.payoneer.com',
            'color': 'amber'
        })
    return recs[:2]


def get_overview_stats(expenses, incomes, bills=None, goals=None, budgets=None):
    """
    Core Financial Engine:
    Computes Health Score (0-100), 50/30/20 Breakdown, Daily Safe Allowance,
    6-Month Trends, Category Limits, and Financial Insights.
    """
    if bills   is None: bills   = Bill.query.filter_by(user_id=current_uid()).all()
    if goals   is None: goals   = Goal.query.filter_by(user_id=current_uid()).all()
    if budgets is None:
        current_month = datetime.now().strftime('%Y-%m')
        budgets = Budget.query.filter_by(user_id=current_uid(), month=current_month).all()

    # Filter to current month for monthly dashboard calculations
    current_mo_str = datetime.now().strftime('%Y-%m')
    monthly_expenses = [e for e in expenses if e.date and e.date.startswith(current_mo_str)]
    monthly_incomes  = [i for i in incomes  if i.date and i.date.startswith(current_mo_str)]

    # Calculate current month's expenses and incomes
    month_expense = sum(e.amount for e in monthly_expenses)
    month_income  = sum(i.amount for i in monthly_incomes)

    total_expense = sum(e.amount for e in expenses)
    total_income  = sum(i.amount for i in incomes)

    net_balance   = month_income - month_expense
    savings_rate  = round((net_balance / month_income * 100), 1) if month_income > 0 else 0.0
    days_in_month = calendar.monthrange(datetime.now().year, datetime.now().month)[1]
    today_day     = datetime.now().day
    days_left     = max(1, days_in_month - today_day)

    unpaid_bills_total = sum(b.amount for b in bills if not b.is_paid)
    safe_net   = max(0, net_balance - unpaid_bills_total)
    daily_safe = round(safe_net / days_left, 2) if days_left > 0 else 0.0

    # Calculate Financial Health Score (0 - 100)
    score = 50
    if month_income > 0:
        ratio = month_expense / month_income
        if   ratio <= 0.5:  score = 95
        elif ratio <= 0.7:  score = 80
        elif ratio <= 0.85: score = 65
        elif ratio <= 1.0:  score = 45
        else:               score = max(10, int(50 - (ratio - 1) * 60))
    if net_balance > 0 and savings_rate >= 20: score = min(100, score + 5)
    if unpaid_bills_total > 0: score = max(10, score - 5)

    if   score >= 85: health_grade, health_label, health_color_class, health_color_hex = 'A+', 'Excellent 🌟', 'emerald', '#10b981'
    elif score >= 70: health_grade, health_label, health_color_class, health_color_hex = 'B',  'Good 👍',      'indigo',  '#6366f1'
    elif score >= 50: health_grade, health_label, health_color_class, health_color_hex = 'C',  'Fair ⚠️',      'amber',   '#f59e0b'
    else:             health_grade, health_label, health_color_class, health_color_hex = 'D',  'Needs Work 🚨','rose',    '#ef4444'

    # Compute category totals
    exp_cat_totals = defaultdict(float)
    for e in (monthly_expenses or expenses):
        exp_cat_totals[e.category or 'General'] += e.amount

    # 50/30/20 Rule calculation
    needs_spent = sum(exp_cat_totals.get(c, 0) for c in NEEDS_CATEGORIES)
    wants_spent = sum(exp_cat_totals.get(c, 0) for c in WANTS_CATEGORIES)
    needs_pct   = round((needs_spent / month_income * 100), 1) if month_income > 0 else 0.0
    wants_pct   = round((wants_spent / month_income * 100), 1) if month_income > 0 else 0.0
    savings_pct = round((max(0, net_balance) / month_income * 100), 1) if month_income > 0 else 0.0

    sorted_cats = sorted(exp_cat_totals.items(), key=lambda x: x[1], reverse=True)
    top_cats    = sorted_cats[:6]

    # Month-over-month comparison chart data (last 6 months)
    now = datetime.now()
    months_labels, inc_data, exp_data = [], [], []
    for i in range(5, -1, -1):
        m, y = now.month - i, now.year
        while m <= 0: m += 12; y -= 1
        months_labels.append(datetime(y, m, 1).strftime('%b'))
        mo = f"{y}-{m:02d}"
        inc_data.append(round(sum(x.amount for x in incomes  if x.date and x.date.startswith(mo)), 2))
        exp_data.append(round(sum(x.amount for x in expenses if x.date and x.date.startswith(mo)), 2))

    # Dynamic Insights
    insights, category_warnings = [], []
    if month_income == 0 and total_income == 0:
        insights.append({'type': 'tip', 'icon': '💡', 'title': 'Add Your Income First',
            'message': 'Start by adding your salary or income sources to see your financial health score.',
            'action': 'Click "+ Income" at the top right to get started.'})
    else:
        if net_balance < 0:
            insights.append({'type': 'danger', 'icon': '🚨', 'title': 'Spending Exceeds Income!',
                'message': f'You are ${abs(net_balance):.2f} over budget this month.',
                'action': 'Review expenses and cut non-essential spending immediately.'})
        elif savings_rate < 10:
            insights.append({'type': 'warning', 'icon': '⚠️', 'title': 'Low Savings Rate',
                'message': f'You are saving only {savings_rate}% of income. Aim for 20%.',
                'action': 'Look for subscriptions or dining expenses you can reduce.'})
        else:
            insights.append({'type': 'success', 'icon': '✅', 'title': 'On Track!',
                'message': f'You are saving {savings_rate}% of your income this month.',
                'action': 'Keep it up! Consider investing some savings for long-term growth.'})

        for cat, amt in sorted_cats[:3]:
            pct = round((amt / month_income) * 100, 1) if month_income > 0 else 0.0
            if pct > 30:
                category_warnings.append({'category': cat, 'amount': round(amt, 2), 'pct': pct})
                insights.append({'type': 'warning', 'icon': '📊', 'title': f'High {cat} Spending',
                    'message': f'{cat} is {pct}% of your income (${amt:.2f}).',
                    'action': f'Set a monthly budget cap for {cat} to stay in control.'})

        if daily_safe > 0:
            insights.append({'type': 'tip', 'icon': '📅', 'title': 'Daily Safe-to-Spend',
                'message': f'You can safely spend ${daily_safe:.2f}/day for the next {days_left} days.',
                'action': 'Stick to this daily limit to finish the month in the green.'})

    # Dynamic daily safe context message
    if daily_safe >= 25.0:
        daily_safe_msg = "You're good for 1 nice meal out 🍔 & coffee!"
    elif daily_safe >= 10.0:
        daily_safe_msg = "You're good for 1 more coffee ☕ & snacks today!"
    elif daily_safe >= 3.0:
        daily_safe_msg = "You're good for 1 more coffee ☕ today!"
    elif daily_safe > 0.0:
        daily_safe_msg = "Stay mindful today to finish the month in green! 🌿"
    else:
        daily_safe_msg = "Take a no-spend day today to recharge! 🛡️"

    last_expense = {
        'description': expenses[0].description,
        'amount': expenses[0].amount,
        'category': expenses[0].category or 'General',
        'payment_method': expenses[0].payment_method or 'Card'
    } if expenses else None

    return {
        'total_income':      round(month_income, 2),
        'total_expense':     round(month_expense, 2),
        'income_count':      len(monthly_incomes) if monthly_incomes else len(incomes),
        'expense_count':     len(monthly_expenses) if monthly_expenses else len(expenses),
        'all_time_income':   round(total_income, 2),
        'all_time_expense':  round(total_expense, 2),

        'net_balance':       round(net_balance, 2),
        'savings_rate':      savings_rate,
        'daily_safe':        daily_safe,
        'daily_safe_msg':    daily_safe_msg,
        'days_left':         days_left,
        'health_score':      score,
        'health_grade':      health_grade,
        'health_label':      health_label,
        'health_color':      health_color_class,
        'health_color_hex':  health_color_hex,
        'last_expense':      last_expense,
        'unpaid_bills':      round(unpaid_bills_total, 2),

        'income_chart':      {'labels': [c for c,_ in top_cats], 'data': [round(a,2) for _,a in top_cats]},
        'comparison_chart':  {'labels': months_labels, 'income': inc_data, 'expenses': exp_data, 'data': [round(month_income, 2), round(month_expense, 2), round(max(0, net_balance), 2)]},
        'rule_50_30_20':     {
            'needs_pct':   min(100, max(0, needs_pct)),
            'wants_pct':   min(100, max(0, wants_pct)),
            'savings_pct': min(100, max(0, savings_pct)),
            'needs_amt':   round(needs_spent, 2),
            'wants_amt':   round(wants_spent, 2),
            'savings_amt': round(max(0, net_balance), 2)
        },
        'insights':          insights,
        'category_warnings': category_warnings,
        'budget_limits':     _compute_budget_usage(budgets, exp_cat_totals),
        'affiliate_recs':    _get_affiliate_recommendations(savings_rate, net_balance, month_income, goals)
    }


def _compute_budget_usage(budgets, exp_cat_totals):
    """Computes percentage usage against monthly budget limits for each category."""
    results = []
    for b in budgets:
        spent = round(exp_cat_totals.get(b.category, 0.0), 2)
        limit = b.monthly_limit
        pct   = round((spent / limit) * 100, 1) if limit > 0 else 0.0

        if   pct >= 100: status, status_label = 'over',    'Over Limit!'
        elif pct >= 80:  status, status_label = 'warning', f'{pct}% used — almost at limit!'
        else:            status, status_label = 'ok',      f'{pct}% used'

        results.append({
            'id': b.id,
            'category': b.category,
            'spent': spent,
            'limit': round(limit, 2),
            'pct': min(100, pct),
            'status': status,
            'status_label': status_label
        })
    return results

# ───────────────────────────────────────────────────────────────
# 9. MAIN DASHBOARD & HOME ROUTES
# ───────────────────────────────────────────────────────────────

@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    """Renders the main financial dashboard with stats, recent activities, and charts."""
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc(), Expense.id.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc(), Income.id.desc()).all()
    bills    = Bill.query.filter_by(user_id=uid).order_by(Bill.due_date.asc()).all()
    goals    = Goal.query.filter_by(user_id=uid).all()

    current_month = datetime.now().strftime('%Y-%m')
    budgets  = Budget.query.filter_by(user_id=uid, month=current_month).all()

    stats = get_overview_stats(expenses, incomes, bills, goals, budgets)

    # Combine recent expenses & incomes for activity feed
    activities = []
    for i in incomes:
        activities.append({
            'type': 'income', 'id': i.id, 'description': i.description,
            'amount': i.amount, 'category': i.category, 'date': i.date,
            'method': i.source, 'notes': i.notes
        })
    for e in expenses:
        activities.append({
            'type': 'expense', 'id': e.id, 'description': e.description,
            'amount': e.amount, 'category': e.category, 'date': e.date,
            'method': e.payment_method, 'notes': e.notes
        })
    activities.sort(key=lambda x: (x['date'], x['id']), reverse=True)
    recent_activities = activities[:10]
    today = datetime.now().strftime('%Y-%m-%d')

    return render_template("dashboard.html",
        stats=stats,
        bills=bills[:4],
        goals=goals[:3],
        recent_activities=recent_activities,
        expense_categories=EXPENSE_CATEGORIES,
        income_categories=INCOME_CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=today
    )


@app.route("/home")
def home():
    """Redirects /home to login or dashboard."""
    return redirect(url_for("login"))

# ───────────────────────────────────────────────────────────────
# 10. SCENARIO SIMULATIONS & CLEAN RESET
# ───────────────────────────────────────────────────────────────

@app.route("/reset-clean", methods=["GET", "POST"])
@login_required
def reset_clean():
    """Resets all financial data for the user for a fresh start."""
    uid = current_uid()
    Expense.query.filter_by(user_id=uid).delete()
    Income.query.filter_by(user_id=uid).delete()
    Bill.query.filter_by(user_id=uid).delete()
    Goal.query.filter_by(user_id=uid).delete()
    Budget.query.filter_by(user_id=uid).delete()
    db.session.commit()
    flash("All your data has been reset. Fresh start!", "success")
    return redirect(url_for("dashboard"))


@app.route("/simulate-low-income", methods=["GET", "POST"])
@login_required
def simulate_low_income():
    """Loads a low-income test scenario ($1,200 income vs $1,950 expenses)."""
    uid = current_uid()
    Expense.query.filter_by(user_id=uid).delete()
    Income.query.filter_by(user_id=uid).delete()
    Bill.query.filter_by(user_id=uid).delete()
    Goal.query.filter_by(user_id=uid).delete()

    today = datetime.now().strftime('%Y-%m-%d')
    db.session.add(Income(user_id=uid, description="Part-Time Wage", amount=1200.0, category="Salary", date=today, source="Direct Deposit"))
    db.session.add(Expense(user_id=uid, description="Apartment Rent", amount=950.0, category="Housing", date=today, payment_method="Bank Transfer"))
    db.session.add(Expense(user_id=uid, description="Shopping & Clothes", amount=450.0, category="Shopping", date=today, payment_method="Card"))
    db.session.add(Expense(user_id=uid, description="Groceries & Takeout", amount=350.0, category="Food", date=today, payment_method="Card"))
    db.session.add(Expense(user_id=uid, description="Gas & Rideshare", amount=200.0, category="Transportation", date=today, payment_method="Card"))
    db.session.add(Bill(user_id=uid, name="Electric Utility", amount=120.0, category="Utilities", due_date=today, is_paid=False))
    db.session.add(Bill(user_id=uid, name="Internet Service", amount=65.0, category="Utilities", due_date=today, is_paid=False))
    db.session.add(Goal(user_id=uid, title="Emergency Fund", target_amount=3000.0, current_amount=150.0, category="Emergency Fund"))

    db.session.commit()
    flash("Low-Income Test Scenario loaded ($1,200 Income vs $1,950 Expenses).", "error")
    return redirect(url_for("dashboard"))


@app.route("/simulate-healthy", methods=["GET", "POST"])
@login_required
def simulate_healthy():
    """Loads a healthy test scenario ($5,000 income vs $2,200 expenses)."""
    uid = current_uid()
    Expense.query.filter_by(user_id=uid).delete()
    Income.query.filter_by(user_id=uid).delete()
    Bill.query.filter_by(user_id=uid).delete()
    Goal.query.filter_by(user_id=uid).delete()

    today = datetime.now().strftime('%Y-%m-%d')
    db.session.add(Income(user_id=uid, description="Full-Time Salary", amount=4200.0, category="Salary", date=today, source="Direct Deposit"))
    db.session.add(Income(user_id=uid, description="Freelance Client Project", amount=800.0, category="Freelance", date=today, source="Bank Transfer"))
    db.session.add(Expense(user_id=uid, description="Apartment Rent", amount=1100.0, category="Housing", date=today, payment_method="Bank Transfer"))
    db.session.add(Expense(user_id=uid, description="Groceries", amount=450.0, category="Food", date=today, payment_method="Card"))
    db.session.add(Expense(user_id=uid, description="Electric & Internet", amount=180.0, category="Utilities", date=today, payment_method="Card"))
    db.session.add(Expense(user_id=uid, description="Weekend Outings", amount=270.0, category="Shopping", date=today, payment_method="Card"))
    db.session.add(Expense(user_id=uid, description="Transit Pass", amount=200.0, category="Transportation", date=today, payment_method="Card"))
    db.session.add(Bill(user_id=uid, name="Car Insurance", amount=140.0, category="Insurance", due_date=today, is_paid=False))
    db.session.add(Goal(user_id=uid, title="Emergency Fund", target_amount=5000.0, current_amount=3200.0, category="Emergency Fund"))
    db.session.add(Goal(user_id=uid, title="Summer Vacation", target_amount=1500.0, current_amount=950.0, category="Vacation"))

    db.session.commit()
    flash("Healthy Scenario loaded ($5,000 Income vs $2,200 Expenses).", "success")
    return redirect(url_for("dashboard"))

# ───────────────────────────────────────────────────────────────
# 11. EXPENSE MANAGEMENT ROUTES (CRUD)
# ───────────────────────────────────────────────────────────────

@app.route("/expenses")
@login_required
def list_expenses():
    """Lists all logged expenses for the current user."""
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc(), Expense.id.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template("expenses.html", expenses=expenses, stats=stats,
        categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS, today=today)


@app.route("/add", methods=["POST"])
@login_required
def add_expense():
    """Creates a new expense item."""
    description    = request.form.get("description", "").strip()
    amount_str     = request.form.get("amount", "").strip()
    category       = request.form.get("category", "General").strip()
    date           = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
    payment_method = request.form.get("payment_method", "Card").strip()
    notes          = request.form.get("notes", "").strip()

    if not description:
        flash("Expense description is required!", "error")
        return redirect(request.referrer or url_for("list_expenses"))

    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid positive amount.", "error")
        return redirect(request.referrer or url_for("list_expenses"))

    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    db.session.add(Expense(
        user_id=current_uid(),
        description=description,
        amount=amount,
        category=category,
        date=date,
        payment_method=payment_method,
        notes=notes
    ))
    db.session.commit()
    flash(f"Added expense: {description} (${amount:.2f})", "success")
    return redirect(request.referrer or url_for("list_expenses"))


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    """Edits an existing expense item."""
    expense = Expense.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    if request.method == "POST":
        description    = request.form.get("description", "").strip()
        amount_str     = request.form.get("amount", "").strip()
        category       = request.form.get("category", "General").strip()
        date           = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
        payment_method = request.form.get("payment_method", "Card").strip()
        notes          = request.form.get("notes", "").strip()

        if not description:
            flash("Description is required!", "error")
            return redirect(url_for("edit_expense", id=id))

        try:
            amount = float(amount_str)
            if amount <= 0: raise ValueError
        except (TypeError, ValueError):
            flash("Amount must be a valid positive number!", "error")
            return redirect(url_for("edit_expense", id=id))

        expense.description    = description
        expense.amount         = amount
        expense.category       = category
        expense.date           = date
        expense.payment_method = payment_method
        expense.notes          = notes

        db.session.commit()
        flash(f"Updated expense: {description} (${amount:.2f})", "success")
        return redirect(url_for("list_expenses"))
    return render_template("edit.html", expense=expense, categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS)


@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_expense(id):
    """Deletes an expense item."""
    expense = Expense.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    desc = expense.description
    db.session.delete(expense)
    db.session.commit()
    flash(f"Expense '{desc}' deleted.", "success")
    return redirect(request.referrer or url_for("list_expenses"))

# ───────────────────────────────────────────────────────────────
# 12. INCOME MANAGEMENT ROUTES (CRUD)
# ───────────────────────────────────────────────────────────────

@app.route("/incomes")
@login_required
def list_incomes():
    """Lists all logged income entries for the current user."""
    uid = current_uid()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc(), Income.id.desc()).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template("incomes.html", incomes=incomes, stats=stats,
        categories=INCOME_CATEGORIES, payment_methods=PAYMENT_METHODS, today=today)


@app.route("/add-income", methods=["POST"])
@login_required
def add_income():
    """Adds a new income source entry."""
    description = request.form.get("description", "").strip()
    amount_str  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "Salary").strip()
    date        = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
    source      = request.form.get("source", "Bank Transfer").strip()
    notes       = request.form.get("notes", "").strip()

    if not description:
        flash("Income description is required!", "error")
        return redirect(request.referrer or url_for("list_incomes"))

    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid positive amount.", "error")
        return redirect(request.referrer or url_for("list_incomes"))

    if not date:
        date = datetime.now().strftime('%Y-%m-%d')

    db.session.add(Income(
        user_id=current_uid(),
        description=description,
        amount=amount,
        category=category,
        date=date,
        source=source,
        notes=notes
    ))
    db.session.commit()
    flash(f"Added income: {description} (+${amount:.2f})", "success")
    return redirect(request.referrer or url_for("list_incomes"))


@app.route("/edit-income/<int:id>", methods=["GET", "POST"])
@login_required
def edit_income(id):
    """Edits an existing income entry."""
    income = Income.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        amount_str  = request.form.get("amount", "").strip()
        category    = request.form.get("category", "Salary").strip()
        date        = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
        source      = request.form.get("source", "Bank Transfer").strip()
        notes       = request.form.get("notes", "").strip()

        if not description:
            flash("Description is required!", "error")
            return redirect(url_for("edit_income", id=id))

        try:
            amount = float(amount_str)
            if amount <= 0: raise ValueError
        except (TypeError, ValueError):
            flash("Amount must be a valid positive number!", "error")
            return redirect(url_for("edit_income", id=id))

        income.description = description
        income.amount      = amount
        income.category    = category
        income.date        = date
        income.source      = source
        income.notes       = notes

        db.session.commit()
        flash(f"Updated income: {description} (+${amount:.2f})", "success")
        return redirect(url_for("list_incomes"))
    return render_template("edit_income.html", income=income, categories=INCOME_CATEGORIES, payment_methods=PAYMENT_METHODS)


@app.route("/delete-income/<int:id>", methods=["POST"])
@login_required
def delete_income(id):
    """Deletes an income entry."""
    income = Income.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    desc = income.description
    db.session.delete(income)
    db.session.commit()
    flash(f"Income '{desc}' deleted.", "success")
    return redirect(request.referrer or url_for("list_incomes"))

# ───────────────────────────────────────────────────────────────
# 13. BILL TRACKER ROUTES
# ───────────────────────────────────────────────────────────────

@app.route("/bills")
@login_required
def list_bills():
    """Lists recurring bills and due dates (Available to all; Premium unlocks unlimited tracking)."""
    uid = current_uid()
    bills = Bill.query.filter_by(user_id=uid).order_by(Bill.due_date.asc()).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes, bills=bills)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template("bills.html", bills=bills, stats=stats, categories=EXPENSE_CATEGORIES, today=today)


@app.route("/add-bill", methods=["POST"])
@login_required
@premium_required
def add_bill():
    """Adds a new bill to track due dates & unpaid totals (Requires Premium)."""
    name     = request.form.get("name", "").strip()
    amount_str = request.form.get("amount", "").strip()
    category = request.form.get("category", "Utilities").strip()
    due_date = request.form.get("due_date", datetime.now().strftime('%Y-%m-%d')).strip()
    recurring= request.form.get("recurring", "Monthly").strip()

    if not name:
        flash("Bill name is required!", "error")
        return redirect(url_for("list_bills"))

    try:
        amount = float(amount_str)
        if amount <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid amount.", "error")
        return redirect(url_for("list_bills"))

    db.session.add(Bill(
        user_id=current_uid(),
        name=name,
        amount=amount,
        category=category,
        due_date=due_date,
        recurring=recurring
    ))
    db.session.commit()
    flash(f"Bill '{name}' (${amount:.2f}) added!", "success")
    return redirect(url_for("list_bills"))


@app.route("/toggle-bill/<int:id>", methods=["POST"])
@login_required
def toggle_bill(id):
    """Toggles paid/unpaid status for a bill."""
    bill = Bill.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    bill.is_paid = not bill.is_paid
    db.session.commit()
    status_label = "paid ✅" if bill.is_paid else "unpaid ⏳"
    flash(f"Marked '{bill.name}' as {status_label}.", "success")
    return redirect(url_for("list_bills"))


@app.route("/delete-bill/<int:id>", methods=["POST"])
@login_required
@premium_required
def delete_bill(id):
    """Deletes a tracked bill."""
    bill = Bill.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(bill)
    db.session.commit()
    flash("Bill removed.", "success")
    return redirect(url_for("list_bills"))

# ───────────────────────────────────────────────────────────────
# 14. GOAL TRACKER ROUTES
# ───────────────────────────────────────────────────────────────

@app.route("/goals")
@login_required
def list_goals():
    """Lists savings goals and progress bars (Available to all; Premium unlocks goal creation)."""
    uid = current_uid()
    goals = Goal.query.filter_by(user_id=uid).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes, goals=goals)
    return render_template("goals.html", goals=goals, stats=stats)


@app.route("/add-goal", methods=["POST"])
@login_required
@premium_required
def add_goal():
    """Creates a new savings goal (Requires Premium)."""
    title      = request.form.get("title", "").strip()
    target_str = request.form.get("target_amount", "").strip()
    curr_str   = request.form.get("current_amount", "0").strip()
    target_date= request.form.get("target_date", "").strip()
    category   = request.form.get("category", "Emergency Fund").strip()

    if not title:
        flash("Goal title is required!", "error")
        return redirect(url_for("list_goals"))

    try:
        target_amount = float(target_str)
        current_amount = float(curr_str or 0)
        if target_amount <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter valid amounts.", "error")
        return redirect(url_for("list_goals"))

    db.session.add(Goal(
        user_id=current_uid(),
        title=title,
        target_amount=target_amount,
        current_amount=current_amount,
        target_date=target_date,
        category=category
    ))
    db.session.commit()
    flash(f"Goal '{title}' created!", "success")
    return redirect(url_for("list_goals"))


@app.route("/delete-goal/<int:id>", methods=["POST"])
@login_required
@premium_required
def delete_goal(id):
    """Deletes a savings goal."""
    goal = Goal.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    flash("Goal removed.", "success")
    return redirect(url_for("list_goals"))

# ───────────────────────────────────────────────────────────────
# 15. BUDGET PLANNER ROUTES
# ───────────────────────────────────────────────────────────────

@app.route("/budgets")
@login_required
def list_budgets():
    """Lists category budget caps and usage (Available to all; Premium unlocks budget caps)."""
    uid = current_uid()
    current_month = datetime.now().strftime('%Y-%m')
    budgets  = Budget.query.filter_by(user_id=uid, month=current_month).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes, budgets=budgets)
    return render_template("budgets.html", budgets=budgets, stats=stats, categories=EXPENSE_CATEGORIES)


@app.route("/add-budget", methods=["POST"])
@login_required
@premium_required
def add_budget():
    """Sets a monthly spending budget cap for a category (Requires Premium)."""
    category  = request.form.get("category", "General").strip()
    limit_str = request.form.get("monthly_limit", "").strip()
    month     = datetime.now().strftime('%Y-%m')

    try:
        monthly_limit = float(limit_str)
        if monthly_limit <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid budget limit.", "error")
        return redirect(url_for("list_budgets"))

    # Update existing budget or create new
    existing = Budget.query.filter_by(user_id=current_uid(), category=category, month=month).first()
    if existing:
        existing.monthly_limit = monthly_limit
    else:
        db.session.add(Budget(user_id=current_uid(), category=category, monthly_limit=monthly_limit, month=month))

    db.session.commit()
    flash(f"Monthly limit for '{category}' set to ${monthly_limit:.2f}!", "success")
    return redirect(url_for("list_budgets"))


@app.route("/delete-budget/<int:id>", methods=["POST"])
@login_required
@premium_required
def delete_budget(id):
    """Removes a category monthly budget cap."""
    budget = Budget.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(budget)
    db.session.commit()
    flash("Budget limit removed.", "success")
    return redirect(url_for("list_budgets"))

# ───────────────────────────────────────────────────────────────
# 16. USER PROFILE & ACCOUNT SETTINGS
# ───────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    """User account settings: Update profile name, email, or password."""
    user = get_current_user()
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_profile":
            name  = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not name or not email:
                flash("Name and email are required.", "error")
            else:
                existing = User.query.filter_by(email=email).first()
                if existing and existing.id != user.id:
                    flash("Email address is already in use.", "error")
                else:
                    user.name = name
                    user.email = email
                    db.session.commit()
                    flash("Profile updated successfully!", "success")

        elif action == "update_password":
            current_pass = request.form.get("current_password", "")
            new_pass     = request.form.get("new_password", "")
            confirm_pass = request.form.get("confirm_password", "")

            if not check_password_hash(user.password_hash, current_pass):
                flash("Current password is incorrect.", "error")
            elif len(new_pass) < 8:
                flash("New password must be at least 8 characters.", "error")
            elif new_pass != confirm_pass:
                flash("New passwords do not match.", "error")
            else:
                user.password_hash = generate_password_hash(new_pass)
                db.session.commit()
                flash("Password updated successfully!", "success")

        return redirect(url_for("settings"))

    return render_template("settings.html", user=user)

# ───────────────────────────────────────────────────────────────
# 17. PRICING & STRIPE PAYMENT INTEGRATION
# ───────────────────────────────────────────────────────────────

@app.route("/pricing")
def pricing():
    """Renders the Premium PRO upgrade page with Stripe checkout triggers."""
    user = get_current_user()
    return render_template("pricing.html",
        is_premium=user.is_premium if user else False,
        stripe_key=STRIPE_PUBLISHABLE_KEY
    )


@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    """Creates a Stripe Checkout session for Premium monthly or annual subscription."""
    user = get_current_user()
    if not user:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))
    cycle = request.form.get("cycle", "monthly")

    # Fallback: If Stripe keys are not configured in environment, activate Demo Mode
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        user.is_premium = True
        db.session.commit()
        plan_label = "$39.99/yr" if cycle == "annual" else "$4.99/mo"
        flash(f"🎉 [Demo Mode] Premium ({plan_label}) unlocked! Configure Stripe keys in .env for live payments.", "success")
        return redirect(url_for("dashboard"))

    try:
        # Create or reuse Stripe customer
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={'user_id': user.id}
            )
            user.stripe_customer_id = customer.id
            db.session.commit()

        price_id = STRIPE_ANNUAL_PRICE_ID if (cycle == "annual" and STRIPE_ANNUAL_PRICE_ID) else STRIPE_PRICE_ID

        session_stripe = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=f"{APP_URL}/dashboard?subscription=success",
            cancel_url=f"{APP_URL}/pricing?subscription=cancelled",
            metadata={'user_id': user.id, 'cycle': cycle}
        )
        return redirect(session_stripe.url, code=333)

    except stripe.StripeError as e:
        flash(f"Payment error: {str(e)}", "error")
        return redirect(url_for("pricing"))


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """Stripe webhook endpoint handling asynchronous subscription payment events."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    if not STRIPE_WEBHOOK_SECRET:
        if os.environ.get("FLASK_ENV") == "production" or os.environ.get("RAILWAY_ENVIRONMENT"):
            print("⚠️ Rejecting unsigned webhook in production mode")
            return jsonify({"error": "STRIPE_WEBHOOK_SECRET is required in production"}), 400

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except (ValueError, stripe.SignatureVerificationError) as e:
        print("Webhook signature error:", e)
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event.get("type", "")
    data_obj   = event.get("data", {}).get("object", {})

    if event_type in ["checkout.session.completed", "invoice.payment_succeeded"]:
        customer_id = data_obj.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.is_premium = True
            user.stripe_subscription_id = data_obj.get("subscription", "")
            db.session.commit()
            print(f"Stripe Webhook: Premium activated for user {user.email}")

    elif event_type in ["customer.subscription.deleted", "invoice.payment_failed"]:
        customer_id = data_obj.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.is_premium = False
            db.session.commit()
            print(f"Stripe Webhook: Premium deactivated for user {user.email}")

    return jsonify({"status": "success"}), 200


@app.route("/downgrade")
@login_required
def downgrade():
    """Cancels Premium subscription for testing/demo purposes."""
    user = get_current_user()
    user.is_premium = False
    db.session.commit()
    flash("Subscription cancelled. You are now on the Free tier.", "info")
    return redirect(url_for("pricing"))

# ───────────────────────────────────────────────────────────────
# 18. DATA EXPORT & LEGAL PAGES
# ───────────────────────────────────────────────────────────────

@app.route("/export-csv")
@login_required
@premium_required
def export_csv():
    """Exports all user financial transaction records to a CSV file (Requires Premium)."""
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Type', 'Date', 'Description', 'Category', 'Amount ($)', 'Payment Method / Source', 'Notes'])
    for i in incomes:
        writer.writerow(['Income', i.date, i.description, i.category, f"{i.amount:.2f}", i.source, i.notes or ''])
    for e in expenses:
        writer.writerow(['Expense', e.date, e.description, e.category, f"{e.amount:.2f}", e.payment_method, e.notes or ''])

    output.seek(0)
    filename = f"kashflow_export_{datetime.now().strftime('%Y%m')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )


@app.route("/privacy")
def privacy():
    """Renders the Privacy Policy page."""
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    """Renders the Terms of Service page."""
    return render_template("terms.html")

# ───────────────────────────────────────────────────────────────
# 19. APPLICATION INITIALIZATION & SERVER STARTUP
# ───────────────────────────────────────────────────────────────

# Initialize database schema and auto-seeding on application context load
with app.app_context():
    init_db()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_mode,
        use_reloader=False
    )
'''

with open("app.py", "w", encoding="utf-8") as f:
    f.write(commented_app)

print("Annotated app.py written successfully!")
