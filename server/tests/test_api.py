from fastapi.testclient import TestClient

from app.api import create_app
from app.holder import BotHolder
from app.store import Store


def test_health(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    r = c.get("/health")
    assert r.json()["ok"] is True


def test_config_auth(tmp_path) -> None:
    store = Store(tmp_path)
    app = create_app(store, BotHolder())
    c = TestClient(app)
    assert c.get("/api/config").status_code == 401
    r = c.get("/api/config", headers={"X-Sync-Secret": "change-me"})
    assert r.status_code == 200
    assert "welcome_text" in r.json()
