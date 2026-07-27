"""Vercel serverless entry point for the Orbit-Shield API.

Vercel's Python runtime discovers files under `api/` and serves the ASGI
application exported as `app`. The application itself is unchanged — this
module only makes `src/` importable, since the function executes with this
directory rather than the backend root on `sys.path`.

Only read paths run here. Conjunction screening, classical Pc and the
XGBoost layer run in the scheduled GitHub Actions pipeline and write their
results to the database; this process just serves them.
"""

from __future__ import annotations

import sys
from pathlib import Path

# backend/api/index.py -> backend/
BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from src.main import app  # noqa: E402

__all__ = ["app"]
