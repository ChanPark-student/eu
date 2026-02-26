import urllib.request
import json
import urllib.error

data = json.dumps({'email': 'testuser@eu.com', 'password': 'testpassword'}).encode('utf-8')
req = urllib.request.Request('http://127.0.0.1:8000/api/auth/register', data=data, headers={'Content-Type': 'application/json'})

try:
    with urllib.request.urlopen(req) as response:
        print("Success:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code)
    print(e.read().decode('utf-8'))
except Exception as e:
    print('Error:', e)
