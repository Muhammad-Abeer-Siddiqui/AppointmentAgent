import sys
import os

# Add the specific path
sys.path.insert(0, r'D:\Coding\appointment scheduling agent\backend')

# Change to that directory
os.chdir(r'D:\Coding\appointment scheduling agent\backend')

# Now try the import
from app.main import app
print("Main import OK")
print(f"App title: {app.title}")