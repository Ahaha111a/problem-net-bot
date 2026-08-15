import asyncio
import logging
import random
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db, get_connection

from handlers import router
from callbacks import callback_router


# =========================================================
# НАСТРОЙКИ
# =========================================================

MIN_NOTIFICATION_DELAY = 60 * 60 * 2
MAX_NOTIFICATION_DELAY = 60 * 60 * 22


# =========================================================
# КЛАВИАТУРА ЭКСТРЕННОЙ ПОДДЕРЖКИ
# =========================================================

def emergency_support_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆘 Экстренная поддержка",
                    callback_data="open_emergency_support",
                )
            ]
        ]
    )


# =========================================================
# ПОЛУЧЕНИЕ ПОЛЬЗОВАТЕЛЕЙ
# =========================================================

def get_user_ids():
    """
    Получаем пользователей, которые когда-либо
    создавали истории или обращения в поддержку.
    """

    connection = get_connection()

    user_ids = set()

    try:
        rows = connection.execute(
            """
            SELECT DISTINCT user_id
            FROM stories
            """
        ).fetchall()

        for row in rows:
            user_ids.add(row["user_id"])

    except Exception as error:
        print(
            f"GET STORY USERS ERROR: {error}"
        )

    try:
        rows = connection.execute(
            """
            SELECT DISTINCT user_id
            FROM support_dialogs
            """
        ).fetchall()

        for row in rows:
            user_ids.add(row["user_id"])

    except Exception as error:
        print(
            f"GET SUPPORT USERS ERROR: {error}"
        )

    connection.close()

    # Администраторам такие уведомления не нужны
    user_ids = {
        user_id
        for user_id in user_ids
        if user_id not in ADMIN_IDS
    }

    return list(user_ids)


# =========================================================
# СОЗДАНИЕ ТАБЛИЦЫ ДЛЯ УВЕДОМЛЕНИЙ
# =========================================================

def init_notification_table():
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_notifications (
            user_id INTEGER PRIMARY KEY,
            last_sent_at TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


# =========================================================
# ПРОВЕРКА: МОЖНО ЛИ ОТПРАВИТЬ
# =========================================================

def can_send_daily_notification(user_id: int) -> bool:
    connection = get_connection()

    row = connection.execute(
        """
        SELECT last_sent_at
        FROM daily_notifications
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchone()

    connection.close()

    if row is None:
        return True

    if not row["last_sent_at"]:
        return True

    try:
        last_sent = datetime.fromisoformat(
            row["last_sent_at"]
        )
    except Exception:
        return True

    return datetime.utcnow() - last_sent >= timedelta(
        hours=24
    )


# =========================================================
# СОХРАНЕНИЕ ОТПРАВКИ
# =========================================================

def mark_daily_notification_sent(user_id: int):
    connection = get_connection()

    connection.execute(
        """
        INSERT INTO daily_notifications (
            user_id,
            last_sent_at
        )
        VALUES (?, CURRENT_TIMESTAMP)

        ON CONFLICT(user_id)
        DO UPDATE SET
            last_sent_at = CURRENT_TIMESTAMP
        """,
        (user_id,),
    )

    connection.commit()
    connection.close()


# =========================================================
# ТЕКСТ УВЕДОМЛЕНИЯ
# =========================================================

def get_daily_support_text():
    messages = [
        (
            "💙 <b>Напоминание</b>\n\n"
            "Если тебе сейчас тяжело, не обязательно "
            "справляться со всем в одиночку.\n\n"
            "В боте есть функция «Экстренная поддержка» — "
            "ты можешь обратиться за помощью в любой момент."
        ),
        (
            "🆘 <b>Нужна поддержка?</b>\n\n"
            "Если что-то сильно беспокоит тебя прямо сейчас, "
            "ты можешь обратиться к сотруднику поддержки "
            "через бота.\n\n"
            "Мы рядом."
        ),
        (
            "💙 <b>Ты можешь попросить о помощи</b>\n\n"
            "Иногда достаточно просто рассказать о том, "
            "что происходит.\n\n"
            "Если тебе нужна поддержка — воспользуйся "
            "функцией «Экстренная поддержка»."
        ),
    ]

    return random.choice(messages)


# =========================================================
# ОТПРАВКА ЕЖЕДНЕВНЫХ УВЕДОМЛЕНИЙ
# =========================================================

async def daily_support_notifications(bot: Bot):
    """
    Фоновая задача.

    Периодически проверяет пользователей и отправляет
    уведомление тем, кому оно ещё не отправлялось
    последние 24 часа.
    """

    await asyncio.sleep(30)

    while True:

        try:
            user_ids = get_user_ids()

            print(
                f"📨 Проверка ежедневных уведомлений. "
                f"Пользователей: {len(user_ids)}"
            )

            for user_id in user_ids:

                if not can_send_daily_notification(
                    user_id
                ):
                    continue

                # Небольшая случайная вероятность,
                # чтобы уведомления не улетали всем одновременно.
                if random.random() > 0.25:
                    continue

                try:
                    await bot.send_message(
                        user_id,
                        get_daily_support_text(),
                        parse_mode="HTML",
                        reply_markup=(
                            emergency_support_keyboard()
                        ),
                    )

                    mark_daily_notification_sent(
                        user_id
                    )

                    print(
                        f"📨 Daily support sent: {user_id}"
                    )

                    # Небольшая пауза между пользователями
                    await asyncio.sleep(
                        random.uniform(1, 3)
                    )

                except Exception as error:

                    print(
                        f"DAILY NOTIFICATION ERROR "
                        f"({user_id}): {error}"
                    )

        except Exception as error:

            print(
                f"DAILY NOTIFICATION LOOP ERROR: "
                f"{error}"
            )

        # Следующая проверка через случайное время
        delay = random.randint(
            MIN_NOTIFICATION_DELAY,
            MAX_NOTIFICATION_DELAY,
        )

        print(
            f"⏰ Следующая проверка уведомлений "
            f"через {delay // 3600} ч."
        )

        await asyncio.sleep(delay)


# =========================================================
# MAIN
# =========================================================

async def main():

    print("🚀 Запуск бота...")

    # База
    init_db()

    # Таблица ежедневных уведомлений
    init_notification_table()

    print(
        "✅ База данных инициализирована"
    )

    # Bot
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        ),
    )

    # Dispatcher
    dp = Dispatcher()

    # Сначала основной router.
    # Это важно: кнопки меню должны обрабатываться раньше
    # state-handler'ов из callbacks.py.
    dp.include_router(
        router
    )

    # Callback-router после основного router.
    dp.include_router(
        callback_router
    )

    print(
        "✅ Обработчики подключены"
    )

    print(
        "🚀 Бот запущен"
    )

    # Запускаем ежедневные уведомления
    notification_task = asyncio.create_task(
        daily_support_notifications(bot)
    )

    try:

        await dp.start_polling(bot)

    finally:

        notification_task.cancel()

        try:
            await notification_task
        except asyncio.CancelledError:
            pass

        await bot.session.close()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
    )

    asyncio.run(
        main()
    )
