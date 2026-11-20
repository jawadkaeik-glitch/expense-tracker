"""
Integration test script testing rendering of all KashFlow v2 pages.
"""

from app import app, init_db, User, db
from werkzeug.security import generate_password_hash

app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF token validation during testing client
init_db()

with app.app_context():
    User.query.filter_by(email='pgtest@kf.app').delete()
    db.session.commit()
    user = User(name='Test User', email='pgtest@kf.app', password_hash=generate_password_hash('Pass1234!'))
    db.session.add(user)
    db.session.commit()

client = app.test_client()
login_res = client.post('/login', data={'email': 'pgtest@kf.app', 'password': 'Pass1234!'})
assert login_res.status_code == 302, f"Login failed with status {login_res.status_code}"

pages = [
    '/dashboard',
    '/expenses',
    '/incomes',
    '/bills',
    '/goals',
    '/budgets',
    '/settings',
    '/privacy',
    '/terms',
    '/delete-account-request'
]

all_ok = True
for p in pages:
    r = client.get(p)
    status = 'OK' if r.status_code == 200 else 'FAIL'
    if r.status_code != 200:
        all_ok = False
        body = r.get_data(as_text=True)
        err_line = [l for l in body.split('\n') if 'Error' in l or 'Exception' in l]
        print(status, p, r.status_code, err_line[:1])
    else:
        print(status, p)

with app.app_context():
    User.query.filter_by(email='pgtest@kf.app').delete()
    db.session.commit()

if all_ok:
    print('\nAll pages render correctly!')
else:
    exit(1)
