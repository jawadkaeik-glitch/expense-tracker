import os
import json
import sqlite3
import calendar
import csv
import io
import stripe
from datetime import datetime
from collections import defaultdict
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "kashflow-secret-2026")

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ── STRIPE CONFIGURATION ─────────────────────────────────────
STRIPE_SECRET_KEY      = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PRICE_ID        = os.environ.get("STRIPE_PRICE_ID", "")
STRIPE_ANNUAL_PRICE_ID = os.environ.get("STRIPE_ANNUAL_PRICE_ID", "")
STRIPE_WEBHOOK_SECRET  = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
APP_URL                = os.environ.get("APP_URL", "http://127.0.0.1:5000")


stripe.api_key = STRIPE_SECRET_KEY


EXPENSE_CATEGORIES = ['Food', 'Transportation', 'Housing', 'Shopping', 'Utilities', 'Health', 'General']
INCOME_CATEGORIES  = ['Salary', 'Freelance', 'Investments', 'Business', 'Gifts & Grants', 'Rental', 'Other']
PAYMENT_METHODS    = ['Card', 'Cash', 'Bank Transfer', 'Check', 'Crypto']
NEEDS_CATEGORIES   = {'Housing', 'Utilities', 'Food', 'Health', 'Transportation'}
WANTS_CATEGORIES   = {'Shopping', 'General'}

# ── MODELS ────────────────────────────────────────────────────

class User(db.Model):
    id                     = db.Column(db.Integer, primary_key=True)
    name                   = db.Column(db.String(100), nullable=False)
    email                  = db.Column(db.String(150), nullable=False, unique=True)
    password_hash          = db.Column(db.String(255), nullable=False)
    is_premium             = db.Column(db.Boolean, default=False)
    stripe_customer_id     = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    created_at             = db.Column(db.String(20), default=lambda: datetime.now().strftime('%Y-%m-%d'))


