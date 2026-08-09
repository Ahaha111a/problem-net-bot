from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS

from database import (
    get_story,
    update_post,
    publish_story,
    reject_story,

    get_dialog,
    get_dialog_messages,
    get_open_dialog_by_user,
    add_support_message,
    assign_dialog,
    close_dialog,
    mark_dialog_read_by_admin,
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

        try:

            await callback.bot.send_message(
                chat_id=story["user_id"],
                text=(
                    "🎉 Ваша история была опубликована!\n\n"
                    "Спасибо, что поделились ей с нами 💙"
                ),
            )

        except Exception as error:

            print(
                f"USER NOTIFICATION ERROR: {error}"
            )

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

        try:

            await callback.bot.send_message(
                chat_id=story["user_id"],
                text=(
                    "ℹ️ Спасибо, что поделились своей историей.\n\n"
                    "К сожалению, сейчас она не может быть опубликована."
                ),
            )

        except Exception as error:

            print(
                f"USER NOTIFICATION ERROR: {error}"
            )

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

    if not is_admin(message.from_user.id):

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
# НАПИСАТЬ ПОЛЬЗОВАТЕЛЮ ПО ИСТОРИИ
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

    if not is_admin(message.from_user.id):

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
                "💬 Сообщение от команды:\n\n"
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


# =========================================================
# ОТВЕТ НА ЗАПРОС ЭКСТРЕННОЙ ПОДДЕРЖКИ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("support_reply:")
)
async def support_reply_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not await check_admin(callback):
        return

    try:

        user_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Некорректный ID пользователя.",
            show_alert=True,
        )

        return

    await state.update_data(
        support_user_id=user_id
    )

    await state.set_state(
        StoryState.waiting_for_support_reply
    )

    await callback.answer()

    await callback.message.answer(
        f"💬 <b>Ответ пользователю</b>\n\n"
        f"👤 User ID: <code>{user_id}</code>\n\n"
        "Напишите сообщение, которое хотите "
        "отправить пользователю.",
        parse_mode="HTML",
    )


# =========================================================
# ОТПРАВИТЬ ОТВЕТ ПОЛЬЗОВАТЕЛЮ
# =========================================================

@callback_router.message(
    StoryState.waiting_for_support_reply
)
async def send_support_reply(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

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
        "support_user_id"
    )

    if not user_id:

        await state.clear()

        await message.answer(
            "❌ Пользователь не определён."
        )

        return

    try:

        await message.bot.send_message(
            chat_id=user_id,
            text=(
                "💙 Сообщение от модератора:\n\n"
                f"{message.text}"
            ),
        )

        await state.clear()

        await message.answer(
            "✅ Ответ отправлен пользователю."
        )

    except Exception as error:

        print(
            f"SUPPORT REPLY ERROR: {error}"
        )

        await state.clear()

        await message.answer(
            "❌ Не удалось отправить ответ.\n\n"
            "Возможно, пользователь заблокировал бота."
        )


# =========================================================
# ОТКРЫТЬ ДИАЛОГ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("dialog_open:")
)
async def dialog_open_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not await check_admin(callback):
        return

    try:

        dialog_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Некорректный ID диалога.",
            show_alert=True,
        )

        return

    dialog = get_dialog(dialog_id)

    if dialog is None:

        await callback.answer(
            "❌ Диалог не найден.",
            show_alert=True,
        )

        return

    if dialog["status"] != "open":

        await callback.answer(
            "ℹ️ Этот диалог уже закрыт.",
            show_alert=True,
        )

        return

    # Открытие диалога автоматически отмечает
    # сообщения пользователя как прочитанные.
    mark_dialog_read_by_admin(
        dialog_id
    )

    assign_dialog(
        dialog_id,
        callback.from_user.id,
    )

    await state.update_data(
        moderator_dialog_id=dialog_id
    )

    await state.set_state(
        StoryState.moderator_dialog
    )

    messages = get_dialog_messages(
        dialog_id
    )

    text = (
        f"💬 <b>Диалог #{dialog_id}</b>\n\n"
        f"👤 User ID: "
        f"<code>{dialog['user_id']}</code>\n\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    for item in messages:

        if item["sender_type"] == "user":

            prefix = "👤 Пользователь"

        else:

            prefix = "👨‍💼 Модератор"

        text += (
            f"<b>{prefix}</b>\n"
            f"{item['text']}\n\n"
        )

    from keyboards import support_dialog_keyboard

    await callback.answer()

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_dialog_keyboard(
            dialog_id
        ),
    )


