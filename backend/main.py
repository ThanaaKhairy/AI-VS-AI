
from flask import Flask
import types
import sys

app = Flask(__name__)
app.secret_key = 'your-secret-key'

flask_app = types.ModuleType('flask_app')
flask_app.app = app
sys.modules['flask_app'] = flask_app

from login_register_apis import *
print("Login Register APIs loaded")

try:
    from admin_apis import *
    print("Admin APIs loaded")
except Exception as e:
    print("Error importing admin_apis:", e)

try:
    from detection_apis import *
    print("Detection APIs loaded")
except Exception as e:
    print("Error importing detection_apis:", e)

try:
    from generation_apis import *
    print("Generation APIs loaded")
except Exception as e:
    print("Error importing generation_apis:", e)

print("Available Routes:")
for rule in app.url_map.iter_rules():
    print(rule)

if __name__ == '__main__':
    app.run(debug=False)
