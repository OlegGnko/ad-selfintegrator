import sys
import os

# Add project root to path so backend.* imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.main import app  # noqa: F401 — Vercel needs this symbol named `app`
