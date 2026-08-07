from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, CHANNEL_ID

from database import (
    get_story,
    update_post,
    publish_story,
    reject_story,
)

from states import StoryState

from keyboards import moderation_keyboard


callback_router = Router()


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# ОПУБЛИКОВАТЬ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("publish:")
)
async def publish_handler(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа.",
            show_alert=True,
        )
        return

    try:
        story_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный ID истории.",
            show_alert=True,
        )
        return

    story = get_story(story_id)

    if not story:
        await callback.answer(
            "❌ История не найдена.",
            show_alert=True,
        )
        return

    post_text = story["post_text"]

    if not post_text:
        await callback.answer(
            "❌ У истории нет готового поста.",
            show_alert=True,
        )
        return

    try:

        await callback.bot.send_message(
            chat_id=CHANNEL_ID,
            text=post_text,
        )

        publish_story(story_id)

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        await callback.answer(
            "✅ История опубликована!"
        )

        await callback.message.answer(
            f"✅ История #{story_id} опубликована в канале."
        )

    except Exception as error:

        print(
            f"PUBLISH ERROR: {error}"
        )

        await callback.answer(
            "❌ Не удалось опубликовать историю.",
            show_alert=True,
        )


# =========================================================
# ОТКЛОНИТЬ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("reject:")
)
async def reject_handler(
    callback: CallbackQuery
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа.",
            show_alert=True,
        )
        return

    try:
        story_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный ID истории.",
            show_alert=True,
        )
        return

    story = get_story(story_id)

    if not story:
        await callback.answer(
            "❌ История не найдена.",
            show_alert=True,
        )
        return

    try:

        reject_story(story_id)

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        await callback.answer(
            "❌ История отклонена."
        )

        await callback.message.answer(
            f"❌ История #{story_id} отклонена."
        )

    except Exception as error:

        print(
            f"REJECT ERROR: {error}"
        )

        await callback.answer(
            "❌ Не удалось отклонить историю.",
            show_alert=True,
        )


# =========================================================
# НАЧАТЬ РЕДАКТИРОВАНИЕ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("edit:")
)
async def edit_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Нет доступа.",
            show_alert=True,
        )
        return

    try:
        story_id = int(
            callback.data.split(":")[1]
        )
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный ID истории.",
            show_alert=True,
        )
        return

    story = get_story(story_id)

    if not story:
        await callback.answer(
            "❌ История не найдена.",
            show_alert=True,
        )
        return

    await state.update_data(
        editing_story_id=story_id
    )

    await state.set_state(
        StoryState.waiting_for_edit
    )

    await callback.answer()

    await callback.message.answer(
        f"✏️ Редактирование истории #{story_id}\n\n"
        "Отправь новый текст готового поста."
    )


# =========================================================
# СОХРАНЕНИЕ ОТРЕДАКТИРОВАННОГО ПОСТА
# =========================================================

@callback_router.message(
    StoryState.waiting_for_edit
)
async def save_edited_post(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):
        await state.clear()
        return

    new_text = message.text

    if not new_text:
        await message.answer(
            "❗ Отправь текстовое сообщение."
        )
        return

    data = await state.get_data()

    story_id = data.get(
        "editing_story_id"
    )

    if not story_id:
        await state.clear()

        await message.answer(
            "❌ Не удалось определить историю."
        )

        return

    story = get_story(story_id)

    if not story:
        await state.clear()

        await message.answer(
            "❌ История не найдена."
        )

        return

    try:

        update_post(
            story_id,
            new_text,
        )

        await state.clear()

        await message.answer(
            f"✅ Пост истории #{story_id} обновлён.\n\n"
            "Теперь его можно опубликовать."
        )

        # Показываем администратору обновлённый пост
        await message.answer(
            f"📌 <b>Новый вариант поста:</b>\n\n"
            f"{new_text}",
            parse_mode="HTML",
            reply_markup=moderation_keyboard(
                story_id
            ),
        )

    except Exception as error:

        print(
            f"EDIT ERROR: {error}"
        )

        await message.answer(
            "❌ Не удалось сохранить изменения."
        )