# =========================================================
# ВЫЙТИ ИЗ ДИАЛОГА
# =========================================================

@callback_router.callback_query(
    F.data.startswith("dialog_exit:")
)
async def dialog_exit_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not await check_admin(callback):
        return

    await state.clear()

    await callback.answer(
        "↩️ Вы вышли из диалога."
    )

    await callback.message.answer(
        "💬 Вы вышли из текущего диалога.\n\n"
        "Сам диалог остаётся открытым.\n"
        "Новые сообщения пользователя продолжат "
        "поступать в систему.\n\n"
        "Открыть его снова можно через "
        "раздел «💬 Диалоги»."
    )


# =========================================================
# ЗАКРЫТЬ ДИАЛОГ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("dialog_close:")
)
async def dialog_close_handler(
    callback: CallbackQuery,
    state: FSMContext,
):

    if not await check_admin(callback):
        return

    try:

        dialog_id = int(
            callback.data.split(":")[1]
        )

    except (ValueError, IndexError):

        await callback.answer(
            "❌ Некорректный ID диалога.",
            show_alert=True,
        )

        return

    dialog = get_dialog(dialog_id)

    if dialog is None:

        await callback.answer(
            "❌ Диалог не найден.",
            show_alert=True,
        )

        return

    close_dialog(
        dialog_id
    )

    if dialog["user_id"]:

        try:

            await callback.bot.send_message(
                chat_id=dialog["user_id"],
                text=(
                    "💙 Диалог с поддержкой завершён.\n\n"
                    "Спасибо, что обратились к нам.\n\n"
                    "Если вам снова понадобится помощь, "
                    "вы можете начать новый диалог через "
                    "«🆘 Экстренная поддержка»."
                ),
            )

        except Exception as error:

            print(
                f"DIALOG CLOSE USER ERROR: {error}"
            )

    await state.clear()

    await callback.message.edit_reply_markup(
        reply_markup=None
    )

    await callback.answer(
        f"🔴 Диалог #{dialog_id} закрыт."
    )


# =========================================================
# СООБЩЕНИЕ МОДЕРАТОРА В ДИАЛОГЕ
# =========================================================

@callback_router.message(
    StoryState.moderator_dialog
)
async def moderator_dialog_message(
    message: Message,
    state: FSMContext,
):

    if not is_admin(message.from_user.id):

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

    dialog_id = data.get(
        "moderator_dialog_id"
    )

    if not dialog_id:

        await state.clear()

        await message.answer(
            "❌ Диалог не определён."
        )

        return

    dialog = get_dialog(
        dialog_id
    )

    if dialog is None or dialog["status"] != "open":

        await state.clear()

        await message.answer(
            "❌ Диалог уже закрыт."
        )

        return

    user_id = dialog["user_id"]

    add_support_message(
        dialog_id=dialog_id,
        sender_id=message.from_user.id,
        sender_type="admin",
        text=message.text,
    )

    try:

        await message.bot.send_message(
            chat_id=user_id,
            text=(
                "💙 <b>Сообщение от модератора:</b>\n\n"
                f"{message.text}"
            ),
            parse_mode="HTML",
        )

        await message.answer(
            "✅ Сообщение отправлено."
        )

    except Exception as error:

        print(
            f"MODERATOR DIALOG SEND ERROR: {error}"
        )

        await message.answer(
            "❌ Не удалось отправить сообщение пользователю."
        )
