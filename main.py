import asyncio
import logging
import random
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db, get_due_notification_users, mark_notification_sent
from handlers import router
from callbacks import callback_router
from keyboards import emergency_support_keyboard


TIMEZONE = ZoneInfo("Europe/Oslo")


DAILY_SUPPORT_MESSAGES = [
    (
        "💙 <b>Напоминание</b>\n\n"
        "Если тебе сейчас тяжело, не обязательно справляться со всем в одиночку.\n\n"
        "В боте есть функция «Экстренная поддержка» — ты можешь обратиться за помощью в любой момент."
    ),
    (
        "🆘 <b>Нужна поддержка?</b>\n\n"
        "Если что-то сильно беспокоит тебя прямо сейчас, ты можешь обратиться к сотруднику поддержки через бота.\n\n"
        "Мы рядом."
    ),
    (
        "💙 <b>Ты можешь попросить о помощи</b>\n\n"
        "Иногда достаточно просто рассказать о том, что происходит.\n\n"
        "Если тебе нужна поддержка — воспользуйся функцией «Экстренная поддержка»."
    ),
]


def next_notification_schedule(now: datetime):
    next_day = now.date() + timedelta(days=1)
    minute = random.randint(10 * 60, 21 * 60)
    return next_day.isoformat(), minute


async def daily_support_notifications(bot: Bot):
    """Проверяет расписание раз в минуту и отправляет каждому пользователю
    не более одного уведомления в сутки в его персональное случайное время.
    """
    await asyncio.sleep(10)

    while True:
        now = datetime.now(TIMEZONE)
        date_iso = now.date().isoformat()
        current_minute = now.hour * 60 + now.minute

        try:
            user_ids = get_due_notification_users(date_iso, current_minute)
            for user_id in user_ids:
                if user_id in ADMIN_IDS:
                    next_date, next_minute = next_notification_schedule(now)
                    mark_notification_sent(user_id, next_date, next_minute)
                    continue

                try:
                    await bot.send_message(
                        user_id,
                        random.choice(DAILY_SUPPORT_MESSAGES),
                        parse_mode="HTML",
                        reply_markup=emergency_support_keyboard(),
                    )
                    print(f"📨 Daily support sent: {user_id}")
                except Exception as error:
                    print(f"DAILY NOTIFICATION ERROR ({user_id}): {error}")
                finally:
                    # Даже если пользователь заблокировал бота, не спамим его повторно
                    # каждую минуту: переносим следующее окно на завтра.
                    next_date, next_minute = next_notification_schedule(now)
                    mark_notification_sent(user_id, next_date, next_minute)

        except Exception as error:
            print(f"DAILY NOTIFICATION LOOP ERROR: {error}")

        # Проверяем расписание каждую минуту, поэтому индивидуальное время
        # пользователя не зависит от случайного интервала проверки.
        await asyncio.sleep(60)


async def main():
    print("🚀 Запуск бота...")

    init_db()
    print("✅ База данных инициализирована")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    # Основной router первым: меню и FSM-сценарии обрабатываются предсказуемо.
    dp.include_router(router)
    dp.include_router(callback_router)

    print("✅ Обработчики подключены")
    print("🚀 Бот запущен")

    notification_task = asyncio.create_task(daily_support_notifications(bot))

    try:
        await dp.start_polling(bot)
    finally:
        notification_task.cancel()
        try:
            await notification_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
