import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import router
from callbacks import callback_router


async def main():
    print("🚀 Запуск бота...")

    # Инициализация базы данных
    init_db()
    print("✅ База данных инициализирована")

    # Создаём бота
    bot = Bot(token=BOT_TOKEN)
    print("✅ Bot создан")

    # Создаём диспетчер
    dp = Dispatcher()

    # Подключаем обработчики пользователей
    dp.include_router(router)

    # Подключаем обработчики callback-кнопок
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
