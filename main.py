import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import router
from callbacks import callback_router


async def main():
    # Создаём таблицы базы данных
    init_db()

    # Создаём бота
    bot = Bot(token=BOT_TOKEN)

    # Создаём диспетчер
    dp = Dispatcher()

    # Подключаем обработчики пользователей
    dp.include_router(router)

    # Подключаем обработчики кнопок модерации
    dp.include_router(callback_router)

    print("🚀 Бот запущен")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
