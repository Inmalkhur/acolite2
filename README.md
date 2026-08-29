# Админ закрытого Telegram-чата

Репозиторий: https://github.com/Inmalkhur/acolite2

**На сервере (Bothost)** — только бот и HTTP API (`python main.py`). Панели там нет.

**Локально** — GUI:

```bash
python local/gui.py
```

Откройте `http://127.0.0.1:43122/`, вставьте публичный URL бота и секрет (`LOCAL_SYNC_SECRET`, по умолчанию `change-me`). Чат `-5456516071` появится после связи с API.

Опционально: `BOT_API_URL=https://bot-1787963517-5953-petrel.bothost.tech python local/gui.py` (подставит адрес). Порт: `GUI_PORT`. Только localhost: `GUI_HOST=127.0.0.1` (так по умолчанию).

## Сервер

```bash
pip install -r requirements.txt
python main.py
```

Проверка бота: `/ping` или `тест`. Обычный текст бот не эхоит.

Если `WEBHOOK_URL` или `DOMAIN` заданы Bothost — бот всё равно на **polling**, пока не выставите `TELEGRAM_WEBHOOK=1`. Иначе Telegram шлёт апдейты на HTTPS, а контейнер их не получает, `/ping` молчит.

## Telegram

- BotFather: **/setprivacy → Disable**.
- Бот — **админ** чата.
- В группе `/start`, если бота добавили до запуска.

## Bothost

Python 3.11, главный файл **`main.py`**, без своего Dockerfile и без Node. Токен только в переменных окружения.

Данные (конфиг чатов, логи, анкеты) пишутся в **`/app/data`** — Bothost сохраняет эту папку при перезапуске. Переопределение: `DATA_DIR`. На своей машине, если `/app/data` недоступен, используется `./runtime`.
