import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import user_handlers
import callbacks
from config import BOT_TOKEN
from database import init_db, ensure_platform_defaults


async def main():
    init_db(); ensure_platform_defaults()
    # Пользовательский бот не имеет административных обработчиков.
    user_handlers.ADMIN_IDS = []
    callbacks.ADMIN_IDS = []

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(callbacks.callback_router)
    dp.include_router(user_handlers.router)
    print('👤 Пользовательский бот запущен')
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
