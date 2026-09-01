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
    # Railway healthcheck is a liveness check. It must not depend on PostgreSQL
    # migrations, otherwise the service is reported unhealthy while Alembic is
    # still starting (or while a transient DB connection is unavailable).
    app = web.Application()

    async def health(request):
        return web.json_response({
            "ok": True,
            "service": "problem-net-user-bot",
            "status": "alive",
        })

    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(__import__('os').getenv('PORT', '8080'))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info("❤️ User bot health server listening on :%s", port)
    return runner


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Добавьте токен пользовательского бота в Railway Variables.")
    # Start liveness endpoint first so Railway can mark the container alive
    # even while Alembic is applying migrations.
    health_runner = await _health_server()
    try:
        await _init_db_with_retry()
    except Exception:
        await health_runner.cleanup()
        raise
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
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
