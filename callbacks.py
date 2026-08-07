import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from database import publish_story, reject_story, save_story, get_story_by_id
from keyboards import moderation_keyboard
from states import StoryState
from ai import generate_post

logger = logging.getLogger(__name__)
router = Router()


# ====================== ПУБЛИКАЦИЯ ======================
@router.callback_query(F.data.startswith("publish:"))
async def callback_publish(callback: CallbackQuery, state: FSMContext):
    await callback.answer("✅ Публикуем...")
    story_id = int(callback.data.split(":")[1])
    story = get_story_by_id(story_id)
    if not story:
        await callback.message.edit_text("❌ История не найдена")
        return
    post_text = await generate_post(story["text"])
    save_story(story_id, post_text=post_text)
    await callback.bot.send_message(config.channel_id, post_text, parse_mode="HTML")
    publish_story(story_id)
    try:
        await callback.message.edit_reply_markup()
    except:
        pass
    await callback.message.edit_text(f"✅ Опубликовано!\n\nID: {story_id}\nПросмотры: 0\nЛайки: 0")
    await state.clear()


# ====================== ИЗМЕНЕНИЕ ======================
@router.callback_query(F.data.startswith("edit:"))
async def callback_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer("✏️ Редактирование...")
    story_id = int(callback.data.split(":")[1])
    await callback.message.edit_text("✏️ Пришли новый текст истории.\n\nКогда закончишь — просто отправь его.\n\nЧтобы отменить — напиши /cancel")
    await state.set_state(StoryState.waiting_for_edit)
    await state.update_data(story_id=story_id)


@router.message(StoryState.waiting_for_edit)
async def handle_edit_text(message: Message, state: FSMContext):
    if message.text == "/cancel":
        await state.clear()
        await message.answer("❌ Редактирование отменено")
        return
    data = await state.get_data()
    story_id = data.get("story_id")
    if not story_id:
        await message.answer("❌ Ошибка")
        await state.clear()
        return
    new_post = await generate_post(message.text)
    save_story(story_id, post_text=new_post)
    await message.answer(f"✅ Редактирование завершено!\n\nНовая версия сохранена.\nID истории: {story_id}")
    await state.clear()


# ====================== ОТКЛОНЕНИЕ ======================
@router.callback_query(F.data.startswith("reject:"))
async def callback_reject(callback: CallbackQuery, state: FSMContext):
    await callback.answer("❌ Отклоняем...")
    story_id = int(callback.data.split(":")[1])
    reject_story(story_id)
    try:
        await callback.message.edit_reply_markup()
    except:
        pass
    await callback.message.edit_text(f"❌ История #{story_id} отклонена")
    await state.clear()
