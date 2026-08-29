# Админ закрытого Telegram-чата

Репозиторий: https://github.com/Inmalkhur/acolite2

**На сервере (Bothost)** — только бот и HTTP API (`python main.py`). Панели там нет.

**Локально** — GUI:

```bash
python local/gui.py
```

Откройте `http://127.0.0.1:43122/`, вставьте публичный URL бота и секрет (`LOCAL_SYNC_SECRET`, по умолчанию `change-me`). Чат `-5456516071` появится после связи с API.

Опционально: `BOT_API_URL=https://… python local/gui.py` (подставит адрес). Порт: `GUI_PORT`. Только localhost: `GUI_HOST=127.0.0.1` (так по умолчанию).

## Сервер

```bash
pip install -r requirements.txt
python main.py
```

Проверка бота: `/ping` или `тест`. Обычный текст бот не эхоит.

Если `WEBHOOK_URL` указывает на панель хостинга — polling. Принудительно: `TELEGRAM_USE_POLLING=1`.

## Telegram

- BotFather: **/setprivacy → Disable**.
- Бот — **админ** чата.
- В группе `/start`, если бота добавили до запуска.

## Bothost

Python 3.11, главный файл **`main.py`**, без своего Dockerfile и без Node. Токен только в переменных окружения.
