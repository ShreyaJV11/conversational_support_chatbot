import requests
import json

BASE = 'http://127.0.0.1:8000'

endpoints = [
    '/',
    '/health',
    '/api/chat/initial-message',
]

print('Testing GET endpoints:')
for ep in endpoints:
    url = BASE + ep
    try:
        r = requests.get(url, timeout=5)
        try:
            data = r.json()
        except Exception:
            data = r.text
        print(f'{url} ->', r.status_code, data)
    except Exception as e:
        print(f'{url} -> ERROR:', e)

print('\nTesting POST /api/chat:')
url = BASE + '/api/chat'
payload = {
    'user_question': 'Hello, is the server working?',
    'user_info': {'name': 'Tester', 'email': 'test@example.com'},
    'user_session_id': 'test_session'
}
try:
    r = requests.post(url, json=payload, timeout=10)
    try:
        data = r.json()
    except Exception:
        data = r.text
    print(f'{url} ->', r.status_code, data)
except Exception as e:
    print(f'{url} -> ERROR:', e)

print('\nDone.')
