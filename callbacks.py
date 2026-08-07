from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from states import StoryState
from database import get_post, publish_story
from config import CHANNEL_ID


router = Router()


@router.callback_query(F.data.startswith("publish:"))
async def publish_callback(callback: CallbackQuery):

    story_id = int(
        callback.data.split(":")[1]
    )

    post_text = get_post(story_id)

    if not post_text:
        await callback.answer(
            "❌ Пост не найден",
            show_alert=True
        )
        return

    if len(post_text.strip()) < 50:
        await callback.answer(
            "❌ Пост слишком короткий",
            show_alert=True
        )
        return

    await callback.bot.send_message(
        CHANNEL_ID,
        post_text
    )

    publish_story(story_id)

    await callback.message.answer(
        "✅ Пост опубликован в канал"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("reject:"))
async def reject_callback(callback: CallbackQuery):

    story_id = int(
        callback.data.split(":")[1]
    )

    await callback.message.answer(
        f"❌ История #{story_id} отклонена"
    )

    await callback.answer()


@router.callback_query(F.data.startswith("edit:"))
async def edit_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    story_id = int(
        callback.data.split(":")[1]
    )

    await state.update_data(
        edit_story_id=story_id
    )

    await state.set_state(
        StoryState.waiting_for_edit
    )

    await callback.message.answer(
        "✏️ Отправьте новый текст поста."
    )

    await callback.answer()
