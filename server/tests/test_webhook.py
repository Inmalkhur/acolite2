from app.webhook import resolve_webhook_url


def test_polling_when_no_env() -> None:
    assert resolve_webhook_url({}) == ""


def test_ignore_junk_webhook_url() -> None:
    assert resolve_webhook_url({"WEBHOOK_URL": "https://bothost.ru/env/bot"}) == ""
    assert resolve_webhook_url({"WEBHOOK_URL": "http://127.0.0.1:3000"}) == ""


def test_honor_explicit_telegram_path() -> None:
    url = "https://bot.example.com/telegram/webhook"
    assert resolve_webhook_url({"WEBHOOK_URL": url}) == url


def test_force_polling() -> None:
    assert (
        resolve_webhook_url(
            {
                "TELEGRAM_USE_POLLING": "1",
                "WEBHOOK_URL": "https://bot.example.com/telegram/webhook",
            }
        )
        == ""
    )


def test_origin_only_with_flag() -> None:
    env = {"WEBHOOK_URL": "https://app.bothost.ru", "TELEGRAM_WEBHOOK": "1"}
    assert resolve_webhook_url(env) == "https://app.bothost.ru/telegram/webhook"
    assert resolve_webhook_url({"WEBHOOK_URL": "https://app.bothost.ru"}) == ""
