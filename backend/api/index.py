"""
Namma Civic — Vercel Serverless Entry Point
Exports the FastAPI ASGI app for Vercel's Python runtime.
"""
from __future__ import annotations

import os
import sys

# Ensure backend root is on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_parent_dir = os.path.dirname(_current_dir)

for _path in [_parent_dir, _current_dir, "/var/task", "/var/task/backend"]:
    if os.path.exists(_path) and _path not in sys.path:
        sys.path.insert(0, _path)

from app.main import app

# Top-level ASGI entrypoints recognized by Vercel Python runtime
application = app
handler = app
