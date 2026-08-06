import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from config import BOT_TOKEN
from keyboards import main_keyboard
from handlers import router
from callbacks import router as callbacks_router


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "💙 <b>Добро пожаловать в «Проблем нет»!</b>\n\n"
        "Здесь можно анонимно поделиться своей историей и получить поддержку.\n\n"
        "Выберите действие ниже 👇",
        reply_markup=main_keyboard,
    )


@dp.message(F.text == "💡 Совет дня")
async def advice(message: Message):
    await message.answer(
        "🌱 Иногда самый маленький шаг вперёд важнее идеального плана. "
        "Позаботьтесь сегодня хотя бы о чём-то одном, что важно именно для вас."
    )


@dp.message(F.text == "📚 Полезные материалы")
async def materials(message: Message):
    await message.answer(
        "📚 Скоро здесь появятся статьи, упражнения и полезные материалы."
    )


@dp.message(F.text == "❤️ Поддержка")
async def support(message: Message):
    await message.answer(
        "💙 Спасибо, что вы здесь.\n\n"
        "Если вы переживаете тяжёлые чувства, помните: просить о помощи — нормально. "
        "Наш бот может помочь вам поделиться своей историей."
    )


async def main():
    print("🚀 ProblemNet AI запущен")
    dp.include_router(router)
    dp.include_router(callbacks_router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