class Expense(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    description    = db.Column(db.String(100), nullable=False)
    amount         = db.Column(db.Float, nullable=False)
    category       = db.Column(db.String(50), nullable=False, default='General')
    date           = db.Column(db.String(10), nullable=False, default=lambda: datetime.now().strftime('%Y-%m-%d'))
    payment_method = db.Column(db.String(50), nullable=False, default='Card')
    notes          = db.Column(db.Text, nullable=True, default='')

class Income(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    description = db.Column(db.String(100), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    category    = db.Column(db.String(50), nullable=False, default='Salary')
    date        = db.Column(db.String(10), nullable=False, default=lambda: datetime.now().strftime('%Y-%m-%d'))
    source      = db.Column(db.String(50), nullable=False, default='Bank Transfer')
    notes       = db.Column(db.Text, nullable=True, default='')

class Bill(db.Model):
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    name      = db.Column(db.String(100), nullable=False)
    amount    = db.Column(db.Float, nullable=False)
    category  = db.Column(db.String(50), nullable=False, default='Utilities')
    due_date  = db.Column(db.String(10), nullable=False)
    is_paid   = db.Column(db.Boolean, default=False)
    recurring = db.Column(db.String(50), default='Monthly')

class Goal(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title          = db.Column(db.String(100), nullable=False)
    target_amount  = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date    = db.Column(db.String(10), nullable=True)
    category       = db.Column(db.String(50), default='Emergency Fund')

class Budget(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    category      = db.Column(db.String(50), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)
    month         = db.Column(db.String(7), nullable=False, default=lambda: datetime.now().strftime('%Y-%m'))


def init_db():
    """Initializes tables and migrates existing SQLite tables safely."""
    with app.app_context():
        db.create_all()
        try:
            db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
            conn = sqlite3.connect(app.instance_path + '/expenses.db' if 'instance' not in db_path else db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(expense)")
            exp_cols = [r[1] for r in cursor.fetchall()]
            for col, defn in [('category', "VARCHAR(50) DEFAULT 'General'"), ('date', "VARCHAR(10) DEFAULT ''"),
                               ('payment_method', "VARCHAR(50) DEFAULT 'Card'"), ('notes', "TEXT DEFAULT ''"),
                               ('user_id', "INTEGER")]:
                if col not in exp_cols:
                    cursor.execute(f"ALTER TABLE expense ADD COLUMN {col} {defn}")

            cursor.execute("PRAGMA table_info(income)")
            inc_cols = [r[1] for r in cursor.fetchall()]
            for col, defn in [('source', "VARCHAR(50) DEFAULT 'Bank Transfer'"), ('notes', "TEXT DEFAULT ''"),
                               ('user_id', "INTEGER")]:
                if col not in inc_cols:
                    cursor.execute(f"ALTER TABLE income ADD COLUMN {col} {defn}")

            for table in ['bill', 'goal', 'budget']:
                cursor.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in cursor.fetchall()]
                if 'user_id' not in cols:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER")

            # Ensure User stripe columns
            cursor.execute("PRAGMA table_info(user)")
            user_cols = [r[1] for r in cursor.fetchall()]
            for col, defn in [('stripe_customer_id', "VARCHAR(255)"),
                               ('stripe_subscription_id', "VARCHAR(255)")]:
                if col not in user_cols:
                    cursor.execute(f"ALTER TABLE user ADD COLUMN {col} {defn}")

            conn.commit()
            conn.close()
        except Exception as e:
            print("DB migration:", e)



# ── AUTH HELPERS ───────────────────────────────────────────────

def get_current_user():
    uid = session.get('user_id')
    return User.query.get(uid) if uid else None

def current_uid():
    return session.get('user_id')

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in to access KashFlow.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def is_premium():
    user = get_current_user()
    return user.is_premium if user else False

def premium_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash("Please log in to access KashFlow.", "error")
            return redirect(url_for('login'))
        if not is_premium():
            flash("This feature requires a Premium PRO subscription. Upgrade to unlock full access!", "error")
            return redirect(url_for('pricing'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    user = get_current_user()
    return {'is_premium': user.is_premium if user else False, 'current_user': user}


# ── AUTH ROUTES ───────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session.permanent = True
            flash(f"Welcome back, {user.name}! 👋", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid email or password. Please try again.", "error")
    return render_template('login.html')

@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get('user_id'):
        return redirect(url_for('dashboard'))
    if request.method == "POST":
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip().lower()
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
        user = User(name=name, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        session['user_id'] = user.id
        session.permanent = True
        flash(f"Account created! Welcome to KashFlow, {name}! 🎉", "success")
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route("/logout")
def logout():
    user = get_current_user()
    name = user.name if user else 'friend'
    session.clear()
    flash(f"See you soon, {name}! 👋", "success")
    return redirect(url_for('login'))

@app.route("/settings")
@login_required
def settings():
    user = get_current_user()
    return render_template("settings.html", user=user, stripe_configured=bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID))

@app.route("/update-profile", methods=["POST"])
@login_required
def update_profile():
    user = get_current_user()
    new_name = request.form.get("name", "").strip()
    if not new_name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for("settings"))
    user.name = new_name
    db.session.commit()
    flash("Profile name updated successfully! ✨", "success")
    return redirect(url_for("settings"))

@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    user = get_current_user()
    current_pass = request.form.get("current_password", "")
    new_pass     = request.form.get("new_password", "")
    confirm_pass = request.form.get("confirm_password", "")

    if not check_password_hash(user.password_hash, current_pass):
        flash("Current password is incorrect.", "error")
        return redirect(url_for("settings"))
    if len(new_pass) < 8:
        flash("New password must be at least 8 characters.", "error")
        return redirect(url_for("settings"))
    if new_pass != confirm_pass:
        flash("New passwords do not match.", "error")
        return redirect(url_for("settings"))

    user.password_hash = generate_password_hash(new_pass)
    db.session.commit()
    flash("Password updated successfully! 🔒", "success")
    return redirect(url_for("settings"))

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

@app.route("/terms")
def terms():
    return render_template("terms.html")




# ── AFFILIATE RECOMMENDATIONS ─────────────────────────────────

def _get_affiliate_recommendations(savings_rate, net_balance, total_income, goals):
    recs = []
    # 1. Global Multi-Currency Account (Wise) - Works worldwide & Lebanon
    if savings_rate >= 10 and net_balance > 150:
        recs.append({
            'partner': 'Wise (TransferWise)',
            'icon': '🌐',
            'title': 'Hold & Send Multi-Currency USD/EUR',
            'message': f"You're saving ${net_balance:.0f} this month! Hold multi-currency balances & transfer globally with real exchange rates.",
            'cta': 'Open Free Wise Account →',
            'url': 'https://wise.com',
            'color': 'cyan'
        })
    # 2. Global Wealth & Stock Investing (eToro / Interactive Brokers)
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
    # 3. Global Digital USD & Yield (Binance / USDT) - Huge in MENA/Lebanon
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
    # 4. Global Freelance & Business Payouts (Payoneer)
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



# ── STATS ENGINE ──────────────────────────────────────────────

def get_overview_stats(expenses, incomes, bills=None, goals=None, budgets=None):
    if bills   is None: bills   = Bill.query.filter_by(user_id=current_uid()).all()
    if goals   is None: goals   = Goal.query.filter_by(user_id=current_uid()).all()
    if budgets is None:
        current_month = datetime.now().strftime('%Y-%m')
        budgets = Budget.query.filter_by(user_id=current_uid(), month=current_month).all()

    # Filter to current month for monthly dashboard calculations
    current_mo_str = datetime.now().strftime('%Y-%m')
    monthly_expenses = [e for e in expenses if e.date and e.date.startswith(current_mo_str)]
    monthly_incomes  = [i for i in incomes  if i.date and i.date.startswith(current_mo_str)]

    # Use current month if available, fallback to total if new user
    month_expense = sum(e.amount for e in monthly_expenses) if monthly_expenses else sum(e.amount for e in expenses)
    month_income  = sum(i.amount for i in monthly_incomes)  if monthly_incomes  else sum(i.amount for i in incomes)

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

    exp_cat_totals = defaultdict(float)
    for e in (monthly_expenses or expenses):
        exp_cat_totals[e.category or 'General'] += e.amount

    needs_spent = sum(exp_cat_totals.get(c, 0) for c in NEEDS_CATEGORIES)
    wants_spent = sum(exp_cat_totals.get(c, 0) for c in WANTS_CATEGORIES)
    needs_pct   = round((needs_spent / month_income * 100), 1) if month_income > 0 else 0.0
    wants_pct   = round((wants_spent / month_income * 100), 1) if month_income > 0 else 0.0
    savings_pct = round((max(0, net_balance) / month_income * 100), 1) if month_income > 0 else 0.0

    sorted_cats = sorted(exp_cat_totals.items(), key=lambda x: x[1], reverse=True)
    top_cats    = sorted_cats[:6]

    now = datetime.now()
    months_labels, inc_data, exp_data = [], [], []
    for i in range(5, -1, -1):
        m, y = now.month - i, now.year
        while m <= 0: m += 12; y -= 1
        months_labels.append(datetime(y, m, 1).strftime('%b'))
        mo = f"{y}-{m:02d}"
        inc_data.append(round(sum(x.amount for x in incomes  if x.date and x.date.startswith(mo)), 2))
        exp_data.append(round(sum(x.amount for x in expenses if x.date and x.date.startswith(mo)), 2))

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

    return {
        'total_income':      round(month_income, 2),
        'total_expense':     round(month_expense, 2),
        'all_time_income':   round(total_income, 2),
        'all_time_expense':  round(total_expense, 2),
        'net_balance':       round(net_balance, 2),
        'savings_rate':      savings_rate,
        'daily_safe':        daily_safe,
        'days_left':         days_left,
        'health_score':      score,
        'health_grade':      health_grade,
        'health_label':      health_label,
        'health_color':      health_color_class,
        'health_color_hex':  health_color_hex,
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
    results = []
    for b in budgets:
        spent = round(exp_cat_totals.get(b.category, 0.0), 2)
        limit = b.monthly_limit
        pct   = round((spent / limit) * 100, 1) if limit > 0 else 0.0
        if   pct >= 100: status, label = 'over',    'Over Limit!'
        elif pct >= 80:  status, label = 'warning', f'{pct}% used — almost at limit!'
        else:            status, label = 'ok',      f'{pct}% used'
        results.append({'id': b.id, 'category': b.category, 'spent': spent,
                        'limit': round(limit, 2), 'pct': min(100, pct),
                        'status': status, 'status_label': label})
    return results


# ── DASHBOARD ─────────────────────────────────────────────────

@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc(), Expense.id.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc(), Income.id.desc()).all()
    bills    = Bill.query.filter_by(user_id=uid).order_by(Bill.due_date.asc()).all()
    goals    = Goal.query.filter_by(user_id=uid).all()
    budgets  = Budget.query.filter_by(user_id=uid, month=datetime.now().strftime('%Y-%m')).all()
    stats    = get_overview_stats(expenses, incomes, bills, goals, budgets)

    activities = []
    for i in incomes:
        activities.append({'type':'income','id':i.id,'description':i.description,'amount':i.amount,
                           'category':i.category,'date':i.date,'method':i.source,'notes':i.notes})
    for e in expenses:
        activities.append({'type':'expense','id':e.id,'description':e.description,'amount':e.amount,
                           'category':e.category,'date':e.date,'method':e.payment_method,'notes':e.notes})
    activities.sort(key=lambda x: (x['date'], x['id']), reverse=True)

    return render_template("dashboard.html", stats=stats, bills=bills[:4], goals=goals[:3],
        recent_activities=activities[:10], expense_categories=EXPENSE_CATEGORIES,
        income_categories=INCOME_CATEGORIES, payment_methods=PAYMENT_METHODS,
        today=datetime.now().strftime('%Y-%m-%d'))

@app.route("/home")
def home():
    return redirect(url_for("login"))


# ── SIMULATIONS & RESET ───────────────────────────────────────

@app.route("/reset-clean")
@login_required
def reset_clean():
    uid = current_uid()
    for Model in [Expense, Income, Bill, Goal, Budget]:
        Model.query.filter_by(user_id=uid).delete()
    db.session.commit()
    flash("All your data has been reset. Fresh start!", "success")
    return redirect(url_for("dashboard"))

@app.route("/simulate-low-income")
@login_required
def simulate_low_income():
    uid = current_uid()
    for Model in [Expense, Income, Bill, Goal]:
        Model.query.filter_by(user_id=uid).delete()
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
    flash("Low-Income Scenario loaded ($1,200 Income vs $1,950 Expenses).", "error")
    return redirect(url_for("dashboard"))

@app.route("/simulate-healthy")
@login_required
def simulate_healthy():
    uid = current_uid()
    for Model in [Expense, Income, Bill, Goal]:
        Model.query.filter_by(user_id=uid).delete()
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


# ── EXPENSE ROUTES ────────────────────────────────────────────

@app.route("/expenses")
@login_required
def list_expenses():
    uid      = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc(), Expense.id.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    base_stats = get_overview_stats(expenses, incomes)

    # Expense-page-specific stats
    exp_count  = len(expenses)
    total_spent = base_stats['total_expense']
    avg_expense = round(total_spent / exp_count, 2) if exp_count > 0 else 0.0
    cat_totals  = defaultdict(float)
    for e in expenses:
        cat_totals[e.category or 'General'] += e.amount
    top_category = max(cat_totals, key=cat_totals.get) if cat_totals else 'N/A'

    stats = dict(base_stats)
    stats.update({'total_spent': total_spent, 'total_count': exp_count,
                  'avg_expense': avg_expense, 'top_category': top_category,
                  'category_chart': base_stats['income_chart'],
                  'trend_chart': base_stats['comparison_chart']})

    return render_template("expenses.html", expenses=expenses, stats=stats,
        categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS, today=datetime.now().strftime('%Y-%m-%d'))

@app.route("/add", methods=["POST"])
@login_required
def add_expense():
    desc   = request.form.get("description", "").strip()
    amt_s  = request.form.get("amount", "").strip()
    cat    = request.form.get("category", "General").strip()
    date   = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip() or datetime.now().strftime('%Y-%m-%d')
    method = request.form.get("payment_method", "Card").strip()
    notes  = request.form.get("notes", "").strip()
    if not desc:
        flash("Expense description is required!", "error")
        return redirect(request.referrer or url_for("list_expenses"))
    try:
        amt = float(amt_s)
        if amt <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid positive amount.", "error")
        return redirect(request.referrer or url_for("list_expenses"))
    db.session.add(Expense(user_id=current_uid(), description=desc, amount=amt, category=cat, date=date, payment_method=method, notes=notes))
    db.session.commit()
    flash(f"Added expense: {desc} (${amt:.2f})", "success")
    return redirect(request.referrer or url_for("list_expenses"))

@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    expense = Expense.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    if request.method == "POST":
        desc   = request.form.get("description", "").strip()
        amt_s  = request.form.get("amount", "").strip()
        cat    = request.form.get("category", "General").strip()
        date   = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
        method = request.form.get("payment_method", "Card").strip()
        notes  = request.form.get("notes", "").strip()
        if not desc:
            flash("Description is required!", "error"); return redirect(url_for("edit_expense", id=id))
        try:
            amt = float(amt_s)
            if amt <= 0: raise ValueError
        except (TypeError, ValueError):
            flash("Amount must be a valid positive number!", "error"); return redirect(url_for("edit_expense", id=id))
        expense.description = desc; expense.amount = amt; expense.category = cat
        expense.date = date; expense.payment_method = method; expense.notes = notes
        db.session.commit()
        flash(f"Updated expense: {desc} (${amt:.2f})", "success")
        return redirect(url_for("list_expenses"))
    return render_template("edit.html", expense=expense, categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS)

@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_expense(id):
    uid = current_uid()
    expense = Expense.query.filter_by(id=id, user_id=uid).first_or_404()
    desc = expense.description

    db.session.delete(expense); db.session.commit()
    flash(f"Expense '{desc}' deleted.", "success")
    return redirect(request.referrer or url_for("list_expenses"))


# ── INCOME ROUTES ─────────────────────────────────────────────

@app.route("/incomes")
@login_required
def list_incomes():
    uid     = current_uid()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc(), Income.id.desc()).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    base_stats = get_overview_stats(expenses, incomes)

    # Income-page-specific stats
    inc_count = len(incomes)
    inc_cat_totals = defaultdict(float)
    for i in incomes:
        inc_cat_totals[i.category or 'Other'] += i.amount
    top_income_category = max(inc_cat_totals, key=inc_cat_totals.get) if inc_cat_totals else 'N/A'

    stats = dict(base_stats)
    stats.update({'income_count': inc_count, 'top_income_category': top_income_category})

    return render_template("incomes.html", incomes=incomes, stats=stats,
        categories=INCOME_CATEGORIES, payment_methods=PAYMENT_METHODS, today=datetime.now().strftime('%Y-%m-%d'))

@app.route("/add-income", methods=["POST"])
@login_required
def add_income():
    desc  = request.form.get("description", "").strip()
    amt_s = request.form.get("amount", "").strip()
    cat   = request.form.get("category", "Salary").strip()
    date  = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip() or datetime.now().strftime('%Y-%m-%d')
    src   = request.form.get("source", "Bank Transfer").strip()
    notes = request.form.get("notes", "").strip()
    if not desc:
        flash("Income description is required!", "error"); return redirect(request.referrer or url_for("list_incomes"))
    try:
        amt = float(amt_s)
        if amt <= 0: raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid positive amount.", "error"); return redirect(request.referrer or url_for("list_incomes"))
    db.session.add(Income(user_id=current_uid(), description=desc, amount=amt, category=cat, date=date, source=src, notes=notes))
    db.session.commit()
    flash(f"Added income: {desc} (+${amt:.2f})", "success")
    return redirect(request.referrer or url_for("list_incomes"))

@app.route("/edit-income/<int:id>", methods=["GET", "POST"])
@login_required
def edit_income(id):
    income = Income.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    if request.method == "POST":
        desc  = request.form.get("description", "").strip()
        amt_s = request.form.get("amount", "").strip()
        cat   = request.form.get("category", "Salary").strip()
        date  = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
        src   = request.form.get("source", "Bank Transfer").strip()
        notes = request.form.get("notes", "").strip()
        if not desc:
            flash("Description is required!", "error"); return redirect(url_for("edit_income", id=id))
        try:
            amt = float(amt_s)
            if amt <= 0: raise ValueError
        except (TypeError, ValueError):
            flash("Amount must be a valid positive number!", "error"); return redirect(url_for("edit_income", id=id))
        income.description = desc; income.amount = amt; income.category = cat
        income.date = date; income.source = src; income.notes = notes
        db.session.commit()
        flash(f"Updated income: {desc} (+${amt:.2f})", "success")
        return redirect(url_for("list_incomes"))
    return render_template("edit_income.html", income=income, categories=INCOME_CATEGORIES, payment_methods=PAYMENT_METHODS)

@app.route("/delete-income/<int:id>", methods=["POST"])
@login_required
def delete_income(id):
    income = Income.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    desc = income.description
    db.session.delete(income); db.session.commit()
    flash(f"Income '{desc}' deleted.", "success")
    return redirect(request.referrer or url_for("list_incomes"))


# ── BILLS ROUTES ─────────────────────────────────────────────

@app.route("/bills")
@login_required
@premium_required
def list_bills():
    return render_template("bills.html",
        bills=Bill.query.filter_by(user_id=current_uid()).order_by(Bill.due_date.asc()).all(),
        today=datetime.now().strftime('%Y-%m-%d'))

@app.route("/add-bill", methods=["POST"])
@login_required
@premium_required
def add_bill():
    name    = request.form.get("name", "").strip()
    amt_s   = request.form.get("amount", "").strip()
    cat     = request.form.get("category", "Utilities").strip()
    due     = request.form.get("due_date", datetime.now().strftime('%Y-%m-%d')).strip()
    recur   = request.form.get("recurring", "Monthly").strip()
    if not name or not amt_s:
        flash("Bill name and amount are required!", "error"); return redirect(url_for("list_bills"))
    try: amt = float(amt_s)
    except ValueError:
        flash("Invalid bill amount!", "error"); return redirect(url_for("list_bills"))
    db.session.add(Bill(user_id=current_uid(), name=name, amount=amt, category=cat, due_date=due, recurring=recur))
    db.session.commit()
    flash(f"Added bill: {name} (${amt:.2f})", "success")
    return redirect(url_for("list_bills"))

@app.route("/toggle-bill/<int:id>", methods=["POST"])
@login_required
@premium_required
def toggle_bill(id):
    bill = Bill.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    bill.is_paid = not bill.is_paid
    db.session.commit()
    flash(f"Marked '{bill.name}' as {'Paid' if bill.is_paid else 'Unpaid'}.", "success")
    return redirect(request.referrer or url_for("list_bills"))

@app.route("/delete-bill/<int:id>", methods=["POST"])
@login_required
@premium_required
def delete_bill(id):
    bill = Bill.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(bill); db.session.commit()
    flash("Bill deleted.", "success")
    return redirect(url_for("list_bills"))


# ── GOALS ROUTES ─────────────────────────────────────────────

@app.route("/goals")
@login_required
@premium_required
def list_goals():
    return render_template("goals.html",
        goals=Goal.query.filter_by(user_id=current_uid()).all(),
        today=datetime.now().strftime('%Y-%m-%d'))

@app.route("/add-goal", methods=["POST"])
@login_required
@premium_required
def add_goal():
    title   = request.form.get("title", "").strip()
    tgt_s   = request.form.get("target_amount", "").strip()
    cur_s   = request.form.get("current_amount", "0").strip()
    cat     = request.form.get("category", "Emergency Fund").strip()
    tgt_dt  = request.form.get("target_date", "").strip()
    if not title or not tgt_s:
        flash("Goal title and target amount required!", "error"); return redirect(url_for("list_goals"))
    try:
        tgt = float(tgt_s); cur = float(cur_s) if cur_s else 0.0
    except ValueError:
        flash("Invalid goal amounts!", "error"); return redirect(url_for("list_goals"))
    db.session.add(Goal(user_id=current_uid(), title=title, target_amount=tgt, current_amount=cur, category=cat, target_date=tgt_dt))
    db.session.commit()
    flash(f"Created goal: {title}", "success")
    return redirect(url_for("list_goals"))

@app.route("/update-goal/<int:id>", methods=["POST"])
@login_required
@premium_required
def update_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    try:
        deposit = float(request.form.get("deposit_amount", "0").strip())
        goal.current_amount = max(0.0, goal.current_amount + deposit)
        db.session.commit()
        flash(f"Updated '{goal.title}' balance: ${goal.current_amount:.2f}", "success")
    except ValueError:
        flash("Invalid deposit amount!", "error")
    return redirect(url_for("list_goals"))

@app.route("/delete-goal/<int:id>", methods=["POST"])
@login_required
@premium_required
def delete_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(goal); db.session.commit()
    flash("Goal deleted.", "success")
    return redirect(url_for("list_goals"))


# ── BUDGET ROUTES ─────────────────────────────────────────────

@app.route("/budgets")
@login_required
@premium_required
def list_budgets():
    uid   = current_uid()
    month = datetime.now().strftime('%Y-%m')
    budgets  = Budget.query.filter_by(user_id=uid, month=month).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    exp_cat  = defaultdict(float)
    for e in expenses: exp_cat[e.category or 'General'] += e.amount
    return render_template("budgets.html", budgets=budgets, budget_usage=_compute_budget_usage(budgets, exp_cat),
        categories=EXPENSE_CATEGORIES, current_month=month, month_label=datetime.now().strftime('%B %Y'))

@app.route("/add-budget", methods=["POST"])
@login_required
@premium_required
def add_budget():

    uid   = current_uid()
    cat   = request.form.get("category", "").strip()
    lim_s = request.form.get("monthly_limit", "").strip()
    month = datetime.now().strftime('%Y-%m')
    if not cat or not lim_s:
        flash("Category and monthly limit are required!", "error"); return redirect(url_for("list_budgets"))
    try:
        lim = float(lim_s)
        if lim <= 0: raise ValueError
    except ValueError:
        flash("Monthly limit must be a positive number!", "error"); return redirect(url_for("list_budgets"))
    existing = Budget.query.filter_by(user_id=uid, category=cat, month=month).first()
    if existing:
        existing.monthly_limit = lim
        flash(f"Updated {cat} budget to ${lim:.2f}/month.", "success")
    else:
        db.session.add(Budget(user_id=uid, category=cat, monthly_limit=lim, month=month))
        flash(f"Set {cat} budget: ${lim:.2f}/month.", "success")
    db.session.commit()
    return redirect(url_for("list_budgets"))

@app.route("/delete-budget/<int:id>", methods=["POST"])
@login_required
def delete_budget(id):
    budget = Budget.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(budget); db.session.commit()
    flash("Budget limit removed.", "success")
    return redirect(url_for("list_budgets"))


# ── PREMIUM & STRIPE PAYMENT ROUTES ───────────────────────────

@app.route("/pricing")
def pricing():
    return render_template("pricing.html", stripe_configured=bool(STRIPE_SECRET_KEY and STRIPE_PRICE_ID))

@app.route("/create-checkout-session", methods=["POST"])
@login_required
def create_checkout_session():
    user = get_current_user()
    cycle = request.form.get("cycle", "monthly")

    # Fallback: if Stripe is not configured, use demo mode
    if not STRIPE_SECRET_KEY or not STRIPE_PRICE_ID:
        user.is_premium = True
        db.session.commit()
        plan_label = "$39.99/yr" if cycle == "annual" else "$4.99/mo"
        flash(f"🎉 [Demo Mode] Premium ({plan_label}) unlocked! Configure Stripe keys in .env for real payments.", "success")
        return redirect(url_for("dashboard"))

    try:
        # Create or reuse Stripe customer
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={"kashflow_user_id": str(user.id)}
            )
            user.stripe_customer_id = customer.id
            db.session.commit()

        # Pick price ID based on selected cycle
        price_id = STRIPE_ANNUAL_PRICE_ID if (cycle == "annual" and STRIPE_ANNUAL_PRICE_ID) else STRIPE_PRICE_ID

        # Create Stripe Checkout Session for subscription
        checkout_session = stripe.checkout.Session.create(
            customer=user.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=APP_URL + url_for("payment_success") + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=APP_URL + url_for("payment_cancel"),
            metadata={"kashflow_user_id": str(user.id), "cycle": cycle},
        )
        return redirect(checkout_session.url, code=303)

    except stripe.StripeError as e:
        flash(f"Payment error: {str(e)}", "error")
        return redirect(url_for("pricing"))


@app.route("/stripe-webhook", methods=["POST"])
def stripe_webhook():
    """Stripe calls this endpoint when payment events happen."""
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        if STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        else:
            event = json.loads(payload)
    except (ValueError, stripe.SignatureVerificationError) as e:
        print("Webhook signature error:", e)
        return jsonify({"error": "Invalid signature"}), 400

    event_type = event.get("type", "")
    data_obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        # Payment successful — activate premium
        customer_id = data_obj.get("customer")
        subscription_id = data_obj.get("subscription")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.is_premium = True
            user.stripe_subscription_id = subscription_id
            db.session.commit()
            print(f"✅ Premium activated for {user.email}")

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        # Subscription cancelled or expired
        customer_id = data_obj.get("customer")
        status = data_obj.get("status", "")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user and status in ("canceled", "unpaid", "past_due"):
            user.is_premium = False
            user.stripe_subscription_id = None
            db.session.commit()
            print(f"⚠️ Premium deactivated for {user.email} (status: {status})")

    elif event_type == "invoice.payment_failed":
        # Payment failed — notify user
        customer_id = data_obj.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            print(f"❌ Payment failed for {user.email}")

    return jsonify({"status": "ok"}), 200

@app.route("/payment-success")
@login_required
def payment_success():
    # Check if Stripe already activated premium via webhook
    user = get_current_user()
    session_id = request.args.get("session_id")

    # If webhook hasn't fired yet, manually check and activate
    if not user.is_premium and session_id and STRIPE_SECRET_KEY:
        try:
            checkout_session = stripe.checkout.Session.retrieve(session_id)
            if checkout_session.payment_status == "paid":
                user.is_premium = True
                user.stripe_subscription_id = checkout_session.subscription
                if not user.stripe_customer_id:
                    user.stripe_customer_id = checkout_session.customer
                db.session.commit()
        except Exception as e:
            print("Session check error:", e)

    return render_template("payment_success.html")

@app.route("/payment-cancel")
@login_required
def payment_cancel():
    return render_template("payment_cancel.html")

@app.route("/cancel-subscription", methods=["POST"])
@login_required
def cancel_subscription():
    user = get_current_user()

    if user.stripe_subscription_id and STRIPE_SECRET_KEY:
        try:
            stripe.Subscription.cancel(user.stripe_subscription_id)
            user.is_premium = False
            user.stripe_subscription_id = None
            db.session.commit()
            flash("Your Premium subscription has been cancelled. You can re-subscribe anytime.", "success")
        except stripe.StripeError as e:
            flash(f"Cancellation error: {str(e)}", "error")
    else:
        # Demo mode or no active subscription
        user.is_premium = False
        user.stripe_subscription_id = None
        db.session.commit()
        flash("You've switched back to the Free plan.", "success")

    return redirect(url_for("pricing"))

# Legacy route aliases for backwards compatibility
@app.route("/upgrade")
@login_required
def upgrade():
    return redirect(url_for("pricing"))

@app.route("/downgrade", methods=["GET", "POST"])
@login_required
def downgrade():
    return redirect(url_for("cancel_subscription"), code=302)


@app.route("/export-csv")
@login_required
@premium_required
def export_csv():
    uid      = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc()).all()
    output   = io.StringIO()
    writer   = csv.writer(output)
    writer.writerow(['Type', 'Date', 'Description', 'Category', 'Amount', 'Method / Source', 'Notes'])
    for i in incomes:
        writer.writerow(['Income',  i.date, i.description, i.category, f"+{i.amount:.2f}", i.source or '',         i.notes or ''])
    for e in expenses:
        writer.writerow(['Expense', e.date, e.description, e.category, f"-{e.amount:.2f}", e.payment_method or '', e.notes or ''])
    output.seek(0)
    fn = f"kashflow_export_{datetime.now().strftime('%Y%m')}.csv"
    return Response(output.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename={fn}'})


# Initialize database and migrations on startup (for Gunicorn & local dev)
with app.app_context():
    init_db()

if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "True").lower() == "true"
    app.run(
        host=os.environ.get("FLASK_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", 5000)),
        debug=debug_mode,
        use_reloader=False
    )


