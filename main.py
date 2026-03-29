"""Telegram marketplace bot entrypoint."""

from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database import Database
from handlers import admin_router, common_router, seller_router
from middlewares import DatabaseMiddleware


def _validate_startup() -> None:
    if not settings.bot_token:
        logging.error("BOT_TOKEN is missing. Copy .env.example to .env and fill it in.")
        sys.exit(1)
    if not settings.admin_ids:
        logging.warning("ADMIN_IDS is empty — moderation will be impossible.")


def _make_bot() -> Bot:
    proxy = settings.outbound_proxy
    if proxy:
        logging.info("Using outbound HTTP proxy for Telegram API (PythonAnywhere / filtered network).")
        session = AiohttpSession(proxy=proxy)
        return Bot(settings.bot_token, session=session, default_parse_mode=ParseMode.HTML)
    return Bot(settings.bot_token, default_parse_mode=ParseMode.HTML)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    _validate_startup()

    db = Database(settings.database_path)
    await db.init()

    bot = _make_bot()
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.middleware(DatabaseMiddleware(db))

    dp.include_router(common_router)
    dp.include_router(seller_router)
    dp.include_router(admin_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
