from app.webhook import resolve_webhook_url


def test_polling_when_no_env() -> None:
    assert resolve_webhook_url({}) == ""


def test_domain_alone_does_not_enable_webhook() -> None:
    assert (
        resolve_webhook_url({"DOMAIN": "bot-1787963517-5953-petrel.bothost.tech"}) == ""
    )
    assert (
        resolve_webhook_url(
            {"WEBHOOK_URL": "https://bot-1787963517-5953-petrel.bothost.tech/telegram/webhook"}
        )
        == ""
    )


def test_ignore_junk_webhook_url() -> None:
    assert resolve_webhook_url({"WEBHOOK_URL": "https://bothost.ru/env/bot"}) == ""


def test_webhook_only_with_explicit_flag() -> None:
    url = "https://bot.example.com/telegram/webhook"
    assert resolve_webhook_url({"TELEGRAM_WEBHOOK": "1", "WEBHOOK_URL": url}) == url
    env = {"WEBHOOK_URL": "https://app.bothost.ru", "TELEGRAM_WEBHOOK": "1"}
    assert resolve_webhook_url(env) == "https://app.bothost.ru/telegram/webhook"


def test_force_polling_overrides_flag() -> None:
    assert (
        resolve_webhook_url(
            {
                "TELEGRAM_USE_POLLING": "1",
                "TELEGRAM_WEBHOOK": "1",
                "WEBHOOK_URL": "https://bot.example.com/telegram/webhook",
            }
        )
        == ""
    )
