from __future__ import annotations

import os


def _truthy(name: str, env: dict[str, str]) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_webhook_url(environ: dict[str, str] | None = None) -> str:
    """Use long polling unless TELEGRAM_WEBHOOK=1.

    Bothost sets DOMAIN / WEBHOOK_URL whenever a public host exists. Setting
    Telegram's webhook to that host made the bot deaf: probes were GET, and
    POSTs from Telegram never showed up. Polling works without inbound HTTP.
    """
    env = environ if environ is not None else dict(os.environ)
    if _truthy("TELEGRAM_USE_POLLING", env):
        return ""
    if not _truthy("TELEGRAM_WEBHOOK", env):
        return ""

    explicit = (env.get("WEBHOOK_URL") or "").strip()
    if explicit:
        low = explicit.lower()
        if "/telegram/webhook" in low or low.rstrip("/").endswith("webhook"):
            return explicit.rstrip("/")
        if low.startswith("https://"):
            return explicit.rstrip("/") + "/telegram/webhook"

    domain = (env.get("DOMAIN") or env.get("PUBLIC_URL") or "").strip()
    if domain:
        host = domain.removeprefix("https://").removeprefix("http://").strip("/")
        if host and "localhost" not in host:
            return f"https://{host}/telegram/webhook"
    return ""
