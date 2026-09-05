import sys
sys.path.insert(0, r'D:\Coding\appointment scheduling agent\backend')
import os
app_dir = r'D:\Coding\appointment scheduling agent\backend\app'
print("app dir exists:", os.path.exists(app_dir))
print("__init__.py exists:", os.path.exists(os.path.join(app_dir, '__init__.py')))

# Try to import app.main
try:
    from app.main import app
    print("Main import OK")
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")
except Exception as e:
    print(f"Other error: {type(e).__name__}: {e}")