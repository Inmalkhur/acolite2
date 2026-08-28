from fastapi.testclient import TestClient

from app.api import create_app
from app.holder import BotHolder
from app.models import ChatConfig, RootConfig
from app.store import Store


def test_admin_page(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "Админ закрытого чата" in r.text


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
