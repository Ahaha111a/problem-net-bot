from aiogram import Router, F
from aiogram.types import CallbackQuery

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
async def edit_callback(callback: CallbackQuery):

    story_id = int(
        callback.data.split(":")[1]
    )


    await callback.message.answer(
        f"✏️ Редактирование истории #{story_id}\n\n"
        "Функция будет добавлена следующим шагом."
    )


    await callback.answer()
