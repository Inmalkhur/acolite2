# Package `app` lives at repo root so Bothost `python -m server.app.main` can `from app.api`.
from __future__ import annotations

from app.bootstrap import ensure_runtime_deps

ensure_runtime_deps()
