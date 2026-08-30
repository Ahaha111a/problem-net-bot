import asyncio
import logging
import sys
from datetime import timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db, ensure_platform_defaults
from handlers import router

async def _init_db_with_retry():
    last_error = None
    for attempt in range(1, 6):
        try:
            init_db()
            ensure_platform_defaults()
            logging.info("🗄️ PostgreSQL + Alembic готовы")
            return
        except Exception as exc:
            last_error = exc
            logging.exception("DB startup attempt %s/5 failed", attempt)
            await asyncio.sleep(min(10, attempt * 2))
    raise RuntimeError(f"PostgreSQL/Alembic startup failed: {last_error}") from last_error


async def main():
    await _init_db_with_retry()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    logging.info("👤 Пользовательский бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
