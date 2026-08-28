"""Start the bot from the repository root: python run.py"""
from __future__ import annotations

import sys
from pathlib import Path

_SERVER = Path(__file__).resolve().parent / "server"
sys.path.insert(0, str(_SERVER))

from app.main import main

if __name__ == "__main__":
    main()
