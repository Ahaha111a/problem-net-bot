from html import escape

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
    unassign_dialog,
    close_dialog,
    mark_dialog_read_by_admin,
    set_dialog_status,
    request_personal_contact,
    create_support_dialog,
)

from states import StoryState

from keyboards import (
    support_dialog_keyboard,
    personal_request_keyboard,
)

callback_router = Router()


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(
    user_id: int,
) -> bool:

    return user_id in ADMIN_IDS


async def check_admin(
    callback: CallbackQuery,
) -> bool:

    if not is_admin(
        callback.from_user.id
    ):

        await callback.answer(
            "⛔ У вас нет доступа.",
            show_alert=True,
        )

        return False

    return True


# =========================================================
# ОТПРАВКА ЗАПРОСА АДМИНИСТРАТОРАМ
# =========================================================

async def send_personal_request_to_admins(
    bot,
    dialog_id: int,
    user_id: int,
):

    is_new_request = request_personal_contact(
        dialog_id
    )

    if not is_new_request:

        return False

    admin_text = (
        "📞 <b>ЗАПРОС НА ЛИЧНЫЙ КОНТАКТ</b>\n\n"
        f"💬 Диалог #{dialog_id}\n"
        f"👤 User ID: "
        f"<code>{user_id}</code>\n\n"
        "Пользователь хочет, чтобы "
        "сотрудник поддержки связался "
        "с ним лично."
    )

    for admin_id in ADMIN_IDS:

        try:

            await bot.send_message(
                admin_id,
                admin_text,
                reply_markup=personal_request_keyboard(
                    dialog_id,
                    user_id,
                ),
                parse_mode="HTML",
            )

        except Exception as error:

            print(
                f"PERSONAL REQUEST ADMIN ERROR: "
                f"{error}"
            )

    return True


# =========================================================
# ВЫБОР: ПРОДОЛЖИТЬ В БОТЕ
# =========================================================

@callback_router.callback_query(
    F.data == "support_method:bot"
)
async def support_method_bot(
    callback: CallbackQuery,
    state: FSMContext,
):

    await callback.answer()

    await state.set_state(
        StoryState.waiting_for_support_message
    )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    await callback.message.answer(
        "💬 <b>Продолжаем здесь</b>\n\n"
        "Напишите, что сейчас происходит.\n\n"
        "Сообщение увидит сотрудник поддержки.\n\n"
        "📞 В любой момент вы сможете "
        "попросить сотрудника связаться "
        "с вами лично.",
        parse_mode="HTML",
    )


# =========================================================
# ВЫБОР: ЛИЧНЫЙ КОНТАКТ
# =========================================================

@callback_router.callback_query(
    F.data == "support_method:personal"
)
async def support_method_personal(
    callback: CallbackQuery,
    state: FSMContext,
):

    user_id = callback.from_user.id

    dialog = get_open_dialog_by_user(
        user_id
    )

    if dialog:

        dialog_id = dialog["id"]

    else:

        dialog_id = create_support_dialog(
            user_id=user_id,
            first_message=(
                "Пользователь запросил "
                "личный контакт с сотрудником поддержки."
            ),
        )

    await send_personal_request_to_admins(
        bot=callback.bot,
        dialog_id=dialog_id,
        user_id=user_id,
    )

    await state.clear()

    await callback.answer(
        "📞 Запрос передан сотруднику."
    )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

    await callback.message.answer(
        "📞 <b>Запрос отправлен</b>\n\n"
        "Мы передали сотруднику поддержки "
        "запрос на личный контакт.\n\n"
        "Сотрудник сможет открыть ваш "
        "Telegram-профиль и написать вам напрямую.\n\n"
        "💬 Диалог в боте при этом остаётся открытым.",
        parse_mode="HTML",
    )


# =========================================================
# ЛИЧНЫЙ КОНТАКТ В ЛЮБОЙ МОМЕНТ
# =========================================================

