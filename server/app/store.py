from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.models import BotConfig, MdDocument, NlpJob


class Store:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self.config = BotConfig()
        self.pending_questionnaires: dict[int, dict[str, Any]] = {}
        self.activity: dict[int, dict[str, Any]] = {}
        self.burst: dict[int, list[tuple[float, str]]] = defaultdict(list)
        self.nlp_queue: list[NlpJob] = []
        self.md_outbox: list[MdDocument] = []
        self.log_buffer: list[str] = []
        self.log_since: float = time.time()
        self.glossary: dict[str, str] = {}
        self.events: list[dict[str, Any]] = []
        self.last_inactive_ping: float = 0.0
        self.bot_username: str = ""
        self.local_connected: bool = False
        self.ws_clients: set[asyncio.Queue] = set()
        self._load()

    def _path(self, name: str) -> Path:
        return self.root / name

    def _load(self) -> None:
        cfg = self._path("config.json")
        if cfg.exists():
            self.config = BotConfig.model_validate_json(cfg.read_text(encoding="utf-8"))
        for name, attr in (
            ("pending.json", "pending_questionnaires"),
            ("activity.json", "activity"),
            ("events.json", "events"),
            ("glossary.json", "glossary"),
        ):
            p = self._path(name)
            if p.exists():
                setattr(self, attr, json.loads(p.read_text(encoding="utf-8")))
        q = self._path("nlp_queue.json")
        if q.exists():
            self.nlp_queue = [NlpJob.model_validate(x) for x in json.loads(q.read_text())]
        meta = self._path("meta.json")
        if meta.exists():
            data = json.loads(meta.read_text())
            self.last_inactive_ping = data.get("last_inactive_ping", 0.0)

    async def persist(self) -> None:
        async with self._lock:
            self._path("config.json").write_text(
                self.config.model_dump_json(indent=2), encoding="utf-8"
            )
            self._path("pending.json").write_text(
                json.dumps(self.pending_questionnaires, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._path("activity.json").write_text(
                json.dumps(self.activity, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._path("events.json").write_text(
                json.dumps(self.events, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._path("glossary.json").write_text(
                json.dumps(self.glossary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self._path("nlp_queue.json").write_text(
                json.dumps([j.model_dump() for j in self.nlp_queue], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._path("meta.json").write_text(
                json.dumps({"last_inactive_ping": self.last_inactive_ping}), encoding="utf-8"
            )

    async def enqueue_nlp(self, job: NlpJob) -> None:
        self.nlp_queue.append(job)
        await self.persist()
        await self.broadcast({"type": "nlp_job", "job": job.model_dump()})

    async def append_md(self, path: str, content: str) -> None:
        doc = MdDocument(path=path, content=content, updated_at=time.time())
        self.md_outbox.append(doc)
        await self.broadcast({"type": "md", "doc": doc.model_dump()})

    async def log_line(self, line: str) -> None:
        if not self.config.logging_enabled:
            return
        self.log_buffer.append(line)
        await self.broadcast({"type": "log", "line": line})

    def drain_logs(self) -> tuple[str, float, float]:
        text = "\n".join(self.log_buffer) + ("\n" if self.log_buffer else "")
        start, end = self.log_since, time.time()
        self.log_buffer = []
        self.log_since = end
        return text, start, end

    def snapshot(self) -> dict[str, Any]:
        return {
            "type": "snapshot",
            "config": self.config.model_dump(),
            "nlp_queue": [j.model_dump() for j in self.nlp_queue],
            "md_outbox": [d.model_dump() for d in self.md_outbox],
            "logs": self.log_buffer[-200:],
            "events": self.events[-100:],
            "glossary_terms": sorted(self.glossary.keys()),
            "pending_questionnaires": self.pending_questionnaires,
            "local_connected": self.local_connected,
            "bot_username": self.bot_username,
        }

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[asyncio.Queue] = []
        for q in self.ws_clients:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.ws_clients.discard(q)


store: Store | None = None


def get_store() -> Store:
    assert store is not None
    return store
