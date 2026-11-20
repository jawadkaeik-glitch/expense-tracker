"""
KashFlow - Smart Personal Finance & Expense Tracker
100% Free, Secure, Modern Architecture.
"""

import os
import io
import csv
import math
import calendar
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, Response, jsonify, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

# ───────────────────────────────────────────────────────────────
# 1. CONFIGURATION & SECURITY HARDENING
# ───────────────────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__)

# Secret key handling: In production, require an explicit secure secret key.
env_name = os.environ.get("FLASK_ENV", "").lower()
is_production = env_name == "production" or bool(os.environ.get("RENDER")) or bool(os.environ.get("RAILWAY_ENVIRONMENT"))

secret_key = os.environ.get("FLASK_SECRET_KEY")
if not secret_key:
    if is_production:
        raise RuntimeError("FLASK_SECRET_KEY environment variable MUST be set in production mode.")
    # Safe local fallback for development
    secret_key = "kashflow-local-dev-secret-only"
app.secret_key = secret_key

# Database connection: Neon / PostgreSQL in production, SQLite for local dev
database_url = os.environ.get("DATABASE_URL")
if database_url:
    # Ensure psycopg 3 driver prefix for PostgreSQL URLs
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Cookie hardening
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
if is_production:
    app.config['SESSION_COOKIE_SECURE'] = True

# CSRF Protection across all POST/PUT/DELETE forms
csrf = CSRFProtect(app)

# Rate Limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["300 per hour"],
    storage_uri="memory://"
)

db = SQLAlchemy(app)

# Security Headers
@app.after_request
def apply_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    if is_production:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response


# ───────────────────────────────────────────────────────────────
# 2. GLOBAL CONSTANTS & CATEGORIES
# ───────────────────────────────────────────────────────────────
EXPENSE_CATEGORIES = ['Food', 'Transportation', 'Housing', 'Shopping', 'Utilities', 'Health', 'General']
INCOME_CATEGORIES  = ['Salary', 'Freelance', 'Investments', 'Business', 'Gifts & Grants', 'Rental', 'Other']
PAYMENT_METHODS    = ['Card', 'Cash', 'Bank Transfer', 'Check', 'Crypto']

# 50/30/20 Rule categorization:
NEEDS_CATEGORIES   = {'Housing', 'Utilities', 'Food', 'Health', 'Transportation'}
WANTS_CATEGORIES   = {'Shopping', 'General'}


# ───────────────────────────────────────────────────────────────
# 3. DATABASE MODELS (Clean & 100% Free)
# ───────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'users'
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(150), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at    = db.Column(db.String(20), default=lambda: datetime.now().strftime('%Y-%m-%d'))


class Expense(db.Model):
    __tablename__ = 'expenses'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    description    = db.Column(db.String(100), nullable=False)
    amount         = db.Column(db.Float, nullable=False)
    category       = db.Column(db.String(50), nullable=False, default='General')
    date           = db.Column(db.String(10), nullable=False, default=lambda: datetime.now().strftime('%Y-%m-%d'))
    payment_method = db.Column(db.String(50), nullable=False, default='Card')
    notes          = db.Column(db.Text, nullable=True, default='')


