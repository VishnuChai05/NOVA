#!/usr/bin/env python
"""Test Apify token specifically."""

import os
from pathlib import Path

print("Current working directory:", os.getcwd())
print(".env file exists:", Path(".env").exists())
print(".env absolute path:", Path(".env").resolve())

if Path(".env").exists():
    print("\nReading .env file content:")
    with open(".env") as f:
        for line in f:
            if "APIFY" in line:
                print(f"  {line.strip()}")

# Now test settings loading
import sys
sys.path.insert(0, "backend")

# Reload settings to force re-reading .env
from importlib import reload
import app.core.settings as settings_module
reload(settings_module)
from app.core.settings import settings

print("\nSettings loaded:")
print(f"  APIFY_API_TOKEN: {settings.apify_api_token}")
print(f"  Has token: {bool(settings.apify_api_token)}")
