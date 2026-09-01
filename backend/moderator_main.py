import asyncio
import logging
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import MODERATOR_BOT_TOKEN, CHANNEL_ID, ADMIN_IDS, TIMEZONE, DATABASE_URL, REDIS_URL
from database import (
    init_db, ensure_platform_defaults, get_due_notification_users, mark_notification_sent,
    get_due_scheduled_stories, claim_scheduled_story, release_scheduled_story, publish_story,
    get_story_reaction_counts, log_admin_action, get_due_repost_jobs, claim_repost_job,
    finish_repost_job, get_story, backup_database, get_complaints, get_sla_breaches,
    create_event_notification_once, set_system_health, log_system_error, integrity_check,
    report_was_sent, mark_report_sent, get_extended_stats, get_moderator_performance, get_latest_safety_decision,
)
from moderator_entry import router as moderator_entry_router
from handlers import router
from callbacks import callback_router, get_channel_message_link
from admin_api import start_admin_web
from keyboards import channel_story_keyboard, published_story_keyboard

TZ = ZoneInfo(TIMEZONE)


async def support_notifications(bot):
    now = datetime.now(TZ)
    for uid in get_due_notification_users(now.isoformat()):
        try:
            await bot.send_message(uid, '🆘 <b>Напоминание о поддержке</b>\n\nЕсли вам тяжело или хочется поговорить с сотрудником, откройте «🆘 Экстренная поддержка».', parse_mode='HTML')
            mark_notification_sent(uid)
        except Exception as e:
            log_system_error('moderator-worker', str(e), f'user={uid}')


async def publish_scheduled(bot, story):
    sid=story['id']
    if not claim_scheduled_story(sid): return
    try:
        safety = get_latest_safety_decision(sid)
        if safety and safety.get('recommendation') != 'publish':
            release_scheduled_story(sid,(datetime.now(ZoneInfo('UTC'))+timedelta(minutes=30)).isoformat())
            log_system_error('scheduler', 'Safety gate blocked scheduled publication', f'story={sid} recommendation={safety.get("recommendation")}')
            return
        text=(story['post_text'] or '').strip()
        if not text: raise RuntimeError('Пустой пост')
        sent=await bot.send_message(CHANNEL_ID,text,reply_markup=channel_story_keyboard(sid))
        publish_story(sid,sent.message_id)
        link=get_channel_message_link(bot,sent.message_id)
        if link:
            await sent.edit_reply_markup(reply_markup=channel_story_keyboard(sid,link,get_story_reaction_counts(sid)))
            await bot.send_message(story['user_id'],'🎉 <b>Ваша история опубликована!</b>\n\nСпасибо, что поделились 💙',parse_mode='HTML',reply_markup=published_story_keyboard(link,sid,get_story_reaction_counts(sid)))
        log_admin_action(story['scheduled_by'] or ADMIN_IDS[0],'scheduled_publish',story_id=sid,user_id=story['user_id'])
    except Exception as e:
        log_system_error('scheduler', str(e), f'story={sid}')
        release_scheduled_story(sid,(datetime.now(ZoneInfo('UTC'))+timedelta(minutes=10)).isoformat())


async def scheduler(bot):
    while True:
        try:
            now=datetime.now(ZoneInfo('UTC')).isoformat()
            for story in get_due_scheduled_stories(now,20): await publish_scheduled(bot,story)
            set_system_health('scheduler','ok','Планировщик работает')
        except Exception as e:
            log_system_error('scheduler',str(e)); set_system_health('scheduler','error',str(e))
        await asyncio.sleep(20)


async def repost_worker(bot):
    while True:
        try:
            now=datetime.now(ZoneInfo('UTC')).isoformat()
            for job in get_due_repost_jobs(now,10):
                if not claim_repost_job(job['id']): continue
                story=get_story(job['story_id'])
                try:
                    sent=await bot.send_message(CHANNEL_ID,story['post_text'],reply_markup=channel_story_keyboard(story['id']))
                    link=get_channel_message_link(bot,sent.message_id)
                    if link: await sent.edit_reply_markup(reply_markup=channel_story_keyboard(story['id'],link,get_story_reaction_counts(story['id'])))
                    finish_repost_job(job['id'],'published')
                except Exception as e:
                    finish_repost_job(job['id'],'failed'); log_system_error('repost',str(e),f'job={job["id"]}')
        except Exception as e: log_system_error('repost-worker',str(e))
        await asyncio.sleep(30)


