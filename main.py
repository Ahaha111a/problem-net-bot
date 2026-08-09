import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import router
from callbacks import callback_router


async def main():
    print("🚀 Запуск бота...")

    init_db()
    print("✅ База данных инициализирована")

    bot = Bot(
        token=BOT_TOKEN
    )

    print("✅ Bot создан")

    dp = Dispatcher()

    dp.include_router(router)
    dp.include_router(callback_router)

    print("✅ Обработчики подключены")
    print("🚀 Бот запущен и ожидает сообщения...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        print("🛑 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