class Income(db.Model):
    __tablename__ = 'incomes'
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    description = db.Column(db.String(100), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    category    = db.Column(db.String(50), nullable=False, default='Salary')
    date        = db.Column(db.String(10), nullable=False, default=lambda: datetime.now().strftime('%Y-%m-%d'))
    source      = db.Column(db.String(50), nullable=False, default='Bank Transfer')
    notes       = db.Column(db.Text, nullable=True, default='')


class Bill(db.Model):
    __tablename__ = 'bills'
    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    name      = db.Column(db.String(100), nullable=False)
    amount    = db.Column(db.Float, nullable=False)
    category  = db.Column(db.String(50), nullable=False, default='Utilities')
    due_date  = db.Column(db.String(10), nullable=False)
    is_paid   = db.Column(db.Boolean, default=False)
    recurring = db.Column(db.String(50), default='Monthly')


class Goal(db.Model):
    __tablename__ = 'goals'
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title          = db.Column(db.String(100), nullable=False)
    target_amount  = db.Column(db.Float, nullable=False)
    current_amount = db.Column(db.Float, default=0.0)
    target_date    = db.Column(db.String(10), nullable=True)
    category       = db.Column(db.String(50), default='Emergency Fund')


class Budget(db.Model):
    __tablename__ = 'budgets'
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category      = db.Column(db.String(50), nullable=False)
    monthly_limit = db.Column(db.Float, nullable=False)
    month         = db.Column(db.String(7), nullable=False, default=lambda: datetime.now().strftime('%Y-%m'))


def init_db():
    """Initializes tables cleanly without hardcoded accounts."""
    with app.app_context():
        db.create_all()


# ───────────────────────────────────────────────────────────────
# 4. AUTH HELPERS & CONTEXT PROCESSOR
# ───────────────────────────────────────────────────────────────

def get_current_user():
    uid = session.get('user_id')
    if uid:
        try:
            return db.session.get(User, uid)
        except Exception:
            return None
    return None


def current_uid():
    return session.get('user_id')


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            session.clear()
            flash("Please sign in to access your dashboard.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.context_processor
def inject_globals():
    return {'current_user': get_current_user()}


# ───────────────────────────────────────────────────────────────
# 4.1 DATA VALIDATION & NUMERIC RESILIENCE
# ───────────────────────────────────────────────────────────────

def parse_currency(val_str, max_val=100_000_000.0):
    """
    Safely parses and validates financial amounts.
    Prevents NaN, Inf, zero/negative amounts, and huge overflow values.
    Returns value rounded to 2 decimal places to prevent floating-point drift.
    """
    if val_str is None:
        return None
    try:
        val = float(str(val_str).replace('$', '').replace(',', '').strip())
        if math.isnan(val) or math.isinf(val) or val <= 0 or val > max_val:
            return None
        return round(val, 2)
    except (TypeError, ValueError):
        return None


def parse_date(date_str):
    """
    Safely validates date format (YYYY-MM-DD), verifying calendar leap-year correctness.
    Falls back to current date if empty. Returns None if malformed or nonexistent day.
    """
    if not date_str or not str(date_str).strip():
        return datetime.now().strftime('%Y-%m-%d')
    try:
        dt = datetime.strptime(str(date_str).strip(), '%Y-%m-%d')
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError):
        return None


# ───────────────────────────────────────────────────────────────
# 5. CORE FINANCIAL CALCULATION ENGINE
# ───────────────────────────────────────────────────────────────

def get_overview_stats(expenses, incomes, bills=None, goals=None, budgets=None):
    uid = current_uid()
    if bills is None:
        bills = Bill.query.filter_by(user_id=uid).all() if uid else []
    if goals is None:
        goals = Goal.query.filter_by(user_id=uid).all() if uid else []
    if budgets is None:
        current_month = datetime.now().strftime('%Y-%m')
        budgets = Budget.query.filter_by(user_id=uid, month=current_month).all() if uid else []

    current_mo_str = datetime.now().strftime('%Y-%m')
    monthly_expenses = [e for e in expenses if e.date and e.date.startswith(current_mo_str)]
    monthly_incomes  = [i for i in incomes  if i.date and i.date.startswith(current_mo_str)]

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
    safe_net = max(0, net_balance - unpaid_bills_total)
    daily_safe = round(safe_net / days_left, 2) if days_left > 0 else 0.0

    # Financial Health Score (0 - 100)
    score = 50
    if month_income > 0:
        ratio = month_expense / month_income
        if ratio <= 0.5:
            score = 95
        elif ratio <= 0.7:
            score = 80
        elif ratio <= 0.85:
            score = 65
        elif ratio <= 1.0:
            score = 45
        else:
            score = max(10, int(50 - (ratio - 1) * 60))
    if net_balance > 0 and savings_rate >= 20:
        score = min(100, score + 5)
    if unpaid_bills_total > 0:
        score = max(10, score - 5)

    if score >= 85:
        health_grade, health_label, health_color_class, health_color_hex = 'A+', 'Excellent', 'emerald', '#10b981'
    elif score >= 70:
        health_grade, health_label, health_color_class, health_color_hex = 'B',  'Good',      'indigo',  '#6366f1'
    elif score >= 50:
        health_grade, health_label, health_color_class, health_color_hex = 'C',  'Fair',      'amber',   '#f59e0b'
    else:
        health_grade, health_label, health_color_class, health_color_hex = 'D',  'Needs Work','rose',    '#ef4444'

    # Category breakdown for 50/30/20 rule
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

    # 6-Month Trend Data
    now = datetime.now()
    months_labels, inc_data, exp_data = [], [], []
    for i in range(5, -1, -1):
        m, y = now.month - i, now.year
        while m <= 0:
            m += 12
            y -= 1
        months_labels.append(datetime(y, m, 1).strftime('%b'))
        mo = f"{y}-{m:02d}"
        inc_data.append(round(sum(x.amount for x in incomes if x.date and x.date.startswith(mo)), 2))
        exp_data.append(round(sum(x.amount for x in expenses if x.date and x.date.startswith(mo)), 2))

    # Dynamic friendly message
    if daily_safe >= 25.0:
        daily_safe_msg = "You are on track with your spending allowance today."
    elif daily_safe >= 10.0:
        daily_safe_msg = "Moderate allowance available for today."
    elif daily_safe > 0.0:
        daily_safe_msg = "Keep spending minimal today to maintain your monthly balance."
    else:
        daily_safe_msg = "Limit any non-essential spending today."

    last_expense = {
        'description': expenses[0].description,
        'amount': expenses[0].amount,
        'category': expenses[0].category or 'General',
        'payment_method': expenses[0].payment_method or 'Card'
    } if expenses else None

    # Budget limits usage
    budget_usage = []
    for b in budgets:
        spent = round(exp_cat_totals.get(b.category, 0.0), 2)
        limit = b.monthly_limit
        pct   = round((spent / limit) * 100, 1) if limit > 0 else 0.0
        if pct >= 100:
            status, status_label = 'over', 'Over Limit'
        elif pct >= 80:
            status, status_label = 'warning', f'{pct}% used'
        else:
            status, status_label = 'ok', f'{pct}% used'
        budget_usage.append({
            'id': b.id,
            'category': b.category,
            'spent': spent,
            'limit': round(limit, 2),
            'pct': min(100, pct),
            'status': status,
            'status_label': status_label
        })

    return {
        'total_income':      round(month_income, 2),
        'total_expense':     round(month_expense, 2),
        'total_spent':       round(month_expense, 2),  # template compatibility
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

        'income_chart':      {'labels': [c for c, _ in top_cats], 'data': [round(a, 2) for _, a in top_cats]},
        'comparison_chart':  {'labels': months_labels, 'income': inc_data, 'expenses': exp_data, 'data': [round(month_income, 2), round(month_expense, 2), round(max(0, net_balance), 2)]},
        'rule_50_30_20':     {
            'needs_pct':   min(100, max(0, needs_pct)),
            'wants_pct':   min(100, max(0, wants_pct)),
            'savings_pct': min(100, max(0, savings_pct)),
            'needs_amt':   round(needs_spent, 2),
            'wants_amt':   round(wants_spent, 2),
            'savings_amt': round(max(0, net_balance), 2)
        },
        'budget_limits':     budget_usage
    }


# ───────────────────────────────────────────────────────────────
# 6. AUTHENTICATION ROUTES
# ───────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if get_current_user():
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session.clear()
            session['user_id'] = user.id
            session.permanent = True
            flash(f"Welcome back, {user.name}!", "success")
            return redirect(url_for('dashboard'))

        flash("Invalid email or password.", "error")

    return render_template('login.html')


@app.route("/register", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def register():
    if get_current_user():
        return redirect(url_for('dashboard'))

    if request.method == "POST":
        name     = request.form.get('name', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return render_template('register.html')

        if '@' not in email or '.' not in email.split('@')[-1]:
            flash("Please enter a valid email address.", "error")
            return render_template('register.html')

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
            return render_template('register.html')

        if password != confirm:
            flash("Passwords do not match.", "error")
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

        session.clear()
        session['user_id'] = user.id
        session.permanent = True
        flash(f"Welcome to KashFlow, {name}!", "success")
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for('login'))


# ───────────────────────────────────────────────────────────────
# 7. DASHBOARD & OVERVIEW
# ───────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if get_current_user():
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route("/dashboard")
@login_required
def dashboard():
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc(), Expense.id.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc(), Income.id.desc()).all()
    bills    = Bill.query.filter_by(user_id=uid).order_by(Bill.due_date.asc()).all()
    goals    = Goal.query.filter_by(user_id=uid).all()

    current_month = datetime.now().strftime('%Y-%m')
    budgets = Budget.query.filter_by(user_id=uid, month=current_month).all()

    stats = get_overview_stats(expenses, incomes, bills, goals, budgets)

    # Activity feed (most recent 10 transactions)
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

    return render_template(
        "dashboard.html",
        stats=stats,
        bills=bills[:4],
        goals=goals[:3],
        recent_activities=recent_activities,
        expense_categories=EXPENSE_CATEGORIES,
        income_categories=INCOME_CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=today
    )


# ───────────────────────────────────────────────────────────────
# 8. EXPENSES (CRUD)
# ───────────────────────────────────────────────────────────────

@app.route("/expenses")
@login_required
def list_expenses():
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc(), Expense.id.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template(
        "expenses.html",
        expenses=expenses,
        stats=stats,
        categories=EXPENSE_CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=today
    )


@app.route("/add", methods=["POST"])
@login_required
def add_expense():
    description    = request.form.get("description", "").strip()
    amount_str     = request.form.get("amount", "").strip()
    category       = request.form.get("category", "General").strip()
    date           = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
    payment_method = request.form.get("payment_method", "Card").strip()
    notes          = request.form.get("notes", "").strip()

    if not description:
        flash("Expense description is required.", "error")
        return redirect(request.referrer or url_for("list_expenses"))

    amount = parse_currency(amount_str)
    if amount is None:
        flash("Please enter a valid positive amount.", "error")
        return redirect(request.referrer or url_for("list_expenses"))

    parsed_date = parse_date(date)
    if not parsed_date:
        flash("Please enter a valid date in YYYY-MM-DD format.", "error")
        return redirect(request.referrer or url_for("list_expenses"))

    db.session.add(Expense(
        user_id=current_uid(),
        description=description,
        amount=amount,
        category=category,
        date=parsed_date,
        payment_method=payment_method,
        notes=notes
    ))
    db.session.commit()
    flash(f"Expense '{description}' added.", "success")
    return redirect(request.referrer or url_for("list_expenses"))


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def edit_expense(id):
    expense = Expense.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    if request.method == "POST":
        description    = request.form.get("description", "").strip()
        amount_str     = request.form.get("amount", "").strip()
        category       = request.form.get("category", "General").strip()
        date           = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
        payment_method = request.form.get("payment_method", "Card").strip()
        notes          = request.form.get("notes", "").strip()

        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("edit_expense", id=id))

        amount = parse_currency(amount_str)
        if amount is None:
            flash("Amount must be a valid positive number.", "error")
            return redirect(url_for("edit_expense", id=id))

        parsed_date = parse_date(date)
        if not parsed_date:
            flash("Please enter a valid date in YYYY-MM-DD format.", "error")
            return redirect(url_for("edit_expense", id=id))

        expense.description    = description
        expense.amount         = amount
        expense.category       = category
        expense.date           = parsed_date
        expense.payment_method = payment_method
        expense.notes          = notes

        db.session.commit()
        flash(f"Expense '{description}' updated.", "success")
        return redirect(url_for("list_expenses"))

    return render_template("edit.html", expense=expense, categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS)