async def reports_and_monitoring(bot):
    last_backup=None; last_day=None; last_week=None; last_month=None
    while True:
        try:
            now=datetime.now(TZ)
            if now.hour==3 and now.minute==15 and last_backup!=now.date():
                backup_database(); last_backup=now.date()
            # DB integrity every 10 minutes.
            result=integrity_check(); set_system_health('database','ok' if result['ok'] else 'error',str(result))
            set_system_health('moderator-bot','ok','Polling + Mini App')
            if now.hour==23 and now.minute==59:
                day=now.strftime('%Y-%m-%d')
                if not report_was_sent('daily',day):
                    s=get_extended_stats(); text=f'📊 <b>Суточный отчёт</b>\n\nИсторий: {s["total"]}\nОпубликовано: {s["published"]}\nОтклонено: {s["rejected"]}'
                    for aid in ADMIN_IDS:
                        try: await bot.send_message(aid,text,parse_mode='HTML')
                        except Exception: pass
                    mark_report_sent('daily',day)
            if now.weekday()==6 and now.hour==23 and now.minute==55:
                key=now.strftime('%G-W%V')
                if not report_was_sent('weekly',key):
                    perf=get_moderator_performance(7)
                    text='📈 <b>Недельный отчёт</b>\n\n'+ '\n'.join(f'• {r["admin_id"]}: {r["actions"]} действий' for r in perf) if perf else 'Данных пока нет.'
                    for aid in ADMIN_IDS:
                        try: await bot.send_message(aid,text,parse_mode='HTML')
                        except Exception: pass
                    mark_report_sent('weekly',key)
            if now.day==1 and now.hour==23 and now.minute==50:
                key=now.strftime('%Y-%m')
                if not report_was_sent('monthly',key):
                    s=get_extended_stats(); text=f'📅 <b>Месячный отчёт</b>\n\nПользователей: {s["users"]}\nИсторий: {s["total"]}\nОпубликовано: {s["published"]}'
                    for aid in ADMIN_IDS:
                        try: await bot.send_message(aid,text,parse_mode='HTML')
                        except Exception: pass
                    mark_report_sent('monthly',key)
        except Exception as e:
            log_system_error('monitoring',str(e)); set_system_health('monitoring','error',str(e))
        await asyncio.sleep(30)


async def event_notifications(bot):
    while True:
        try:
            for aid in ADMIN_IDS:
                for row in get_complaints('new',20):
                    fp=f'complaint:{row["id"]}'
                    if create_event_notification_once(aid,'complaint','⚠️ Новая жалоба',f'Жалоба по истории #{row["story_id"]}',fp):
                        try: await bot.send_message(aid,f'⚠️ <b>Новая жалоба</b>\nИстория #{row["story_id"]}',parse_mode='HTML')
                        except Exception: pass
                for row in get_sla_breaches():
                    fp=f'sla:{row["id"]}:{row["first_response_due_at"]}'
                    if create_event_notification_once(aid,'sla','🔴 Нарушен SLA',fp,fp):
                        try: await bot.send_message(aid,f'🔴 <b>Нарушен SLA</b>\nДиалог #{row["id"]}',parse_mode='HTML')
                        except Exception: pass
        except Exception as e: log_system_error('event-notifications',str(e))
        await asyncio.sleep(60)


async def _init_db_with_retry():
    last_error = None
    for attempt in range(1, 6):
        try:
            init_db()
            ensure_platform_defaults()
            return
        except Exception as exc:
            last_error = exc
            logging.exception("DB startup attempt %s/5 failed", attempt)
            await asyncio.sleep(min(10, attempt * 2))
    raise RuntimeError(f"PostgreSQL/Alembic startup failed: {last_error}") from last_error


async def main():
    if not MODERATOR_BOT_TOKEN:
        raise RuntimeError('MODERATOR_BOT_TOKEN не задан. Создай второго Telegram-бота и добавь его токен в Railway.')
    bot = Bot(MODERATOR_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(moderator_entry_router)
    dp.include_router(callback_router)
    dp.include_router(router)

    # Start the HTTP health endpoint before database migrations. This prevents
    # Railway from seeing a dead deployment while PostgreSQL/Alembic is booting.
    web_runner = await start_admin_web(bot)
    tasks = []
    try:
        await _init_db_with_retry()
        print(f'🗄️ DB backend: {"PostgreSQL" if DATABASE_URL else "SQLite"}')
        print(f'🔴 Redis: {"подключён" if REDIS_URL else "не задан"}')
        tasks = [
            asyncio.create_task(scheduler(bot)),
            asyncio.create_task(repost_worker(bot)),
            asyncio.create_task(reports_and_monitoring(bot)),
            asyncio.create_task(event_notifications(bot)),
        ]
        print('🛡 Бот сотрудников запущен. DB=PostgreSQL; backups=automatic')
        await dp.start_polling(bot)
    finally:
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await web_runner.cleanup()
        await bot.session.close()


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,stream=sys.stdout)
    asyncio.run(main())
