import asyncio
import logging
import sys
from datetime import timedelta
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

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


async def _health_server():
    app = web.Application()
    async def health(request):
        try:
            from database import get_connection
            con = get_connection(); con.execute("SELECT 1").fetchone(); con.close()
            return web.json_response({"ok": True, "service": "problem-net-user-bot", "database": "ok"})
        except Exception as exc:
            return web.json_response({"ok": False, "database": str(exc)}, status=503)
    app.router.add_get('/health', health)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(__import__('os').getenv('PORT','8080'))); await site.start()
    return runner


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Добавьте токен пользовательского бота в Railway Variables.")
    await _init_db_with_retry()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    health_runner = await _health_server()
    dp = Dispatcher()
    dp.include_router(router)
    logging.info("👤 Пользовательский бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        await health_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