@app.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_expense(id):
    expense = Expense.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    desc = expense.description
    db.session.delete(expense)
    db.session.commit()
    flash(f"Expense '{desc}' deleted.", "success")
    return redirect(request.referrer or url_for("list_expenses"))


# ───────────────────────────────────────────────────────────────
# 9. INCOMES (CRUD)
# ───────────────────────────────────────────────────────────────

@app.route("/incomes")
@login_required
def list_incomes():
    uid = current_uid()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc(), Income.id.desc()).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template(
        "incomes.html",
        incomes=incomes,
        stats=stats,
        categories=INCOME_CATEGORIES,
        payment_methods=PAYMENT_METHODS,
        today=today
    )


@app.route("/add-income", methods=["POST"])
@login_required
def add_income():
    description = request.form.get("description", "").strip()
    amount_str  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "Salary").strip()
    date        = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
    source      = request.form.get("source", "Bank Transfer").strip()
    notes       = request.form.get("notes", "").strip()

    if not description:
        flash("Income description is required.", "error")
        return redirect(request.referrer or url_for("list_incomes"))

    amount = parse_currency(amount_str)
    if amount is None:
        flash("Please enter a valid positive amount.", "error")
        return redirect(request.referrer or url_for("list_incomes"))

    parsed_date = parse_date(date)
    if not parsed_date:
        flash("Please enter a valid date in YYYY-MM-DD format.", "error")
        return redirect(request.referrer or url_for("list_incomes"))

    db.session.add(Income(
        user_id=current_uid(),
        description=description,
        amount=amount,
        category=category,
        date=parsed_date,
        source=source,
        notes=notes
    ))
    db.session.commit()
    flash(f"Income '{description}' added.", "success")
    return redirect(request.referrer or url_for("list_incomes"))


