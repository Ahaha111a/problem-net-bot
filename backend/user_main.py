import asyncio
import logging
import sys
from datetime import timedelta
import os
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
            await asyncio.to_thread(init_db)
            await asyncio.to_thread(ensure_platform_defaults)
            logging.info("🗄️ PostgreSQL + Alembic готовы")
            return
        except Exception as exc:
            last_error = exc
            logging.exception("DB startup attempt %s/5 failed", attempt)
            await asyncio.sleep(min(10, attempt * 2))
    raise RuntimeError(f"PostgreSQL/Alembic startup failed: {last_error}") from last_error


def _railway_port(default=8080):
    raw = os.getenv('PORT', '').strip()
    try:
        port = int(raw) if raw else default
    except (TypeError, ValueError):
        port = default
    return port if 1 <= port <= 65535 else default


async def _health_server():
    app = web.Application()

    async def health(request):
        return web.json_response({
            "ok": True,
            "ready": True,
            "service": "problem-net-user-bot",
        }, status=200)

    app.router.add_get('/health', health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = _railway_port()
    site = web.TCPSite(runner, '0.0.0.0', port, reuse_address=True)
    try:
        await site.start()
    except Exception:
        await runner.cleanup()
        raise
    logging.info("🌐 Health server listening on 0.0.0.0:%s", port)
    return runner


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан. Добавьте токен пользовательского бота в Railway Variables.")
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    health_runner = await _health_server()
    try:
        await _init_db_with_retry()
        dp = Dispatcher()
        dp.include_router(router)
        logging.info("👤 Пользовательский бот запущен")
        await dp.start_polling(bot)
    finally:
        await health_runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
