# Админ закрытого Telegram-чата

Стек: **только Python 3.11** (aiogram + FastAPI + Uvicorn). Репозиторий: https://github.com/Inmalkhur/acolite2

```bash
git clone https://github.com/Inmalkhur/acolite2.git
cd acolite2
pip install -r requirements.txt
python main.py
```

Панель: откройте `http://127.0.0.1:3000/` (на Bothost порт из `PORT`, обычно 3000). Секрет — `LOCAL_SYNC_SECRET`.

## Что умеет бот

1. Приветствие новичков и анкета (кик без анкеты отключаемый).
2. Логи, репост из каналов, пинг наименее активного.
3. Фильтр мата с мутом, длинные посты в `.md`, чёрный список.
4. Термины из `data/glossary`, «запланировать», «сделаю».
5. Отдельные настройки на каждый чат. ID подхватывается при добавлении бота или по `/start` в группе.

## Telegram

- BotFather: **/setprivacy → Disable**.
- Бот — **админ** чата (чтение сообщений).
- В группе `/start`, если бот был добавлен до запуска.

## Bothost

Платформа сама ставит **Python 3.11**. Dockerfile в репозитории не нужен и мешает.

В карточке бота:

- шаблон **Python / aiogram**;
- главный файл **`main.py`**;
- **не** включать свой Dockerfile.

Затем новый деплой. В сборке не должно быть `FROM node` и `npm`.

Токен берите из переменных Bothost (`BOT_TOKEN` / `TELEGRAM_BOT_TOKEN`). Не кладите его в Git.
