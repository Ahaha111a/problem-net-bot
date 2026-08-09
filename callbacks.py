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
    material_actions_keyboard,
    admin_keyboard,
)


callback_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_admin(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ У вас нет доступа.",
            show_alert=True,
        )
        return False

    return True


async def send_personal_request_to_admins(
    bot,
    dialog_id: int,
    user_id: int,
):
    if not request_personal_contact(dialog_id):
        return False

    text = (
        "📞 <b>ЗАПРОС НА ЛИЧНЫЙ КОНТАКТ</b>\n\n"
        f"💬 Диалог #{dialog_id}\n"
        f"👤 User ID: <code>{user_id}</code>\n\n"
        "Пользователь хочет связаться с сотрудником поддержки."
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=personal_request_keyboard(
                    dialog_id,
                    user_id,
                ),
                parse_mode="HTML",
            )
        except Exception as error:
            print(f"PERSONAL REQUEST ERROR: {error}")

    return True


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
        "Сообщение увидит сотрудник поддержки.",
        parse_mode="HTML",
    )


@callback_router.callback_query(
    F.data == "support_method:personal"
)
async def support_method_personal(
    callback: CallbackQuery,
    state: FSMContext,
):
    user_id = callback.from_user.id

    dialog = get_open_dialog_by_user(user_id)

    if dialog:
        dialog_id = dialog["id"]
    else:
        dialog_id = create_support_dialog(
            user_id,
            "Пользователь запросил личный контакт с сотрудником поддержки.",
        )

    await send_personal_request_to_admins(
        callback.bot,
        dialog_id,
        user_id,
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
        "Сотрудник поддержки получил запрос на личный контакт.\n\n"
        "💬 Диалог в боте остаётся открытым.",
        parse_mode="HTML",
    )


@callback_router.callback_query(
    F.data == "support_personal_request"
)
async def support_personal_request(
    callback: CallbackQuery,
):
    user_id = callback.from_user.id

    dialog = get_open_dialog_by_user(user_id)

    if dialog:
        dialog_id = dialog["id"]
    else:
        dialog_id = create_support_dialog(
            user_id,
            "Пользователь запросил личный контакт с сотрудником поддержки.",
        )

    new_request = await send_personal_request_to_admins(
        callback.bot,
        dialog_id,
        user_id,
    )

    await callback.answer(
        "📞 Запрос передан сотруднику."
        if new_request
        else "📞 Запрос уже находится у сотрудника."
    )


@callback_router.callback_query(
    F.data.startswith("publish:")
)
async def publish_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return

    try:
        story_id = int(callback.data.split(":", 1)[1])
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
            callback.message.chat.id,
            post_text,
        )

        publish_story(story_id)

        try:
            await callback.bot.send_message(
                story["user_id"],
                "🎉 Ваша история была опубликована!\n\n"
                "Спасибо, что поделились ей с нами 💙",
            )
        except Exception as error:
            print(f"USER NOTIFICATION ERROR: {error}")

        try:
            await callback.message.edit_reply_markup(
                reply_markup=None
            )
        except Exception:
            pass

        await callback.answer("✅ Опубликовано!")

    except Exception as error:
        print(f"PUBLISH ERROR: {error}")

        await callback.answer(
            "❌ Ошибка публикации.",
            show_alert=True,
        )