@app.route("/edit-income/<int:id>", methods=["GET", "POST"])
@login_required
def edit_income(id):
    income = Income.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    if request.method == "POST":
        description = request.form.get("description", "").strip()
        amount_str  = request.form.get("amount", "").strip()
        category    = request.form.get("category", "Salary").strip()
        date        = request.form.get("date", datetime.now().strftime('%Y-%m-%d')).strip()
        source      = request.form.get("source", "Bank Transfer").strip()
        notes       = request.form.get("notes", "").strip()

        if not description:
            flash("Description is required.", "error")
            return redirect(url_for("edit_income", id=id))

        amount = parse_currency(amount_str)
        if amount is None:
            flash("Amount must be a valid positive number.", "error")
            return redirect(url_for("edit_income", id=id))

        parsed_date = parse_date(date)
        if not parsed_date:
            flash("Please enter a valid date in YYYY-MM-DD format.", "error")
            return redirect(url_for("edit_income", id=id))

        income.description = description
        income.amount      = amount
        income.category    = category
        income.date        = parsed_date
        income.source      = source
        income.notes       = notes

        db.session.commit()
        flash(f"Income '{description}' updated.", "success")
        return redirect(url_for("list_incomes"))

    return render_template("edit_income.html", income=income, categories=INCOME_CATEGORIES, payment_methods=PAYMENT_METHODS)


