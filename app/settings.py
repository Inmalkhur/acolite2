from __future__ import annotations

import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

HOSTED_DATA_DIR = Path("/app/data")


def resolve_data_dir() -> Path:
    """Bothost persists /app/data across restarts. DATA_DIR overrides."""
    explicit = os.getenv("DATA_DIR", "").strip()
    if explicit:
        path = Path(explicit)
        path.mkdir(parents=True, exist_ok=True)
        return path.resolve()
    try:
        HOSTED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = HOSTED_DATA_DIR / ".persist_ok"
        probe.write_text("1", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return HOSTED_DATA_DIR
    except OSError:
        local = Path("./runtime")
        local.mkdir(parents=True, exist_ok=True)
        return local.resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    local_sync_secret: str = "change-me"
    host: str = "0.0.0.0"
    port: int = 3000
    data_dir: Path = Path("./runtime")

    @model_validator(mode="after")
    def fill_paths_and_token(self) -> "Settings":
        if not self.bot_token.strip():
            for key in (
                "BOT_TOKEN",
                "TELEGRAM_BOT_TOKEN",
                "BOT_API_TOKEN",
                "API_TOKEN",
                "TOKEN",
            ):
                value = os.getenv(key, "").strip()
                if value:
                    self.bot_token = value
                    break
        self.data_dir = resolve_data_dir()
        return self


settings = Settings()
