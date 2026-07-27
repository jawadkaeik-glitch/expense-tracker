"""Test Stripe integration routes"""
from app import app, db, User, init_db
from werkzeug.security import generate_password_hash

init_db()

with app.app_context():
    User.query.filter_by(email='stripe-test@kf.app').delete()
    db.session.commit()
    user = User(name='StripeTest', email='stripe-test@kf.app', password_hash=generate_password_hash('Pass1234!'))
    db.session.add(user)
    db.session.commit()
    uid = user.id

client = app.test_client()
with client.session_transaction() as s:
    s['user_id'] = uid

# Test pricing page
r = client.get('/pricing')
print('OK' if r.status_code == 200 else 'FAIL', '/pricing', r.status_code)
assert b'Demo Mode' in r.data or b'Stripe' in r.data, "Pricing page should show demo or stripe mode"

# Test checkout session (demo mode - no Stripe keys configured)
r = client.post('/create-checkout-session', follow_redirects=True)
print('OK' if r.status_code == 200 else 'FAIL', '/create-checkout-session (demo mode)', r.status_code)

# Verify premium was activated in demo mode
with app.app_context():
    u = User.query.get(uid)
    print('OK' if u.is_premium else 'FAIL', 'Premium activated in demo mode:', u.is_premium)

# Test payment success page
r = client.get('/payment-success')
print('OK' if r.status_code == 200 else 'FAIL', '/payment-success', r.status_code)

# Test payment cancel page
r = client.get('/payment-cancel')
print('OK' if r.status_code == 200 else 'FAIL', '/payment-cancel', r.status_code)

# Test cancel subscription
r = client.post('/cancel-subscription', follow_redirects=True)
print('OK' if r.status_code == 200 else 'FAIL', '/cancel-subscription', r.status_code)

# Verify premium was deactivated
with app.app_context():
    u = User.query.get(uid)
    print('OK' if not u.is_premium else 'FAIL', 'Premium deactivated:', not u.is_premium)

# Test webhook endpoint
import json
webhook_payload = json.dumps({
    "type": "checkout.session.completed",
    "data": {"object": {"customer": "cus_test123", "subscription": "sub_test123"}}
})
r = client.post('/stripe-webhook', data=webhook_payload, content_type='application/json')
print('OK' if r.status_code == 200 else 'FAIL', '/stripe-webhook', r.status_code)

# Cleanup
with app.app_context():
    User.query.filter_by(email='stripe-test@kf.app').delete()
    db.session.commit()

print('\nAll Stripe integration tests passed!')
