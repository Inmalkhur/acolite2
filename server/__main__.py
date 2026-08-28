"""python -m server from repo root, or python -m app.main from server/."""
from __future__ import annotations

import sys
from pathlib import Path

_SERVER = Path(__file__).resolve().parent
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))

from app.main import main

if __name__ == "__main__":
    main()