@app.route("/delete-income/<int:id>", methods=["POST"])
@login_required
def delete_income(id):
    income = Income.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    desc = income.description
    db.session.delete(income)
    db.session.commit()
    flash(f"Income '{desc}' deleted.", "success")
    return redirect(request.referrer or url_for("list_incomes"))


# ───────────────────────────────────────────────────────────────
# 10. BILLS (100% Free for Everyone)
# ───────────────────────────────────────────────────────────────

@app.route("/bills")
@login_required
def list_bills():
    uid = current_uid()
    bills    = Bill.query.filter_by(user_id=uid).order_by(Bill.due_date.asc()).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes, bills=bills)
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template("bills.html", bills=bills, stats=stats, categories=EXPENSE_CATEGORIES, today=today)


@app.route("/add-bill", methods=["POST"])
@login_required
def add_bill():
    name       = request.form.get("name", "").strip()
    amount_str = request.form.get("amount", "").strip()
    category   = request.form.get("category", "Utilities").strip()
    due_date   = request.form.get("due_date", datetime.now().strftime('%Y-%m-%d')).strip()
    recurring  = request.form.get("recurring", "Monthly").strip()

    if not name:
        flash("Bill name is required.", "error")
        return redirect(url_for("list_bills"))

    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
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
    flash(f"Bill '{name}' added.", "success")
    return redirect(url_for("list_bills"))


@app.route("/toggle-bill/<int:id>", methods=["POST"])
@login_required
def toggle_bill(id):
    bill = Bill.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    bill.is_paid = not bill.is_paid
    db.session.commit()
    status_label = "paid" if bill.is_paid else "unpaid"
    flash(f"Marked '{bill.name}' as {status_label}.", "success")
    return redirect(url_for("list_bills"))


@app.route("/delete-bill/<int:id>", methods=["POST"])
@login_required
def delete_bill(id):
    bill = Bill.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(bill)
    db.session.commit()
    flash("Bill removed.", "success")
    return redirect(url_for("list_bills"))


# ───────────────────────────────────────────────────────────────
# 11. GOALS (100% Free for Everyone)
# ───────────────────────────────────────────────────────────────

@app.route("/goals")
@login_required
def list_goals():
    uid = current_uid()
    goals    = Goal.query.filter_by(user_id=uid).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes, goals=goals)
    return render_template("goals.html", goals=goals, stats=stats)


