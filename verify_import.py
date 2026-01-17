
import sys
import os
from pathlib import Path

# Add project root
root = Path(os.getcwd())
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

print(f"Checking imports in apps.api.src.main...")
try:
    from apps.api.src.main import app
    print("SUCCESS: app imported correctly")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
    exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    exit(1)
