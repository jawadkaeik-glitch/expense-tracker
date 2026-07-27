from app import app, init_db, User, db
from werkzeug.security import generate_password_hash
init_db()

with app.app_context():
    User.query.filter_by(email='pgtest@kf.app').delete()
    db.session.commit()
    user = User(name='Test', email='pgtest@kf.app', password_hash=generate_password_hash('Pass1234!'), is_premium=True)
    db.session.add(user)
    db.session.commit()


client = app.test_client()
client.post('/login', data={'email': 'pgtest@kf.app', 'password': 'Pass1234!'})

pages = ['/dashboard', '/expenses', '/incomes', '/bills', '/goals', '/budgets', '/pricing', '/settings', '/privacy', '/terms']


all_ok = True
for p in pages:
    r = client.get(p)
    status = 'OK' if r.status_code == 200 else 'FAIL'
    if r.status_code != 200:
        all_ok = False
        # Print first error
        body = r.get_data(as_text=True)
        err_line = [l for l in body.split('\n') if 'UndefinedError' in l or 'AttributeError' in l]
        print(status, p, r.status_code, err_line[:1])
    else:
        print(status, p)

with app.app_context():
    User.query.filter_by(email='pgtest@kf.app').delete()
    db.session.commit()

if all_ok:
    print('\nAll pages render correctly!')