@app.route("/add-goal", methods=["POST"])
@login_required
def add_goal():
    title       = request.form.get("title", "").strip()
    target_str  = request.form.get("target_amount", "").strip()
    curr_str    = request.form.get("current_amount", "0").strip()
    target_date = request.form.get("target_date", "").strip()
    category    = request.form.get("category", "Emergency Fund").strip()

    if not title:
        flash("Goal title is required.", "error")
        return redirect(url_for("list_goals"))

    try:
        target_amount  = float(target_str)
        current_amount = float(curr_str or 0)
        if target_amount <= 0 or current_amount < 0:
            raise ValueError
    except (TypeError, ValueError):
        flash("Please enter valid positive amounts.", "error")
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
    flash(f"Goal '{title}' created.", "success")
    return redirect(url_for("list_goals"))


@app.route("/update-goal/<int:id>", methods=["POST"])
@login_required
def update_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    curr_str = request.form.get("current_amount", "").strip()
    try:
        new_amount = float(curr_str)
        if new_amount < 0:
            raise ValueError
        goal.current_amount = new_amount
        db.session.commit()
        flash(f"Updated '{goal.title}' saved amount to ${new_amount:.2f}.", "success")
    except (TypeError, ValueError):
        flash("Please enter a valid amount.", "error")
    return redirect(url_for("list_goals"))


@app.route("/delete-goal/<int:id>", methods=["POST"])
@login_required
def delete_goal(id):
    goal = Goal.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(goal)
    db.session.commit()
    flash("Goal removed.", "success")
    return redirect(url_for("list_goals"))


# ───────────────────────────────────────────────────────────────
# 12. BUDGETS (100% Free for Everyone)
# ───────────────────────────────────────────────────────────────

@app.route("/budgets")
@login_required
def list_budgets():
    uid = current_uid()
    current_month = datetime.now().strftime('%Y-%m')
    budgets  = Budget.query.filter_by(user_id=uid, month=current_month).all()
    expenses = Expense.query.filter_by(user_id=uid).all()
    incomes  = Income.query.filter_by(user_id=uid).all()
    stats = get_overview_stats(expenses, incomes, budgets=budgets)
    return render_template("budgets.html", budgets=budgets, stats=stats, categories=EXPENSE_CATEGORIES)


@app.route("/add-budget", methods=["POST"])
@login_required
def add_budget():
    category  = request.form.get("category", "General").strip()
    limit_str = request.form.get("monthly_limit", "").strip()
    month     = datetime.now().strftime('%Y-%m')

    try:
        monthly_limit = float(limit_str)
        if monthly_limit <= 0:
            raise ValueError
    except (TypeError, ValueError):
        flash("Please enter a valid positive budget limit.", "error")
        return redirect(url_for("list_budgets"))

    existing = Budget.query.filter_by(user_id=current_uid(), category=category, month=month).first()
    if existing:
        existing.monthly_limit = monthly_limit
    else:
        db.session.add(Budget(
            user_id=current_uid(),
            category=category,
            monthly_limit=monthly_limit,
            month=month
        ))

    db.session.commit()
    flash(f"Monthly limit for '{category}' set to ${monthly_limit:.2f}.", "success")
    return redirect(url_for("list_budgets"))


@app.route("/delete-budget/<int:id>", methods=["POST"])
@login_required
def delete_budget(id):
    budget = Budget.query.filter_by(id=id, user_id=current_uid()).first_or_404()
    db.session.delete(budget)
    db.session.commit()
    flash("Budget limit removed.", "success")
    return redirect(url_for("list_budgets"))


# ───────────────────────────────────────────────────────────────
# 13. ACCOUNT SETTINGS & DATA PRIVACY
# ───────────────────────────────────────────────────────────────