@callback_router.callback_query(
    F.data.startswith("reject:")
)
async def reject_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return

    try:
        story_id = int(callback.data.split(":", 1)[1])
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

    reject_story(story_id)

    try:
        await callback.bot.send_message(
            story["user_id"],
            "ℹ️ Спасибо, что поделились своей историей.\n\n"
            "К сожалению, сейчас она не может быть опубликована.",
        )
    except Exception as error:
        print(f"USER NOTIFICATION ERROR: {error}")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer("❌ История отклонена.")


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
        story_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer(
            "❌ Некорректный ID истории.",
            show_alert=True,
        )
        return

    if get_story(story_id) is None:
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
        f"✏️ <b>Редактирование истории #{story_id}</b>\n\n"
        "Отправьте новый текст поста.",
        parse_mode="HTML",
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
        return

    if not message.text:
        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )
        return

    data = await state.get_data()
    story_id = data.get("editing_story_id")

    if not story_id:
        await state.clear()
        await message.answer(
            "❌ История не определена."
        )
        return

    update_post(
        story_id,
        message.text,
    )

    await state.clear()

    await message.answer(
        f"✅ Пост истории #{story_id} изменён.",
        reply_markup=admin_keyboard,
    )


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
        story_id = int(callback.data.split(":", 1)[1])
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
        contact_user_id=story["user_id"],
        contact_story_id=story_id,
    )

    await state.set_state(
        StoryState.waiting_for_contact_message
    )

    await callback.answer()

    await callback.message.answer(
        f"👤 <b>Сообщение пользователю</b>\n\n"
        f"История #{story_id}\n\n"
        "Напишите сообщение автору истории.",
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
        return

    if not message.text:
        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )
        return

    data = await state.get_data()

    user_id = data.get("contact_user_id")
    story_id = data.get("contact_story_id")

    if not user_id:
        await state.clear()
        await message.answer(
            "❌ Пользователь не найден."
        )
        return

    try:
        await message.bot.send_message(
            user_id,
            "💬 <b>Сообщение от команды:</b>\n\n"
            f"{escape(message.text)}",
            parse_mode="HTML",
        )

        await state.clear()

        await message.answer(
            f"✅ Сообщение отправлено.\n\n"
            f"История #{story_id}",
            reply_markup=admin_keyboard,
        )

    except Exception as error:
        print(f"CONTACT ERROR: {error}")
        await state.clear()

        await message.answer(
            "❌ Не удалось отправить сообщение."
        )


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
        dialog_id = int(callback.data.split(":", 1)[1])
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
            "ℹ️ Диалог уже закрыт.",
            show_alert=True,
        )
        return

    current_admin = callback.from_user.id

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"] != current_admin
    ):
        await callback.answer(
            "👨‍💼 Диалог уже ведёт другой сотрудник.",
            show_alert=True,
        )
        return

    mark_dialog_read_by_admin(dialog_id)
    assign_dialog(dialog_id, current_admin)

    await state.update_data(
        moderator_dialog_id=dialog_id
    )

    await state.set_state(
        StoryState.moderator_dialog
    )

    messages = get_dialog_messages(dialog_id)

    statuses = {
        "new": "🔴 Новый",
        "in_progress": "🟡 В работе",
        "waiting_user": "🟠 Ожидает пользователя",
        "closed": "⚫ Закрыт",
    }

    status = statuses.get(
        dialog["support_status"],
        "📌 Неизвестный",
    )

    text = (
        f"💬 <b>Диалог #{dialog_id}</b>\n\n"
        f"👤 User ID: <code>{dialog['user_id']}</code>\n"
        f"📌 Статус: {status}\n"
        f"👨‍💼 Сотрудник: <code>{current_admin}</code>\n\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    for item in messages:
        prefix = (
            "👤 Пользователь"
            if item["sender_type"] == "user"
            else "👨‍💼 Сотрудник"
        )

        text += (
            f"<b>{prefix}</b>\n"
            f"{escape(item['text'])}\n\n"
        )

    await callback.answer()

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=support_dialog_keyboard(dialog_id),
    )


@callback_router.callback_query(
    F.data.startswith("dialog_waiting:")
)
async def dialog_waiting_handler(
    callback: CallbackQuery,
):
    if not await check_admin(callback):
        return

    try:
        dialog_id = int(callback.data.split(":", 1)[1])
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

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"] != callback.from_user.id
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
        "🟠 Ожидает пользователя."
    )


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
        dialog_id = int(callback.data.split(":", 1)[1])
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

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"] != callback.from_user.id
    ):
        await callback.answer(
            "⛔ Вы не ведёте этот диалог.",
            show_alert=True,
        )
        return

    unassign_dialog(dialog_id)
    await state.clear()

    await callback.answer(
        "↩️ Вы вышли из диалога."
    )

    await callback.message.answer(
        "💬 Вы вышли из текущего диалога.",
        reply_markup=admin_keyboard,
    )


