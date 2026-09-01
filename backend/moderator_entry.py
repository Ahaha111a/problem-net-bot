from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardRemove

from config import ADMIN_IDS
from database import is_admin_active, get_stats, get_waiting_stories, get_all_stories
from keyboards import admin_keyboard, moderation_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS and is_admin_active(user_id)


@router.message(F.text == "/start")
async def start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Этот бот предназначен для сотрудников проекта.")
        return
    # Clear any stale persistent keyboard from the old user-facing menu first.
    await message.answer("🧹", reply_markup=ReplyKeyboardRemove())
    await message.answer("🛡 <b>Панель сотрудников</b>\n\nВыберите нужный раздел.", reply_markup=admin_keyboard())


@router.message(F.text == "🖥 Админ-панель")
async def admin_app(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🖥 Откройте Mini App через кнопку выше.", reply_markup=admin_keyboard())


@router.message(F.text == "⏳ Модерация")
async def moderation(message: Message):
    if not is_admin(message.from_user.id):
        return
    rows = get_waiting_stories()
    if not rows:
        await message.answer("🟢 Историй на модерации нет.")
        return
    for story in rows[:20]:
        await message.answer(
            f"📥 <b>История #{story['id']}</b>\n\n{story['text']}",
            reply_markup=moderation_keyboard(story['id']),
        )


@router.message(F.text == "📊 Статистика")
async def stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    s = get_stats()
    await message.answer(
        f"📊 <b>Статистика</b>\n\n"
        f"Всего историй: {s['total']}\n"
        f"На модерации: {s['waiting']}\n"
        f"Опубликовано: {s['published']}\n"
        f"Отклонено: {s['rejected']}"
    )


@router.message(F.text == "📁 Все истории")
async def all_stories(message: Message):
    if not is_admin(message.from_user.id):
        return
    rows = get_all_stories()[:20]
    if not rows:
        await message.answer("📁 Историй пока нет.")
        return
    await message.answer(
        "📁 <b>Последние истории</b>\n\n"
        + "\n".join(f"#{r['id']} — {r['status']}" for r in rows)
    )
