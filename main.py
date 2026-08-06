import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from config import BOT_TOKEN

from handlers import router
from callbacks import router as callbacks_router


async def main():

    bot = Bot(
        token=BOT_TOKEN
    )

    dp = Dispatcher()


    dp.include_router(router)

    dp.include_router(callbacks_router)


    await bot.set_my_commands(
        [
            BotCommand(
                command="start",
                description="Начать"
            ),
            BotCommand(
                command="help",
                description="Помощь"
            )
        ]
    )


    print("🚀 Бот запущен")


    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(main())
