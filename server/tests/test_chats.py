import asyncio
from pathlib import Path
from types import SimpleNamespace

from aiogram.enums import ChatType

from app.bot import chat_type_str
from app.store import Store, _migrate_config


def test_chat_type_str_accepts_enum_and_plain_str() -> None:
    assert chat_type_str(SimpleNamespace(type="supergroup")) == "supergroup"
    assert chat_type_str(SimpleNamespace(type=ChatType.SUPERGROUP)) == "supergroup"
    assert chat_type_str("group") == "group"
    assert chat_type_str(ChatType.GROUP) == "group"


def test_migrate_legacy_config() -> None:
    raw = {
        "chat_id": -100123,
        "welcome_text": "hi",
        "ollama_model": "llama3.2",
        "log_flush_interval_minutes": 30,
    }
    cfg = _migrate_config(raw)
    assert "-100123" in cfg.chats
    assert cfg.chats["-100123"].welcome_text == "hi"
    assert cfg.log_flush_interval_minutes == 30


def test_ensure_chat_creates_and_updates(tmp_path: Path) -> None:
    async def _run() -> None:
        store = Store(tmp_path)
        a = await store.ensure_chat(-1001, title="Alpha")
        b = await store.ensure_chat(-1001, title="Alpha 2")
        assert a.chat_id == b.chat_id == -1001
        assert store.chat(-1001).title == "Alpha 2"
        assert len(store.chats) == 1
        await store.ensure_chat(-1002, title="Beta")
        assert set(store.chats) == {"-1001", "-1002"}

    asyncio.run(_run())
