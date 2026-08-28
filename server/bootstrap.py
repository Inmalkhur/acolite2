from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def ensure_runtime_deps() -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import pydantic_settings  # noqa: F401
        return
    except ImportError:
        pass

    here = Path(__file__).resolve().parent
    candidates = [here.parent / "requirements.txt", here / "requirements.txt"]
    req = next((p for p in candidates if p.is_file()), None)
    if req is None:
        print("requirements.txt not found; cannot install FastAPI/uvicorn", file=sys.stderr)
        return
    print(f"Installing Python deps from {req} ...", flush=True)
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "-r", str(req), "-q"],
    )
