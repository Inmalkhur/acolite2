from fastapi.testclient import TestClient

from app.api import create_app
from app.holder import BotHolder
from app.models import ChatConfig, RootConfig
from app.store import Store


def test_root_is_bot_api_not_gui(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "bot"
    assert "Админ закрытого чата" not in r.text
    assert c.get("/gui").status_code == 404
    assert c.get("/admin").status_code == 404


def test_health(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    r = c.get("/health")
    assert r.json()["ok"] is True
    assert r.json()["chats"] == 0
    assert r.json()["telegram_mode"] == "off"


def test_config_auth(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    assert c.get("/api/config").status_code == 401
    r = c.get("/api/config", headers={"X-Sync-Secret": "change-me"})
    assert r.status_code == 200
    assert "chats" in r.json()
    assert c.get("/api/config?secret=change-me").status_code == 200
    assert c.get("/telegram/webhook").status_code == 200
    assert c.get("/telegram/webhook").json()["ok"] is True
    assert c.get("/favicon.ico").status_code == 204


def test_health_lists_bound_chats(tmp_path) -> None:
    import asyncio

    store = Store(tmp_path)

    async def _add() -> None:
        await store.ensure_chat(-5456516071, title="Закрытый")

    asyncio.run(_add())
    app = create_app(store, BotHolder())
    c = TestClient(app)
    body = c.get("/health").json()
    assert body["chats"] == 1
    assert "-5456516071" in body["chat_ids"]
    assert body["chat_list"][0]["id"] == -5456516071
    assert body["chat_list"][0]["title"] == "Закрытый"
    cfg = c.get("/api/config?secret=change-me").json()
    assert cfg["chats"]["-5456516071"]["title"] == "Закрытый"


def test_put_per_chat_config(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    payload = RootConfig(
        chats={
            "-1001": ChatConfig(chat_id=-1001, title="A", welcome_text="привет A"),
            "-1002": ChatConfig(chat_id=-1002, title="B", welcome_text="привет B"),
        }
    )
    r = c.put("/api/config", headers={"X-Sync-Secret": "change-me"}, json=payload.model_dump())
    assert r.status_code == 200
    got = c.get("/api/config", headers={"X-Sync-Secret": "change-me"}).json()
    assert got["chats"]["-1001"]["welcome_text"] == "привет A"
    assert got["chats"]["-1002"]["welcome_text"] == "привет B"
