from __future__ import annotations

import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    local_sync_secret: str = "change-me"
    host: str = "0.0.0.0"
    port: int = 3000
    data_dir: Path = Path("./runtime")

    @model_validator(mode="after")
    def fill_token_aliases(self) -> "Settings":
        if self.bot_token.strip():
            return self
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
        return self


settings = Settings()
