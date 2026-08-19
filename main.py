import asyncio
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, CHANNEL_ID, ADMIN_IDS

from database import (
    init_db,
    get_due_notification_users,
    mark_notification_sent,
    get_due_scheduled_stories,
    claim_scheduled_story,
    release_scheduled_story,
    publish_story,
    get_story_reaction_counts,
    log_admin_action,
    backup_database,
    get_complaints,
    get_sla_breaches,
    create_event_notification_once,
)

from handlers import router, get_channel_message_link
from callbacks import callback_router
from keyboards import (
    channel_story_keyboard,
    published_story_keyboard,
)

from admin_api import start_admin_web


# =========================================================
# TIMEZONE
# =========================================================

TIMEZONE = ZoneInfo("Europe/Moscow")


# =========================================================
# DAILY EMERGENCY SUPPORT NOTIFICATIONS
# =========================================================

async def send_daily_support_notifications(bot: Bot):
    now = datetime.now(TIMEZONE)
    now_iso = now.isoformat()

    user_ids = get_due_notification_users(now_iso)

    for user_id in user_ids:
        try:
            await bot.send_message(
                user_id,
                "🆘 <b>Напоминание о поддержке</b>\n\n"
                "Если вам сейчас тяжело или просто хочется "
                "с кем-то поговорить, вы можете воспользоваться "
                "функцией «🆘 Экстренная поддержка».\n\n"
                "Вы можете написать сотруднику поддержки "
                "прямо в боте. 💙",
                parse_mode="HTML",
            )

            mark_notification_sent(user_id)

        except Exception as error:
            print(
                f"DAILY SUPPORT NOTIFICATION ERROR "
                f"({user_id}): {error}"
            )


# =========================================================
# SCHEDULED PUBLICATION
# =========================================================

async def publish_scheduled_story(bot: Bot, story):
    story_id = story["id"]

    if not claim_scheduled_story(story_id):
        return

    post_text = (
        story["post_text"] or ""
    ).strip()

    if not post_text:
        release_scheduled_story(
            story_id,
            (
                datetime.now(ZoneInfo("UTC"))
                + timedelta(minutes=10)
            ).isoformat(),
        )

        print(
            f"SCHEDULED STORY {story_id}: "
            "empty post, retry in 10 minutes"
        )

        return

    try:
        sent = await bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
            reply_markup=channel_story_keyboard(
                story_id,
                None,
                get_story_reaction_counts(story_id),
            ),
        )

        publish_story(
            story_id,
            sent.message_id,
        )

        log_admin_action(
            story["scheduled_by"] or 0,
            "scheduled_publish",
            story_id=story_id,
            user_id=story["user_id"],
            details=(
                f"channel_message_id="
                f"{sent.message_id}"
            ),
        )

        link = await get_channel_message_link(
            bot,
            sent.message_id,
        )

        if link:

            try:
                await sent.edit_reply_markup(
                    reply_markup=channel_story_keyboard(
                        story_id,
                        link,
                        get_story_reaction_counts(
                            story_id
                        ),
                    )
                )

            except Exception as error:
                print(
                    "SCHEDULED CHANNEL KEYBOARD ERROR:",
                    error,
                )

            try:
                await bot.send_message(
                    story["user_id"],
                    "🎉 <b>Ваша история была опубликована!</b>\n\n"
                    "Публикация была выполнена "
                    "автоматически по расписанию.\n\n"
                    "Спасибо, что поделились ей с нами 💙",
                    parse_mode="HTML",
                    reply_markup=published_story_keyboard(
                        link,
                        story_id,
                        get_story_reaction_counts(
                            story_id
                        ),
                    ),
                )

            except Exception as error:
                print(
                    "SCHEDULED USER NOTIFY ERROR:",
                    error,
                )

        print(
            f"✅ Scheduled story #{story_id} published"
        )

    except Exception as error:

        print(
            f"SCHEDULED PUBLISH ERROR "
            f"#{story_id}: {error}"
        )

        release_scheduled_story(
            story_id,
            (
                datetime.now(ZoneInfo("UTC"))
                + timedelta(minutes=10)
            ).isoformat(),
        )


# =========================================================
# SCHEDULE WORKER
# =========================================================

async def scheduled_publication_worker(bot: Bot):

    while True:

        try:
            now_utc = (
                datetime.now(
                    ZoneInfo("UTC")
                ).isoformat()
            )

            stories = get_due_scheduled_stories(
                now_utc,
                10,
            )

            for story in stories:
                await publish_scheduled_story(
                    bot,
                    story,
                )

        except Exception as error:

            print(
                f"SCHEDULE WORKER ERROR: {error}"
            )

        await asyncio.sleep(30)


