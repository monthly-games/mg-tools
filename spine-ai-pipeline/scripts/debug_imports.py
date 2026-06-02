import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    from scripts.lib.lama_client import LamaClient
    print("Success: from scripts.lib.lama_client")
except ImportError as e:
    print(f"Fail scripts.lib: {e}")

try:
    from lib.lama_client import LamaClient
    print("Success: from lib.lama_client")
except ImportError as e:
    print(f"Fail lib: {e}")