@callback_router.callback_query(
    F.data.startswith("dialog_personal:")
)
async def dialog_personal_handler(
    callback: CallbackQuery,
):
    if not await check_admin(callback):
        return

    try:
        dialog_id = int(callback.data.split(":", 1)[1])
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

    user_id = dialog["user_id"]

    await callback.answer(
        "📞 Профиль пользователя готов."
    )

    await callback.message.answer(
        "📞 <b>Личный контакт</b>\n\n"
        f"Диалог #{dialog_id}\n"
        f"User ID: <code>{user_id}</code>",
        parse_mode="HTML",
        reply_markup=personal_request_keyboard(
            dialog_id,
            user_id,
        ),
    )

    try:
        await callback.bot.send_message(
            user_id,
            "📞 <b>Сотрудник поддержки получил ваш запрос.</b>\n\n"
            "Он может связаться с вами напрямую.",
            parse_mode="HTML",
        )
    except Exception as error:
        print(f"PERSONAL CONTACT ERROR: {error}")


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
        dialog_id = int(callback.data.split(":", 1)[1])
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

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"] != callback.from_user.id
    ):
        await callback.answer(
            "⛔ Диалог ведёт другой сотрудник.",
            show_alert=True,
        )
        return

    close_dialog(dialog_id)
    await state.clear()

    try:
        await callback.bot.send_message(
            dialog["user_id"],
            "💙 Диалог с поддержкой завершён.\n\n"
            "Если вам снова понадобится помощь, "
            "используйте «🆘 Экстренная поддержка».",
        )
    except Exception as error:
        print(f"DIALOG CLOSE ERROR: {error}")

    try:
        await callback.message.edit_reply_markup(
            reply_markup=None
        )
    except Exception:
        pass

    await callback.answer(
        "🔴 Диалог закрыт."
    )

    await callback.message.answer(
        "🔴 Диалог закрыт.",
        reply_markup=admin_keyboard,
    )


@callback_router.message(
    StoryState.moderator_dialog
)
async def moderator_dialog_message(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        await state.clear()
        return

    if not message.text:
        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )
        return

    data = await state.get_data()
    dialog_id = data.get("moderator_dialog_id")

    if not dialog_id:
        await state.clear()
        await message.answer(
            "❌ Диалог не определён."
        )
        return

    dialog = get_dialog(dialog_id)

    if dialog is None or dialog["status"] != "open":
        await state.clear()
        await message.answer(
            "❌ Диалог закрыт."
        )
        return

    if (
        dialog["assigned_admin_id"]
        and dialog["assigned_admin_id"] != message.from_user.id
    ):
        await state.clear()
        await message.answer(
            "⛔ Этот диалог ведёт другой сотрудник."
        )
        return

    add_support_message(
        dialog_id,
        message.from_user.id,
        "admin",
        message.text,
    )

    try:
        await message.bot.send_message(
            dialog["user_id"],
            "💙 <b>Сообщение от сотрудника поддержки:</b>\n\n"
            f"{escape(message.text)}",
            parse_mode="HTML",
        )

        await message.answer(
            "✅ Сообщение отправлено."
        )

    except Exception as error:
        print(f"MODERATOR SEND ERROR: {error}")

        await message.answer(
            "❌ Не удалось отправить сообщение."
        )


@callback_router.callback_query(
    F.data.startswith("material:")
)
async def material_handler(
    callback: CallbackQuery,
):
    material_key = callback.data.split(":", 1)[1]

    if material_key == "support":
        await callback.answer()

        await callback.message.answer(
            "🆘 Нажмите «🆘 Экстренная поддержка» "
            "в главном меню."
        )
        return

    from handlers import MATERIALS

    text = MATERIALS.get(material_key)

    if not text:
        await callback.answer(
            "❌ Материал не найден.",
            show_alert=True,
        )
        return

    await callback.answer()

    await callback.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=material_actions_keyboard(),
    )