# =========================================================
# ADMIN EVENT NOTIFICATIONS
# =========================================================

async def admin_event_notification_worker(
    bot: Bot,
):

    while True:

        try:

            complaints = get_complaints(
                "new",
                20,
            )

            breaches = get_sla_breaches()

            for admin_id in ADMIN_IDS:

                for row in complaints:

                    fingerprint = (
                        f"complaint:{row['id']}"
                    )

                    created = (
                        create_event_notification_once(
                            admin_id,
                            "complaint",
                            "⚠️ Новая жалоба",
                            (
                                f"История #{row['story_id']}\n"
                                f"Причина: {row['reason']}"
                            ),
                            fingerprint,
                        )
                    )

                    if created:

                        try:

                            await bot.send_message(
                                admin_id,
                                (
                                    "⚠️ <b>Новая жалоба</b>\n\n"
                                    f"История #{row['story_id']}\n"
                                    f"Причина: {row['reason']}"
                                ),
                                parse_mode="HTML",
                            )

                        except Exception as error:

                            print(
                                "ADMIN COMPLAINT "
                                f"NOTIFY ERROR: {error}"
                            )

                for row in breaches:

                    fingerprint = (
                        f"sla:"
                        f"{row['id']}:"
                        f"{row['first_response_due_at']}"
                    )

                    created = (
                        create_event_notification_once(
                            admin_id,
                            "sla",
                            "🔴 Нарушен SLA",
                            (
                                f"Диалог #{row['id']}\n"
                                f"Приоритет: {row['priority']}"
                            ),
                            fingerprint,
                        )
                    )

                    if created:

                        try:

                            await bot.send_message(
                                admin_id,
                                (
                                    "🔴 <b>SLA нарушен</b>\n\n"
                                    f"Диалог #{row['id']}\n"
                                    f"Приоритет: "
                                    f"{row['priority']}"
                                ),
                                parse_mode="HTML",
                            )

                        except Exception as error:

                            print(
                                "ADMIN SLA NOTIFY ERROR:",
                                error,
                            )

        except Exception as error:

            print(
                f"ADMIN EVENT WORKER ERROR: {error}"
            )

        await asyncio.sleep(60)


# =========================================================
# MAINTENANCE
# =========================================================

async def maintenance_worker(bot: Bot):

    last_notification_minute = None
    last_backup_date = None

    while True:

        try:

            now = datetime.now(TIMEZONE)

            minute_key = now.strftime(
                "%Y-%m-%d %H:%M"
            )

            if (
                minute_key
                != last_notification_minute
            ):

                await send_daily_support_notifications(
                    bot
                )

                last_notification_minute = (
                    minute_key
                )

            # Автоматическая резервная копия.
            # 03:15 по Москве.

            if (
                now.hour == 3
                and now.minute == 15
                and last_backup_date != now.date()
            ):

                try:

                    path = backup_database()

                    print(
                        "💾 Automatic database backup:",
                        path,
                    )

                    last_backup_date = now.date()

                except Exception as error:

                    print(
                        "AUTOMATIC BACKUP ERROR:",
                        error,
                    )

        except Exception as error:

            print(
                f"MAINTENANCE WORKER ERROR: {error}"
            )

        await asyncio.sleep(30)


# =========================================================
# MAIN
# =========================================================

async def main():

    print("🚀 Запуск бота...")

    init_db()

    print(
        "✅ База данных инициализирована"
    )

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
        ),
    )

    dp = Dispatcher()

    dp.include_router(
        callback_router
    )

    dp.include_router(
        router
    )

    print(
        "✅ Обработчики подключены"
    )

    print(
        "🚀 Бот запущен"
    )

    scheduler_task = asyncio.create_task(
        scheduled_publication_worker(bot)
    )

    maintenance_task = asyncio.create_task(
        maintenance_worker(bot)
    )

    admin_event_task = asyncio.create_task(
        admin_event_notification_worker(bot)
    )

    web_runner = await start_admin_web(
        bot
    )

    try:

        await dp.start_polling(
            bot
        )

    finally:

        scheduler_task.cancel()
        maintenance_task.cancel()
        admin_event_task.cancel()

        try:
            await web_runner.cleanup()
        except Exception:
            pass

        await bot.session.close()


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
    )

    asyncio.run(
        main()
    )
