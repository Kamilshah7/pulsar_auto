"""
Credentials live outside source code.

Resolution order for get_secret(name):
  1. the environment variable of the same name
  2. local_secrets.json next to this file (excluded from zip_project.py -- never ship it)

Previously the Groq API key was a string literal in pipeline.py and three other scripts,
and the portal password was printed into the GUI log, so every zip_project.py archive
carried both. Keep them here instead.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
SECRETS_FILE = os.path.join(_HERE, "local_secrets.json")


def get_secret(name, required=True):
    value = os.environ.get(name)
    if not value and os.path.exists(SECRETS_FILE):
        with open(SECRETS_FILE, encoding="utf-8") as f:
            value = json.load(f).get(name)
    if not value and required:
        raise RuntimeError(
            f"{name} is not configured. Set the {name} environment variable or add it to {SECRETS_FILE}."
        )
    return value