@callback_router.callback_query(
    F.data == "support_personal_request"
)
async def support_personal_request(
    callback: CallbackQuery,
):

    user_id = callback.from_user.id

    dialog = get_open_dialog_by_user(
        user_id
    )

    if not dialog:

        dialog_id = create_support_dialog(
            user_id=user_id,
            first_message=(
                "Пользователь запросил "
                "личный контакт с сотрудником поддержки."
            ),
        )

    else:

        dialog_id = dialog["id"]

    is_new_request = await send_personal_request_to_admins(
        bot=callback.bot,
        dialog_id=dialog_id,
        user_id=user_id,
    )

    if is_new_request:

        await callback.answer(
            "📞 Запрос передан сотруднику."
        )

    else:

        await callback.answer(
            "📞 Запрос уже находится у сотрудника."
        )


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

    except (
        ValueError,
        IndexError,
    ):

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
                f"USER NOTIFICATION ERROR: "
                f"{error}"
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

    except (
        ValueError,
        IndexError,
    ):

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
                    "ℹ️ Спасибо, что поделились "
                    "своей историей.\n\n"
                    "К сожалению, сейчас она "
                    "не может быть опубликована."
                ),
            )

        except Exception as error:

            print(
                f"USER NOTIFICATION ERROR: "
                f"{error}"
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

    except (
        ValueError,
        IndexError,
    ):

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

    if not message.text:

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
            message.text,
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

    except (
        ValueError,
        IndexError,
    ):

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
                f"{escape(message.text)}"
            ),
            parse_mode="HTML",
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
            "❌ Не удалось отправить сообщение."
        )


# =========================================================
# СТАРЫЙ ОТВЕТ НА ПОДДЕРЖКУ
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

    except (
        ValueError,
        IndexError,
    ):

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
        f"👤 User ID: "
        f"<code>{user_id}</code>\n\n"
        "Напишите сообщение.",
        parse_mode="HTML",
    )


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
                f"{escape(message.text)}"
            ),
            parse_mode="HTML",
        )

        await state.clear()

        await message.answer(
            "✅ Ответ отправлен пользователю."
        )

    except Exception as error:

        print(
            f"SUPPORT REPLY ERROR: "
            f"{error}"
        )

        await state.clear()

        await message.answer(
            "❌ Не удалось отправить ответ."
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

    except (
        ValueError,
        IndexError,
    ):

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

    assigned_admin_id = (
        dialog["assigned_admin_id"]
    )

    current_admin_id = (
        callback.from_user.id
    )

    if (
        assigned_admin_id
        and assigned_admin_id != current_admin_id
    ):

        await callback.answer(
            "👨‍💼 Этот диалог уже взят "
            "другим сотрудником.",
            show_alert=True,
        )

        return

    mark_dialog_read_by_admin(
        dialog_id
    )

    assign_dialog(
        dialog_id,
        current_admin_id,
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

    support_status = (
        dialog["support_status"] or "new"
    )

    status_names = {
        "new": "🔴 Новый",
        "in_progress": "🟡 В работе",
        "waiting_user": "🟠 Ожидает пользователя",
        "closed": "⚫ Закрыт",
    }

    status_text = status_names.get(
        support_status,
        "📌 Неизвестный статус",
    )

    text = (
        f"💬 <b>Диалог #{dialog_id}</b>\n\n"
        f"👤 User ID: "
        f"<code>{dialog['user_id']}</code>\n"
        f"📌 Статус: {status_text}\n"
        f"👨‍💼 Сотрудник: "
        f"<code>{current_admin_id}</code>\n\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    for item in messages:

        if item["sender_type"] == "user":

            prefix = "👤 Пользователь"

        else:

            prefix = "👨‍💼 Сотрудник"

        text += (
            f"<b>{prefix}</b>\n"
            f"{escape(item['text'])}\n\n"
        )

    await callback.answer()

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_dialog_keyboard(
            dialog_id
        ),
    )


# =========================================================
# ОЖИДАЕТ ПОЛЬЗОВАТЕЛЯ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("dialog_waiting:")
)
async def dialog_waiting_handler(
    callback: CallbackQuery,
):

    if not await check_admin(callback):
        return

    try:

        dialog_id = int(
            callback.data.split(":")[1]
        )

    except (
        ValueError,
        IndexError,
    ):

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

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"]
        != callback.from_user.id
    ):

        await callback.answer(
            "⛔ Диалог ведёт другой сотрудник.",
            show_alert=True,
        )

        return

    set_dialog_status(
        dialog_id,
        "waiting_user",
    )

    await callback.answer(
        "🟠 Диалог отмечен как ожидающий пользователя."
    )

    await callback.message.answer(
        f"🟠 Диалог #{dialog_id} отмечен как "
        "«ожидает пользователя»."
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

    try:

        dialog_id = int(
            callback.data.split(":")[1]
        )

    except (
        ValueError,
        IndexError,
    ):

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

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"]
        != callback.from_user.id
    ):

        await callback.answer(
            "⛔ Вы не ведёте этот диалог.",
            show_alert=True,
        )

        return

    unassign_dialog(
        dialog_id
    )

    await state.clear()

    await callback.answer(
        "↩️ Вы вышли из диалога."
    )

    await callback.message.answer(
        "💬 Вы вышли из текущего диалога.\n\n"
        "Сам диалог остаётся открытым.\n"
        "Другой сотрудник сможет взять его в работу."
    )


