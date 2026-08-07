import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database import get_all_stories, get_stats, get_story_by_id
from keyboards import admin_keyboard, main_keyboard, moderation_keyboard
from states import StoryState

logger = logging.getLogger(__name__)
moderation_router = Router()


# ====================== АДМИН-ПАНЕЛЬ (без скрытия) ======================
@moderation_router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(message: types.Message, state: FSMContext):
    await message.answer("Выбери действие:", reply_markup=admin_keyboard)


@moderation_router.message(F.text == "📊 Статистика")
async def admin_stats(message: types.Message):
    stats = await get_stats()
    text = (
        f"📊 Статистика бота:\n\n"
        f"Всего историй: {stats['total']}\n"
        f"Опубликовано: {stats['published']}\n"
        f"Отклонено: {stats['rejected']}\n"
        f"Оживает модерации: {stats['waiting']}"
    )
    await message.answer(text)


@moderation_router.message(F.text == "⏳ Модерация")
async def moderation_start(message: types.Message):
    stories = await get_all_stories()
    if not stories:
        await message.answer("Нет историй на модерации.")
        return

    for story in stories:
        if story["status"] == "waiting":
            story_text = story["text"]
            if len(story_text) > 300:
                story_text = story_text[:300] + "..."
            await message.answer(
                f"📖 История #{story['id']} — Пользователь: {story['user_id']}\n\n{story_text}\n\n"
                f"Выбери действие:",
                reply_markup=moderation_keyboard(story["id"])
            )


@moderation_router.message(F.text == "⬅️ Назад")
async def admin_back(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_keyboard)
