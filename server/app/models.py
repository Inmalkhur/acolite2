from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BotConfig(BaseModel):
    chat_id: int | None = None
    welcome_text: str = (
        "Добро пожаловать. Ответьте на это сообщение анкетой: кто вы, "
        "чем занимаетесь и зачем пришли в чат. Можно несколькими сообщениями."
    )
    questionnaire_timeout_minutes: int = 60
    questionnaire_kick_enabled: bool = True
    logging_enabled: bool = True
    log_flush_interval_minutes: int = 60
    channel_ids: list[int] = Field(default_factory=list)
    inactive_warning_enabled: bool = True
    inactive_check_hours: int = 24
    inactive_warning_text: str = (
        "{mention}, вы сейчас наименее активны в чате. "
        "Если молчание продолжится, вас могут исключить."
    )
    forbidden_words: list[str] = Field(
        default_factory=lambda: ["блять", "хуй", "пизд", "ебан", "сука"]
    )
    mute_seconds: int = 3600
    mute_notice: str = "Сообщение удалено. Мут на {minutes} мин. за запрещённые выражения."
    long_post_chars: int = 800
    long_post_burst: int = 3
    long_post_burst_seconds: int = 120
    blacklist: list[int] = Field(default_factory=list)
    ollama_model: str = "llama3.2"
    nlp_profanity: bool = False
    missing_term_reply: str = "В базе терминов этого нет."
    activity_reminders: list[int] = Field(default_factory=lambda: [1440, 180, 60])
    timezone: str = "Europe/Moscow"


class NlpJob(BaseModel):
    id: str
    kind: Literal["questionnaire", "profanity", "term", "schedule"]
    payload: dict
    created_at: float


class NlpResult(BaseModel):
    id: str
    kind: str
    ok: bool
    payload: dict


class MdDocument(BaseModel):
    path: str
    content: str
    updated_at: float


class LogChunk(BaseModel):
    filename: str
    content: str
    from_ts: float
    to_ts: float