@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    user = get_current_user()
    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "update_profile":
            name  = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            if not name or not email:
                flash("Name and email are required.", "error")
            elif '@' not in email or '.' not in email.split('@')[-1]:
                flash("Please enter a valid email address.", "error")
            else:
                existing = User.query.filter_by(email=email).first()
                if existing and existing.id != user.id:
                    flash("Email address is already in use.", "error")
                else:
                    user.name = name
                    user.email = email
                    db.session.commit()
                    flash("Profile updated successfully.", "success")

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
                flash("Password updated successfully.", "success")

        elif action == "delete_account":
            password_confirm = request.form.get("password_confirm", "")
            if not check_password_hash(user.password_hash, password_confirm):
                flash("Incorrect password. Account deletion aborted.", "error")
                return redirect(url_for("settings"))

            uid = user.id
            Expense.query.filter_by(user_id=uid).delete()
            Income.query.filter_by(user_id=uid).delete()
            Bill.query.filter_by(user_id=uid).delete()
            Goal.query.filter_by(user_id=uid).delete()
            Budget.query.filter_by(user_id=uid).delete()
            db.session.delete(user)
            db.session.commit()

            session.clear()
            flash("Your account and all associated data have been permanently deleted.", "success")
            return redirect(url_for("register"))

        return redirect(url_for("settings"))

    return render_template("settings.html", user=user)


# ───────────────────────────────────────────────────────────────
# 14. DATA EXPORT & LEGAL
# ───────────────────────────────────────────────────────────────

@app.route("/export-csv")
@login_required
def export_csv():
    uid = current_uid()
    expenses = Expense.query.filter_by(user_id=uid).order_by(Expense.date.desc()).all()
    incomes  = Income.query.filter_by(user_id=uid).order_by(Income.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Type', 'Date', 'Description', 'Category', 'Amount', 'Payment Method / Source', 'Notes'])

    for i in incomes:
        writer.writerow(['Income', i.date, i.description, i.category, f"{i.amount:.2f}", i.source or '', i.notes or ''])
    for e in expenses:
        writer.writerow(['Expense', e.date, e.description, e.category, f"{e.amount:.2f}", e.payment_method or '', e.notes or ''])

    output.seek(0)
    filename = f"kashflow_export_{datetime.now().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename={filename}'}
    )


@app.route("/import-csv", methods=["POST"])
@login_required
def import_csv():
    file = request.files.get("csv_file")
    if not file or not file.filename:
        flash("Please select a CSV file to restore.", "error")
        return redirect(url_for("settings"))

    if not file.filename.lower().endswith(".csv"):
        flash("Only standard .csv files are supported for import.", "error")
        return redirect(url_for("settings"))

    try:
        content = file.stream.read().decode("utf-8-sig")
        stream = io.StringIO(content, newline=None)
        reader = csv.reader(stream)
        header = next(reader, None)

        imported_count = 0
        uid = current_uid()

        for row in reader:
            if not row or len(row) < 5:
                continue
            rec_type = row[0].strip().capitalize()
            date = parse_date(row[1]) or datetime.now().strftime('%Y-%m-%d')
            description = row[2].strip()
            category = row[3].strip()
            amount = parse_currency(row[4])
            method_source = row[5].strip() if len(row) > 5 else ''
            notes = row[6].strip() if len(row) > 6 else ''

            if not description or amount is None:
                continue

            if rec_type == 'Income':
                exists = Income.query.filter_by(
                    user_id=uid, date=date, description=description, amount=amount
                ).first()
                if not exists:
                    db.session.add(Income(
                        user_id=uid, description=description, amount=amount,
                        category=category or 'Other', date=date,
                        source=method_source or 'Bank Transfer', notes=notes
                    ))
                    imported_count += 1
            else:
                exists = Expense.query.filter_by(
                    user_id=uid, date=date, description=description, amount=amount
                ).first()
                if not exists:
                    db.session.add(Expense(
                        user_id=uid, description=description, amount=amount,
                        category=category or 'General', date=date,
                        payment_method=method_source or 'Card', notes=notes
                    ))
                    imported_count += 1

        db.session.commit()
        flash(f"Successfully restored {imported_count} financial transactions from CSV.", "success")
    except Exception as e:
        flash(f"Failed to process CSV file: {str(e)}", "error")

    return redirect(url_for("settings"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/delete-account-request", methods=["GET", "POST"])
def delete_account_request():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email or "@" not in email:
            flash("Please enter a valid email address.", "error")
        else:
            flash(f"Account deletion request received for {email}. If an account exists, all records will be purged within 48 hours.", "success")
        return redirect(url_for("delete_account_request"))
    return render_template("delete_account_request.html")


# ───────────────────────────────────────────────────────────────
# 15. INITIALIZATION
# ───────────────────────────────────────────────────────────────

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
