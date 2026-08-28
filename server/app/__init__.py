# Telegram admin bot + sync API
from __future__ import annotations

import sys
from pathlib import Path

_SERVER_DIR = Path(__file__).resolve().parent.parent
_s = str(_SERVER_DIR)
if _s not in sys.path:
    sys.path.insert(0, _s)
