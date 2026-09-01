from aiogram import Router, F
from aiogram.types import CallbackQuery

from config import ADMIN_IDS, CHANNEL_ID
from database import (
    get_story, get_latest_safety_decision, publish_story, reject_story, get_story_reaction_counts,
    set_story_reaction, get_user_story_reaction, lock_story, get_story_lock,
    is_admin_active,
    unlock_story, update_story_content, log_admin_action, get_admin_role, record_kpi_event,
)
from keyboards import moderation_keyboard, channel_story_keyboard

callback_router = Router()


def get_channel_message_link(bot, message_id: int) -> str | None:
    """Build a Telegram channel message link for public or private channels."""
    try:
        raw = str(CHANNEL_ID)
        if raw.startswith("-100"):
            return f"https://t.me/c/{raw[4:]}/{message_id}"
        return None
    except Exception:
        return None


@callback_router.callback_query(F.data.startswith("story:publish:"))
async def publish_callback(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS or not is_admin_active(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True)
        return
    story_id = int(query.data.rsplit(":", 1)[1])
    story = get_story(story_id)
    if not story:
        await query.answer("История не найдена", show_alert=True); return
    try:
        safety = get_latest_safety_decision(story_id)
        role = get_admin_role(query.from_user.id)
        if safety and safety.get("recommendation") != "publish" and role != "owner":
            await query.answer("Нужна ручная safety-проверка. Владелец может сделать override.", show_alert=True)
            return
        sent = await query.bot.send_message(CHANNEL_ID, story["post_text"] or story["text"])
        publish_story(story_id, sent.message_id)
        record_kpi_event(query.from_user.id, 'publish', max(0, int((__import__('time').time()) - story['created_at'].timestamp())) if hasattr(story['created_at'], 'timestamp') else 0)
        link = get_channel_message_link(query.bot, sent.message_id)
        await query.message.edit_reply_markup(reply_markup=channel_story_keyboard(story_id, link, get_story_reaction_counts(story_id)))
        await query.answer("Опубликовано")
        await query.message.edit_text((query.message.text or "") + "\n\n✅ ОПУБЛИКОВАНО", reply_markup=None)
        log_admin_action(query.from_user.id, "publish", story_id=story_id, user_id=story["user_id"])
    except Exception as exc:
        await query.answer(f"Ошибка: {exc}", show_alert=True)


@callback_router.callback_query(F.data.startswith("story:reject:"))
async def reject_callback(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS or not is_admin_active(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True); return
    story_id = int(query.data.rsplit(":", 1)[1])
    story = get_story(story_id)
    if not story:
        await query.answer("История не найдена", show_alert=True); return
    reject_story(story_id, "Отклонено модератором")
    record_kpi_event(query.from_user.id, 'reject', max(0, int((__import__('time').time()) - story['created_at'].timestamp())) if hasattr(story['created_at'], 'timestamp') else 0)
    await query.answer("История отклонена")
    await query.message.edit_text((query.message.text or "") + "\n\n❌ ОТКЛОНЕНО", reply_markup=None)
    log_admin_action(query.from_user.id, "reject", story_id=story_id, user_id=story["user_id"])


@callback_router.callback_query(F.data.startswith("story:lock:"))
async def lock_callback(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS or not is_admin_active(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True); return
    story_id = int(query.data.rsplit(":", 1)[1])
    row = lock_story(story_id, query.from_user.id)
    if row and int(row["admin_id"]) != int(query.from_user.id):
        await query.answer(f"Историю уже редактирует {row['admin_id']}", show_alert=True); return
    await query.answer("История заблокирована за вами")


@callback_router.callback_query(F.data.startswith("story:ai:"))
async def ai_callback(query: CallbackQuery):
    if query.from_user.id not in ADMIN_IDS or not is_admin_active(query.from_user.id):
        await query.answer("Нет доступа", show_alert=True); return
    await query.answer("ИИ-проверка запускается из Mini App", show_alert=True)


@callback_router.callback_query(F.data.startswith("react:"))
async def reaction_callback(query: CallbackQuery):
    parts = query.data.split(":")
    story_id = int(parts[1]); reaction = parts[2]
    current = get_user_story_reaction(story_id, query.from_user.id)
    set_story_reaction(story_id, query.from_user.id, None if current == reaction else reaction)
    counts = get_story_reaction_counts(story_id)
    await query.message.edit_reply_markup(reply_markup=channel_story_keyboard(story_id, None, counts))
    await query.answer("Готово")

