#!/usr/bin/env python3
"""Run register_odoo.py with API key from credentials file."""
import os
import subprocess
import sys

with open(os.path.expanduser("~/.hermes/credentials.env")) as f:
    content = f.read()

api_key = ""
for line in content.splitlines():
    if line.startswith("TRIBBE_ODOO_API_KEY=***                api_key = line.split("=", 1)[1].strip().strip('"\'')
                break

os.environ["TRIBBE_ODOO_API_KEY"] = api_key
print(f"API Key: {len(api_key)} chars")

result = subprocess.run(
    [sys.executable, "/home/ubuntu/repos/langextract-cuidum/scripts/register_odoo.py"],
    env=os.environ,
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr[:500])
print(f"Exit: {result.returncode}")
