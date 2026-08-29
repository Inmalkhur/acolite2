from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
import uvicorn

from app.api import create_app
from app.bot import ALLOWED_UPDATES, build_dispatcher, tick_jobs
from app.holder import BotHolder
from app.settings import settings
from app.store import Store
from app.webhook import resolve_webhook_url
from app import store as store_mod


async def run() -> None:
    store_mod.store = Store(settings.data_dir)
    store = store_mod.store
    print(f"Data dir: {store.root} (Bothost persists /app/data)", flush=True)
    holder = BotHolder()
    dp = build_dispatcher(store) if settings.bot_token else None
    app = create_app(store, holder, dispatcher=dp)

    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="info")
    server = uvicorn.Server(config)

    polling = None
    ticker = None
    bot = None

    if settings.bot_token:
        bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
        holder.bot = bot
        me = await bot.get_me()
        store.bot_username = me.username or ""
        print(f"Bot @{store.bot_username} id={me.id}", flush=True)

        async def ticks() -> None:
            while True:
                await tick_jobs(bot, store)
                await asyncio.sleep(30)

        ticker = asyncio.create_task(ticks())
        hook = resolve_webhook_url()
        if hook:
            await bot.set_webhook(hook, allowed_updates=ALLOWED_UPDATES, drop_pending_updates=False)
            store.telegram_mode = "webhook"
            print(f"Webhook set: {hook}", flush=True)
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            store.telegram_mode = "polling"
            polling = asyncio.create_task(
                dp.start_polling(bot, handle_signals=False, allowed_updates=ALLOWED_UPDATES)
            )
            print("Polling started (chat_member + messages)", flush=True)

    try:
        await server.serve()
    finally:
        if polling:
            polling.cancel()
        if ticker:
            ticker.cancel()
        if bot:
            await bot.session.close()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
