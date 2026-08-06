import asyncio
import os

from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Поделиться историей")
        ],
        [
            KeyboardButton(text="💡 Совет дня"),
            KeyboardButton(text="ℹ️ О проекте")
        ]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "💙 Добро пожаловать в «Проблем нет».\n\n"
        "Здесь можно анонимно рассказать о своей ситуации "
        "и получить поддержку.\n\n"
        "Нажмите кнопку ниже, чтобы поделиться историей.",
        reply_markup=main_keyboard
    )


@dp.message(lambda message: message.text == "📝 Поделиться историей")
async def story_start(message: types.Message):
    await message.answer(
        "💙 Расскажите, что вас беспокоит.\n\n"
        "Ваше сообщение будет рассмотрено и "
        "опубликовано анонимно в канале."
    )


@dp.message()
async def receive_story(message: types.Message):

    user_text = message.text

    await bot.send_message(
        ADMIN_ID,
        "📥 Новая история:\n\n"
        f"{user_text}\n\n"
        f"ID пользователя: {message.from_user.id}"
    )

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история получена. Мы внимательно её рассмотрим."
    )


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
