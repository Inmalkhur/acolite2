from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bot_token: str = ""
    local_sync_secret: str = "change-me"
    host: str = "0.0.0.0"
    port: int = 43121
    data_dir: Path = Path("./runtime")


settings = Settings()