# =========================================================
# ЛИЧНЫЙ КОНТАКТ МОДЕРАТОРА
# =========================================================

@callback_router.callback_query(
    F.data.startswith("dialog_personal:")
)
async def dialog_personal_handler(
    callback: CallbackQuery,
):

    if not await check_admin(callback):
        return

    try:

        dialog_id = int(
            callback.data.split(":")[1]
        )

    except (
        ValueError,
        IndexError,
    ):

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

    user_id = dialog["user_id"]

    await callback.answer(
        "📞 Профиль пользователя готов."
    )

    await callback.message.answer(
        "📞 <b>Личный контакт</b>\n\n"
        f"Диалог #{dialog_id}\n"
        f"User ID: <code>{user_id}</code>\n\n"
        "Нажмите кнопку ниже, чтобы открыть "
        "профиль пользователя и написать ему "
        "напрямую из своего Telegram.",
        parse_mode="HTML",
        reply_markup=personal_request_keyboard(
            dialog_id,
            user_id,
        ),
    )

    try:

        await callback.bot.send_message(
            chat_id=user_id,
            text=(
                "📞 <b>Сотрудник поддержки получил "
                "ваш запрос.</b>\n\n"
                "Он может связаться с вами "
                "напрямую в Telegram.\n\n"
                "💬 Диалог в боте остаётся открытым."
            ),
            parse_mode="HTML",
        )

    except Exception as error:

        print(
            f"PERSONAL CONTACT USER NOTIFY ERROR: "
            f"{error}"
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

    except (
        ValueError,
        IndexError,
    ):

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

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"]
        != callback.from_user.id
    ):

        await callback.answer(
            "⛔ Диалог ведёт другой сотрудник.",
            show_alert=True,
        )

        return

    close_dialog(
        dialog_id
    )

    await state.clear()

    try:

        await callback.bot.send_message(
            chat_id=dialog["user_id"],
            text=(
                "💙 Диалог с поддержкой завершён.\n\n"
                "Если вам снова понадобится помощь, "
                "вы можете нажать "
                "«🆘 Экстренная поддержка» "
                "или «📞 Связь с сотрудником»."
            ),
        )

    except Exception as error:

        print(
            f"DIALOG CLOSE USER ERROR: {error}"
        )

    try:

        await callback.message.edit_reply_markup(
            reply_markup=None
        )

    except Exception:
        pass

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

    dialog = get_dialog(dialog_id)

    if (
        dialog is None
        or dialog["status"] != "open"
    ):

        await state.clear()

        await message.answer(
            "❌ Диалог уже закрыт."
        )

        return

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"]
        != message.from_user.id
    ):

        await state.clear()

        await message.answer(
            "⛔ Этот диалог уже ведёт другой сотрудник."
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
                "💙 <b>Сообщение от сотрудника поддержки:</b>\n\n"
                f"{escape(message.text)}"
            ),
            parse_mode="HTML",
        )

        await message.answer(
            "✅ Сообщение отправлено."
        )

    except Exception as error:

        print(
            f"MODERATOR DIALOG SEND ERROR: "
            f"{error}"
        )

        await message.answer(
            "❌ Не удалось отправить сообщение "
            "пользователю."
        )


# =========================================================
# ПОЛЕЗНЫЕ МАТЕРИАЛЫ
# =========================================================

@callback_router.callback_query(
    F.data.startswith("material:")
)
async def material_handler(
    callback: CallbackQuery,
):

    material_key = callback.data.split(":", 1)[1]

    if material_key == "support":

        await callback.answer()

        try:
            await callback.message.answer(
                "🆘 Если вам сейчас нужна поддержка, "
                "нажмите кнопку «🆘 Экстренная поддержка» "
                "в главном меню."
            )
        except Exception:
            pass

        return

    from handlers import MATERIALS

    material_text = MATERIALS.get(
        material_key
    )

    if not material_text:

        await callback.answer(
            "❌ Материал не найден.",
            show_alert=True,
        )

        return

    await callback.answer()

    await callback.message.answer(
        material_text,
        parse_mode="HTML",
        reply_markup=material_actions_keyboard(),
    )
