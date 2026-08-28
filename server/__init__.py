"""Make `from app.*` work when Bothost runs `python -m server.app.main` from /app."""
from __future__ import annotations

import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent
_s = str(_SERVER_DIR)
if _s not in sys.path:
    sys.path.insert(0, _s)
