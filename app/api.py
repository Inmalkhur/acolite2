from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.holder import BotHolder
from app.models import RootConfig, NlpResult
from app.settings import settings
from app.store import Store


class GlossarySync(BaseModel):
    files: dict[str, str]


def create_app(store: Store, holder: BotHolder, dispatcher: Any | None = None) -> FastAPI:
    app = FastAPI(title="Chat admin sync")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def check(
        secret: str | None,
        authorization: str | None = None,
        query_secret: str | None = None,
    ) -> None:
        token = (secret or query_secret or "").strip()
        if not token and authorization:
            raw = authorization.strip()
            if raw.lower().startswith("bearer "):
                token = raw[7:].strip()
        if token != settings.local_sync_secret:
            raise HTTPException(401, "bad secret")

    def admin_page() -> HTMLResponse:
        page = Path(__file__).parent / "templates" / "admin.html"
        return HTMLResponse(page.read_text(encoding="utf-8"))

    @app.get("/", response_class=HTMLResponse)
    async def ui() -> HTMLResponse:
        return admin_page()

    @app.get("/admin", response_class=HTMLResponse)
    @app.get("/gui", response_class=HTMLResponse)
    async def ui_alias() -> HTMLResponse:
        return admin_page()

    @app.get("/health")
    async def health() -> dict:
        return {
            "ok": True,
            "local_connected": store.local_connected,
            "bot": bool(store.bot_username),
            "bot_username": store.bot_username or None,
            "telegram_mode": store.telegram_mode,
            "chats": len(store.chats),
            "chat_ids": list(store.chats.keys()),
        }

    @app.post("/telegram/webhook")
    async def telegram_webhook(request: Request) -> dict:
        if holder.bot is None or dispatcher is None:
            raise HTTPException(503, "bot is not ready")
        from aiogram.types import Update

        data = await request.json()
        update = Update.model_validate(data, context={"bot": holder.bot})
        await dispatcher.feed_update(holder.bot, update)
        return {"ok": True}

    @app.get("/api/config")
    async def get_config(
        x_sync_secret: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        secret: str | None = Query(default=None),
    ) -> dict:
        check(x_sync_secret, authorization, secret)
        return store.root_config.model_dump()

    @app.put("/api/config")
    async def put_config(
        cfg: RootConfig,
        x_sync_secret: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        secret: str | None = Query(default=None),
    ) -> dict:
        check(x_sync_secret, authorization, secret)
        await store.replace_config(cfg)
        return {"ok": True}

    @app.post("/api/glossary")
    async def put_glossary(
        body: GlossarySync,
        x_sync_secret: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        secret: str | None = Query(default=None),
    ) -> dict:
        check(x_sync_secret, authorization, secret)
        store.glossary = {}
        for path, content in body.files.items():
            title = path.rsplit("/", 1)[-1].removesuffix(".md")
            lines = content.strip().splitlines()
            first = lines[0] if lines else title
            if first.startswith("#"):
                first = first.lstrip("# ").strip()
            store.glossary[first or title] = content
        await store.persist()
        return {"ok": True, "terms": list(store.glossary.keys())}

    @app.post("/api/nlp/result")
    async def nlp_result(
        result: NlpResult,
        x_sync_secret: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        secret: str | None = Query(default=None),
    ) -> dict:
        check(x_sync_secret, authorization, secret)
        store.nlp_queue = [j for j in store.nlp_queue if j.id != result.id]
        await store.persist()
        if holder.bot and result.ok:
            await apply_nlp(store, holder.bot, result)
        await store.broadcast({"type": "nlp_done", "id": result.id})
        return {"ok": True}

    @app.post("/api/md/ack")
    async def md_ack(
        body: dict,
        x_sync_secret: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        secret: str | None = Query(default=None),
    ) -> dict:
        check(x_sync_secret, authorization, secret)
        paths = set(body.get("paths") or [])
        store.md_outbox = [d for d in store.md_outbox if d.path not in paths]
        return {"ok": True}

    @app.get("/api/flush-logs")
    async def flush_logs(
        x_sync_secret: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
        secret: str | None = Query(default=None),
    ) -> dict:
        check(x_sync_secret, authorization, secret)
        text, start, end = store.drain_logs()
        day = datetime.now(timezone.utc).date().isoformat()
        return {
            "filename": f"logs/chat-{day}.md",
            "content": text,
            "from_ts": start,
            "to_ts": end,
        }

    @app.websocket("/ws")
    async def ws(websocket: WebSocket) -> None:
        secret = websocket.query_params.get("secret")
        if secret != settings.local_sync_secret:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        store.ws_clients.add(queue)
        store.local_connected = True
        await websocket.send_text(json.dumps(store.snapshot(), ensure_ascii=False, default=str))

        async def reader() -> None:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                if msg.get("type") == "config":
                    await store.replace_config(RootConfig.model_validate(msg["config"]))
                elif msg.get("type") == "flush_logs":
                    text, start, end = store.drain_logs()
                    day = datetime.now(timezone.utc).date().isoformat()
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "logs_dump",
                                "filename": f"logs/chat-{day}.md",
                                "content": text,
                                "from_ts": start,
                                "to_ts": end,
                            },
                            ensure_ascii=False,
                        )
                    )

        async def writer() -> None:
            while True:
                item = await queue.get()
                await websocket.send_text(json.dumps(item, ensure_ascii=False, default=str))

        try:
            await asyncio.gather(reader(), writer())
        except WebSocketDisconnect:
            pass
        finally:
            store.ws_clients.discard(queue)
            store.local_connected = bool(store.ws_clients)

    return app


async def apply_nlp(store: Store, bot: Any, result: NlpResult) -> None:
    from app.bot import complete_questionnaire, _qkey

    p = result.payload
    if result.kind == "questionnaire" and p.get("is_questionnaire"):
        key = _qkey(int(p.get("chat_id") or 0), p.get("user_id"))
        pending = store.pending_questionnaires.get(key)
        if pending and not pending.get("done"):
            pending.setdefault("fragments", []).append(p.get("text") or "")
            await complete_questionnaire(store, key)
    elif result.kind == "term":
        answer = p.get("answer")
        chat_id = p.get("chat_id")
        cfg = store.chat(int(chat_id)) if chat_id else None
        missing = p.get("missing") or (cfg.missing_term_reply if cfg else "В базе терминов этого нет.")
        if chat_id and answer:
            await bot.send_message(chat_id, answer, reply_to_message_id=p.get("reply_to"))
        elif chat_id:
            await bot.send_message(chat_id, missing, reply_to_message_id=p.get("reply_to"))
    elif result.kind == "schedule" and p.get("when") and p.get("title"):
        store.events.append(
            {
                "id": result.id,
                "title": p["title"],
                "when": float(p["when"]),
                "author": p.get("user_id"),
                "chat_id": p.get("chat_id"),
                "reminders_sent": [],
            }
        )
        await store.persist()
        if p.get("chat_id"):
            await bot.send_message(p["chat_id"], f"Активность «{p['title']}» сохранена.")
    elif result.kind == "profanity" and p.get("is_profanity"):
        try:
            await bot.delete_message(p["chat_id"], p["message_id"])
        except Exception:
            pass
