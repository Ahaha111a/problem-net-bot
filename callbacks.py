from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS

from database import (
    get_story,
    update_post,
    publish_story,
    reject_story,
)

from states import StoryState


callback_router = Router()


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_admin(
    callback: CallbackQuery,
) -> bool:

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ У вас нет доступа.",
            show_alert=True,
        )
        return False

    return True


# =========================================================
# ОПУБЛИКОВАТЬ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("publish:")
)
async def publish_handler(
    callback: CallbackQuery,
):

    if not await check_admin(callback):
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

    if story is None:

        await callback.answer(
            "❌ История не найдена.",
            show_alert=True,
        )
        return

    post_text = story["post_text"]

    if not post_text:

        await callback.answer(
            "❌ Готовый пост отсутствует.",
            show_alert=True,
        )
        return

    try:

        await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text=post_text,
        )

        publish_story(story_id)

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

        await callback.answer(
            "✅ Опубликовано!"
        )

    except Exception as error:

        print(
            f"PUBLISH ERROR: {error}"
        )

        await callback.answer(
            "❌ Ошибка публикации.",
            show_alert=True,
        )


# =========================================================
# ОТКЛОНИТЬ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("reject:")
)
async def reject_handler(
    callback: CallbackQuery,
):

    if not await check_admin(callback):
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

    if story is None:

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

    except Exception as error:

        print(
            f"REJECT ERROR: {error}"
        )

        await callback.answer(
            "❌ Ошибка при отклонении.",
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

    if not await check_admin(callback):
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

    if story is None:

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
        "Отправьте новый текст поста."
    )


# =========================================================
# СОХРАНЕНИЕ РЕДАКТИРОВАНИЯ
# =========================================================

@callback_router.message(
    StoryState.waiting_for_edit
)
async def save_edited_post(
    message: Message,
    state: FSMContext,
):

    if not is_admin(
        message.from_user.id
    ):
        await state.clear()

        await message.answer(
            "⛔ У вас нет доступа."
        )

        return

    new_text = message.text

    if not new_text:

        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )

        return

    data = await state.get_data()

    story_id = data.get(
        "editing_story_id"
    )

    if not story_id:

        await state.clear()

        await message.answer(
            "❌ История не определена."
        )

        return

    try:

        update_post(
            story_id,
            new_text,
        )

        await state.clear()

        await message.answer(
            f"✅ Пост истории #{story_id} "
            "успешно изменён."
        )

    except Exception as error:

        print(
            f"EDIT ERROR: {error}"
        )

        await message.answer(
            "❌ Не удалось сохранить изменения."
        )


# =========================================================
# НАПИСАТЬ ПОЛЬЗОВАТЕЛЮ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("contact:")
)
async def contact_user_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not await check_admin(callback):
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

    if story is None:

        await callback.answer(
            "❌ История не найдена.",
            show_alert=True,
        )
        return

    # sqlite3.Row нужно читать через ["поле"],
    # а не через .get()
    user_id = story["user_id"]

    if not user_id:

        await callback.answer(
            "❌ ID пользователя не найден.",
            show_alert=True,
        )
        return

    await state.update_data(
        contact_user_id=user_id,
        contact_story_id=story_id,
    )

    await state.set_state(
        StoryState.waiting_for_contact_message
    )

    await callback.answer()

    await callback.message.answer(
        f"👤 <b>Сообщение пользователю</b>\n\n"
        f"История #{story_id}\n\n"
        "Напишите сообщение, которое хотите "
        "отправить автору истории.",
        parse_mode="HTML",
    )


# =========================================================
# ОТПРАВИТЬ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ
# =========================================================

@callback_router.message(
    StoryState.waiting_for_contact_message
)
async def send_contact_message(
    message: Message,
    state: FSMContext,
):

    if not is_admin(
        message.from_user.id
    ):
        await state.clear()

        await message.answer(
            "⛔ У вас нет доступа."
        )

        return

    if not message.text:

        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )

        return

    data = await state.get_data()

    user_id = data.get(
        "contact_user_id"
    )

    story_id = data.get(
        "contact_story_id"
    )

    if not user_id:

        await state.clear()

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    try:

        await message.bot.send_message(
            chat_id=user_id,
            text=(
                "💬 Сообщение от команды "
                "«Проблем нет»:\n\n"
                f"{message.text}"
            ),
        )

        await state.clear()

        await message.answer(
            f"✅ Сообщение отправлено пользователю.\n\n"
            f"История #{story_id}"
        )

    except Exception as error:

        print(
            f"CONTACT USER ERROR: {error}"
        )

        await state.clear()

        await message.answer(
            "❌ Не удалось отправить сообщение.\n\n"
            "Возможно, пользователь заблокировал бота "
            "или ещё не начал с ним диалог."
        )
