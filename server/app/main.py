from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m app.main` from /app, /app/server, or `python app/main.py`.
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import asyncio

from aiogram import Bot
import uvicorn

from app.api import create_app
from app.bot import build_dispatcher, tick_jobs
from app.holder import BotHolder
from app.settings import settings
from app.store import Store
from app import store as store_mod


async def run() -> None:
    store_mod.store = Store(settings.data_dir)
    store = store_mod.store
    holder = BotHolder()
    app = create_app(store, holder)

    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="info")
    server = uvicorn.Server(config)

    polling = None
    ticker = None
    bot = None

    if settings.bot_token:
        bot = Bot(settings.bot_token)
        holder.bot = bot
        me = await bot.get_me()
        store.bot_username = me.username or ""
        dp = build_dispatcher(store)

        async def ticks() -> None:
            while True:
                await tick_jobs(bot, store)
                await asyncio.sleep(30)

        ticker = asyncio.create_task(ticks())
        polling = asyncio.create_task(dp.start_polling(bot, handle_signals=False))

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
