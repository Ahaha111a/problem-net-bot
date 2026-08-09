import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers import router
from callbacks import callback_router

async def main():
print("🚀 Запуск бота...")

init_db()

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()

# Основной пользовательский router
dp.include_router(router)

# Callback и административные действия
dp.include_router(callback_router)

print("✅ Бот запущен")

try:
    await dp.start_polling(bot)

finally:
    await bot.session.close()

if name == "main":
asyncio.run(main())
