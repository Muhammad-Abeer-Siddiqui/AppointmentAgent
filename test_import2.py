#!/usr/bin/env python3
import sys
import os

# Add backend to path
backend_path = r'D:\Coding\appointment scheduling agent\backend'
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Check if app directory has __init__.py
app_dir = os.path.join(backend_path, 'app')
print(f"app_dir: {app_dir}")
print(f"__init__.py exists: {os.path.exists(os.path.join(app_dir, '__init__.py'))}")

# List all Python files in app
if os.path.exists(app_dir):
    for f in sorted(os.listdir(app_dir)):
        if f.endswith('.py'):
            print(f"  Python file: {f}")

# Try importing app.main
try:
    from app.main import app
    print("Main import OK")
except ModuleNotFoundError as e:
    print(f"ModuleNotFoundError: {e}")
    # Try to find what's available
    import importlib.util
    spec = importlib.util.find_spec('app')
    print(f"app spec: {spec}")
except Exception as e:
    print(f"Other error: {type(e).__name__}: {e}")