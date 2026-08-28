from __future__ import annotations

import os


def _truthy(name: str, env: dict[str, str]) -> bool:
    return env.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def resolve_webhook_url(environ: dict[str, str] | None = None) -> str:
    """Return a Telegram webhook URL, or empty string to use long polling.

    Bothost and similar hosts often set WEBHOOK_URL to a panel/env page.
    Setting that as Telegram's webhook makes the bot deaf. We only honor
    URLs that already point at /telegram/webhook, or an explicit TELEGRAM_WEBHOOK=1
    plus an https origin we can append the path to.
    """
    env = environ if environ is not None else dict(os.environ)
    if _truthy("TELEGRAM_USE_POLLING", env):
        return ""

    explicit = (env.get("WEBHOOK_URL") or "").strip()
    if explicit:
        low = explicit.lower()
        junk = (
            "/env",
            "environment",
            "/panel",
            "dashboard",
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
        )
        if any(marker in low for marker in junk):
            return ""
        if "/telegram/webhook" in low or low.rstrip("/").endswith("webhook"):
            return explicit.rstrip("/")
        if _truthy("TELEGRAM_WEBHOOK", env) and low.startswith("https://"):
            return explicit.rstrip("/") + "/telegram/webhook"
        return ""

    domain = (env.get("DOMAIN") or env.get("PUBLIC_URL") or "").strip()
    if domain:
        host = domain.removeprefix("https://").removeprefix("http://").strip("/")
        if host and "localhost" not in host:
            return f"https://{host}/telegram/webhook"
    return ""
