from html import escape

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from config import ADMIN_IDS, CHANNEL_ID
from database import (
    get_story,
    update_post,
    update_ai_result,
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
    set_admin_control_message,
    get_admin_control_message,
    clear_admin_control_message,
    claim_story_for_publish,
    release_story_publish_claim,
    get_user_profile,
    register_user,
    toggle_story_favorite,
    set_ai_review,
)
from states import StoryState
from ai import analyze_story, review_story
from post_generator import create_post
from keyboards import (
    support_dialog_keyboard,
    personal_request_keyboard,
    material_actions_keyboard,
    admin_keyboard,
    moderation_keyboard,
    published_story_keyboard,
    moderation_cancel_keyboard,
    user_profile_keyboard,
)

callback_router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def check_admin(callback: CallbackQuery) -> bool:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ У вас нет доступа.", show_alert=True)
        return False
    return True


def get_id_from_callback(callback: CallbackQuery):
    try:
        return int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError, AttributeError):
        return None


async def safe_remove_keyboard(callback: CallbackQuery):
    try:
        if callback.message:
            await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


async def get_channel_message_link(bot, message_id: int):
    try:
        chat = await bot.get_chat(CHANNEL_ID)
        if chat.username:
            return f"https://t.me/{chat.username}/{message_id}"
        chat_id = str(chat.id)
        if chat_id.startswith("-100"):
            return f"https://t.me/c/{chat_id[4:]}/{message_id}"
    except Exception as error:
        print(f"CHANNEL LINK ERROR: {error}")
    return None


# =========================================================
# MODERATION CARD
# =========================================================


def story_card_text(story) -> str:
    status = story["status"] or "waiting"
    status_names = {
        "waiting": "⏳ На модерации",
        "publishing": "🟡 Публикуется…",
        "published": "✅ Опубликовано",
        "rejected": "❌ Отклонено",
    }
    ai_result = story["ai_result"] or "⚠️ Анализ пока отсутствует."
    post_text = story["post_text"] or "⚠️ Пост не подготовлен."
    reason = story["rejection_reason"] if "rejection_reason" in story.keys() else None
    reason_block = f"\n❗ <b>Причина отклонения:</b> {escape(reason)}\n" if reason else ""
    return (
        f"📥 <b>История #{story['id']}</b>\n\n"
        f"👤 User ID: <code>{story['user_id']}</code>\n"
        f"📌 Статус: {status_names.get(status, status)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💭 <b>История:</b>\n\n"
        f"{escape(story['text'])}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Анализ ИИ:</b>\n\n"
        f"{escape(ai_result)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📌 <b>Готовый пост:</b>\n\n"
        f"{escape(post_text)}"
        f"{reason_block}"
    )


async def refresh_story_card(message: Message, story_id: int):
    story = get_story(story_id)
    if not story:
        return
    try:
        await message.edit_text(
            story_card_text(story),
            parse_mode="HTML",
            reply_markup=(
                moderation_keyboard(story_id, story["user_id"])
                if story["status"] == "waiting"
                else None
            ),
        )
    except Exception as error:
        print(f"STORY CARD UPDATE ERROR: {error}")


# =========================================================
# SUPPORT CARD
# =========================================================


def dialog_card_text(dialog_id: int) -> str:
    dialog = get_dialog(dialog_id)
    if not dialog:
        return "❌ Диалог не найден."

    status_names = {
        "new": "🔴 Новый",
        "in_progress": "🟡 В работе",
        "waiting_user": "🟠 Ожидает пользователя",
        "resolved": "🟢 Решён",
        "closed": "⚫ Закрыт",
    }
    status = dialog["support_status"] or "new"
    messages = get_dialog_messages(dialog_id)

    text = (
        f"💬 <b>Диалог #{dialog_id}</b>\n\n"
        f"👤 User ID: <code>{dialog['user_id']}</code>\n"
        f"📌 Статус: {status_names.get(status, status)}\n"
        f"👨‍💼 Сотрудник: <code>{dialog['assigned_admin_id'] or 'не назначен'}</code>\n\n"
        "━━━━━━━━━━━━━━\n\n"
    )

    if not messages:
        return text + "Сообщений пока нет."

    for item in messages:
        prefix = "👤 Пользователь" if item["sender_type"] == "user" else "👨‍💼 Сотрудник"
        created = item["created_at"] or ""
        text += f"<b>{prefix}</b> <i>{escape(str(created))}</i>\n{escape(item['text'])}\n\n"

    return text


async def refresh_dialog_card(bot, dialog_id: int, chat_id: int | None = None, message_id: int | None = None):
    dialog = get_dialog(dialog_id)
    if not dialog:
        return None

    stored = get_admin_control_message(dialog_id)
    target_chat = chat_id or (stored["admin_control_chat_id"] if stored else None)
    target_message = message_id or (stored["admin_control_message_id"] if stored else None)

    if target_chat and target_message:
        try:
            await bot.edit_message_text(
                chat_id=target_chat,
                message_id=target_message,
                text=dialog_card_text(dialog_id),
                parse_mode="HTML",
                reply_markup=(
                    support_dialog_keyboard(dialog_id)
                    if dialog["status"] == "open"
                    else None
                ),
            )
            set_admin_control_message(dialog_id, target_chat, target_message)
            return target_message
        except Exception as error:
            print(f"DIALOG CARD EDIT ERROR: {error}")

    if target_chat:
        try:
            sent = await bot.send_message(
                target_chat,
                dialog_card_text(dialog_id),
                parse_mode="HTML",
                reply_markup=(
                    support_dialog_keyboard(dialog_id)
                    if dialog["status"] == "open"
                    else None
                ),
            )
            set_admin_control_message(dialog_id, target_chat, sent.message_id)
            return sent.message_id
        except Exception as error:
            print(f"DIALOG CARD SEND ERROR: {error}")
    return None


# =========================================================
# SUPPORT METHOD
# =========================================================

@callback_router.callback_query(F.data == "support_method:bot")
async def support_method_bot(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(StoryState.waiting_for_support_message)
    await safe_remove_keyboard(callback)
    await callback.message.answer(
        "💬 <b>Продолжаем здесь</b>\n\n"
        "Напишите, что сейчас происходит.\n\n"
        "Сообщение увидит сотрудник поддержки.\n\n"
        "Чтобы отменить — нажмите «⬅️ Назад»."
    )


@callback_router.callback_query(F.data == "support_method:personal")
async def support_method_personal(callback: CallbackQuery, state: FSMContext):
    register_user(callback.from_user.id)
    user_id = callback.from_user.id
    dialog = get_open_dialog_by_user(user_id)
    dialog_id = dialog["id"] if dialog else create_support_dialog(
        user_id, "Пользователь запросил личный контакт с сотрудником поддержки."
    )
    sent = await send_personal_request_to_admins(callback.bot, dialog_id, user_id)
    await state.clear()
    await safe_remove_keyboard(callback)
    await callback.answer("📞 Запрос передан сотруднику." if sent else "📞 Запрос уже находится у сотрудника.")
    await callback.message.answer(
        "📞 <b>Запрос отправлен</b>\n\nМы передали сотруднику поддержки запрос на личный контакт.",
        parse_mode="HTML",
    )


@callback_router.callback_query(F.data == "support_personal_request")
async def support_personal_request(callback: CallbackQuery):
    register_user(callback.from_user.id)
    user_id = callback.from_user.id
    dialog = get_open_dialog_by_user(user_id)
    dialog_id = dialog["id"] if dialog else create_support_dialog(
        user_id, "Пользователь запросил личный контакт с сотрудником поддержки."
    )
    new_request = await send_personal_request_to_admins(callback.bot, dialog_id, user_id)
    await callback.answer("📞 Запрос передан сотруднику." if new_request else "📞 Запрос уже находится у сотрудника.")


async def send_personal_request_to_admins(bot, dialog_id: int, user_id: int):
    new_request = request_personal_contact(dialog_id)
    if not new_request:
        return False
    text = (
        "📞 <b>ЗАПРОС НА ЛИЧНЫЙ КОНТАКТ</b>\n\n"
        f"💬 Диалог #{dialog_id}\n"
        f"👤 User ID: <code>{user_id}</code>\n\n"
        "Пользователь хочет, чтобы сотрудник связался с ним лично."
    )
    sent = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                text,
                reply_markup=personal_request_keyboard(dialog_id, user_id),
                parse_mode="HTML",
            )
            sent = True
        except Exception as error:
            print(f"PERSONAL REQUEST ERROR: {error}")
    return sent


# =========================================================
# STORIES — PUBLISH / REJECT / EDIT / AI / PREVIEW
# =========================================================

@callback_router.callback_query(F.data.startswith("publish:"))
async def publish_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return

    story_id = get_id_from_callback(callback)
    story = get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True)
        return

    if story["status"] != "waiting":
        await callback.answer("ℹ️ История уже обрабатывается или обработана.", show_alert=True)
        return

    if not claim_story_for_publish(story_id):
        await callback.answer("⏳ Историю уже обрабатывает другой администратор.", show_alert=True)
        return

    await callback.answer("📤 Публикую…")
    try:
        story = get_story(story_id)
        post_text = story["post_text"] or ""
        if not post_text.strip():
            release_story_publish_claim(story_id)
            await callback.answer("❌ Готовый пост отсутствует.", show_alert=True)
            return

        sent = await callback.bot.send_message(CHANNEL_ID, post_text)
        publish_story(story_id, sent.message_id)
        link = await get_channel_message_link(callback.bot, sent.message_id)

        try:
            if link:
                await callback.bot.send_message(
                    story["user_id"],
                    "🎉 <b>Ваша история была опубликована!</b>\n\nСпасибо, что поделились ей с нами 💙",
                    parse_mode="HTML",
                    reply_markup=published_story_keyboard(link),
                )
            else:
                await callback.bot.send_message(
                    story["user_id"],
                    "🎉 <b>Ваша история была опубликована!</b>\n\nСпасибо, что поделились ей с нами 💙",
                    parse_mode="HTML",
                )
        except Exception as error:
            print(f"USER PUBLISH NOTIFY ERROR: {error}")

        await refresh_story_card(callback.message, story_id)
        await callback.answer("✅ История опубликована.")
    except Exception as error:
        print(f"PUBLISH ERROR: {error}")
        release_story_publish_claim(story_id)
        await callback.answer("❌ Не удалось опубликовать историю. Статус возвращён на модерацию.", show_alert=True)


@callback_router.callback_query(F.data.startswith("reject:"))
async def reject_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    story = get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(
        rejecting_story_id=story_id,
        moderation_message_id=callback.message.message_id,
        moderation_chat_id=callback.message.chat.id,
    )
    await state.set_state(StoryState.waiting_for_reject_reason)
    await callback.answer()
    await callback.message.edit_text(
        f"❌ <b>Отклонение истории #{story_id}</b>\n\n"
        "Напишите причину отказа следующим сообщением.\n\n"
        "Карточка останется на месте.",
        parse_mode="HTML",
        reply_markup=moderation_cancel_keyboard("reject", story_id),
    )


@callback_router.message(StoryState.waiting_for_reject_reason, F.text == "⬅️ Назад")
async def cancel_reject(message: Message, state: FSMContext):
    data = await state.get_data()
    story_id = data.get("rejecting_story_id")
    chat_id = data.get("moderation_chat_id")
    msg_id = data.get("moderation_message_id")
    await state.clear()
    if story_id and chat_id and msg_id:
        try:
            story = get_story(story_id)
            if story:
                await message.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=story_card_text(story),
                    parse_mode="HTML",
                    reply_markup=moderation_keyboard(story_id, story["user_id"]),
                )
        except Exception as error:
            print(f"RESTORE MODERATION ERROR: {error}")
    await message.answer("↩️ Отклонение отменено.", reply_markup=admin_keyboard)


@callback_router.message(StoryState.waiting_for_reject_reason)
async def save_reject(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("❗ Напишите причину отказа.")
        return
    data = await state.get_data()
    story_id = data.get("rejecting_story_id")
    chat_id = data.get("moderation_chat_id")
    msg_id = data.get("moderation_message_id")
    story = get_story(story_id) if story_id else None
    if not story:
        await state.clear()
        await message.answer("❌ История не найдена.", reply_markup=admin_keyboard)
        return
    reject_story(story_id, reason)
    try:
        await message.bot.send_message(
            story["user_id"],
            "ℹ️ <b>История не была опубликована.</b>\n\n"
            f"Причина: {escape(reason)}",
            parse_mode="HTML",
        )
    except Exception as error:
        print(f"REJECT NOTIFY ERROR: {error}")
    if chat_id and msg_id:
        try:
            updated = get_story(story_id)
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=story_card_text(updated),
                parse_mode="HTML",
                reply_markup=None,
            )
        except Exception as error:
            print(f"REJECT CARD ERROR: {error}")
    await state.clear()
    await message.answer("❌ История отклонена.", reply_markup=admin_keyboard)


@callback_router.callback_query(F.data.startswith("preview:"))
async def preview_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    story = get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        "👀 <b>Предпросмотр публикации</b>\n\n" + escape(story["post_text"] or "⚠️ Пост отсутствует."),
        parse_mode="HTML",
    )


@callback_router.callback_query(F.data.startswith("ai_retry:"))
async def ai_retry_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    story = get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True)
        return
    try:
        result = await analyze_story(story["text"])
        update_ai_result(story_id, result)
        await refresh_story_card(callback.message, story_id)
        await callback.answer("✅ ИИ-анализ обновлён.")
    except Exception as error:
        print(f"AI RETRY ERROR: {error}")
        await callback.answer("❌ Не удалось получить анализ ИИ.", show_alert=True)


@callback_router.callback_query(F.data.startswith("favorite:"))
async def favorite_handler(callback: CallbackQuery):
    if not await check_admin(callback): return
    story_id=get_id_from_callback(callback); story=get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True); return
    value=toggle_story_favorite(story_id)
    await refresh_story_card(callback.message, story_id)
    await callback.answer("⭐ Добавлено в избранное." if value else "☆ Убрано из избранного.")


@callback_router.callback_query(F.data.startswith("ai_review:"))
async def ai_review_handler(callback: CallbackQuery):
    if not await check_admin(callback): return
    story_id=get_id_from_callback(callback); story=get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True); return
    try:
        result=await review_story(story["text"])
        risk="Высокий" if "высок" in result.lower() else ("Средний" if "сред" in result.lower() else "Низкий")
        set_ai_review(story_id,result,risk)
        await callback.message.answer(f"🤖 <b>ИИ-проверка #{story_id}</b>\n\n{escape(result)}",parse_mode="HTML")
        await callback.answer("✅ Проверка завершена.")
    except Exception as error:
        print(f"AI REVIEW ERROR: {error}")
        await callback.answer("❌ ИИ-проверка недоступна.", show_alert=True)


@callback_router.callback_query(F.data.startswith("edit:"))
async def edit_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    story = get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(
        editing_story_id=story_id,
        moderation_message_id=callback.message.message_id,
        moderation_chat_id=callback.message.chat.id,
    )
    await state.set_state(StoryState.waiting_for_edit)
    await callback.answer()
    await callback.message.edit_text(
        f"✏️ <b>Редактирование истории #{story_id}</b>\n\n"
        "Отправьте новый текст поста следующим сообщением.\n\n"
        "Карточка истории останется на месте, а после сохранения обновится автоматически.",
        parse_mode="HTML",
        reply_markup=moderation_cancel_keyboard("edit", story_id),
    )


@callback_router.callback_query(F.data.startswith("edit_cancel:"))
async def edit_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    await state.clear()
    story = get_story(story_id) if story_id else None
    if story:
        await callback.message.edit_text(story_card_text(story), parse_mode="HTML", reply_markup=moderation_keyboard(story_id, story["user_id"]))
    await callback.answer("↩️ Редактирование отменено.")


@callback_router.callback_query(F.data.startswith("reject_cancel:"))
async def reject_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    await state.clear()
    story = get_story(story_id) if story_id else None
    if story:
        await callback.message.edit_text(story_card_text(story), parse_mode="HTML", reply_markup=moderation_keyboard(story_id, story["user_id"]))
    await callback.answer("↩️ Отклонение отменено.")


@callback_router.callback_query(F.data.startswith("contact_cancel:"))
async def contact_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    await state.clear()
    story = get_story(story_id) if story_id else None
    if story:
        await callback.message.edit_text(story_card_text(story), parse_mode="HTML", reply_markup=moderation_keyboard(story_id, story["user_id"]))
    await callback.answer("↩️ Отправка отменена.")


@callback_router.message(StoryState.waiting_for_edit, F.text == "⬅️ Назад")
async def cancel_edit(message: Message, state: FSMContext):
    data = await state.get_data()
    story_id = data.get("editing_story_id")
    chat_id = data.get("moderation_chat_id")
    msg_id = data.get("moderation_message_id")
    await state.clear()
    if story_id and chat_id and msg_id:
        story = get_story(story_id)
        if story:
            try:
                await message.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=story_card_text(story),
                    parse_mode="HTML",
                    reply_markup=moderation_keyboard(story_id, story["user_id"]),
                )
            except Exception as error:
                print(f"RESTORE EDIT CARD ERROR: {error}")
    await message.answer("↩️ Редактирование отменено.", reply_markup=admin_keyboard)


@callback_router.message(StoryState.waiting_for_edit)
async def save_edited_post(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("❗ Отправьте текст.")
        return
    data = await state.get_data()
    story_id = data.get("editing_story_id")
    chat_id = data.get("moderation_chat_id")
    msg_id = data.get("moderation_message_id")
    story = get_story(story_id) if story_id else None
    if not story:
        await state.clear()
        await message.answer("❌ История не найдена.", reply_markup=admin_keyboard)
        return
    update_post(story_id, text)
    if chat_id and msg_id:
        try:
            updated = get_story(story_id)
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=story_card_text(updated),
                parse_mode="HTML",
                reply_markup=moderation_keyboard(story_id, updated["user_id"]),
            )
        except Exception as error:
            print(f"UPDATE EDITED CARD ERROR: {error}")
    await state.clear()
    await message.answer(f"✅ Пост истории #{story_id} изменён.", reply_markup=admin_keyboard)


# =========================================================
# CONTACT USER
# =========================================================

@callback_router.callback_query(F.data.startswith("contact:"))
async def contact_user_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    story_id = get_id_from_callback(callback)
    story = get_story(story_id) if story_id else None
    if not story:
        await callback.answer("❌ История не найдена.", show_alert=True)
        return
    await state.clear()
    await state.update_data(
        contact_user_id=story["user_id"],
        contact_story_id=story_id,
        moderation_message_id=callback.message.message_id,
        moderation_chat_id=callback.message.chat.id,
    )
    await state.set_state(StoryState.waiting_for_contact_message)
    await callback.answer()
    await callback.message.edit_text(
        f"👤 <b>Сообщение пользователю</b>\n\nИстория #{story_id}\n\n"
        "Напишите сообщение автору следующим сообщением.\n\n"
        "Карточка истории останется на месте.",
        parse_mode="HTML",
        reply_markup=moderation_cancel_keyboard("contact", story_id),
    )


@callback_router.message(StoryState.waiting_for_contact_message, F.text == "⬅️ Назад")
async def cancel_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    story_id = data.get("contact_story_id")
    chat_id = data.get("moderation_chat_id")
    msg_id = data.get("moderation_message_id")
    await state.clear()
    if story_id and chat_id and msg_id:
        story = get_story(story_id)
        if story:
            try:
                await message.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=msg_id,
                    text=story_card_text(story),
                    parse_mode="HTML",
                    reply_markup=moderation_keyboard(story_id, story["user_id"]),
                )
            except Exception as error:
                print(f"RESTORE CONTACT CARD ERROR: {error}")
    await message.answer("↩️ Отправка сообщения отменена.", reply_markup=admin_keyboard)


@callback_router.message(StoryState.waiting_for_contact_message)
async def send_contact_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("❗ Сообщение пустое.")
        return
    data = await state.get_data()
    user_id = data.get("contact_user_id")
    story_id = data.get("contact_story_id")
    chat_id = data.get("moderation_chat_id")
    msg_id = data.get("moderation_message_id")
    if not user_id:
        await state.clear()
        await message.answer("❌ Пользователь не найден.", reply_markup=admin_keyboard)
        return
    try:
        await message.bot.send_message(
            user_id,
            "💬 <b>Сообщение от команды:</b>\n\n" + escape(text),
            parse_mode="HTML",
        )
        if story_id and chat_id and msg_id:
            story = get_story(story_id)
            if story:
                try:
                    await message.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=msg_id,
                        text=story_card_text(story),
                        parse_mode="HTML",
                        reply_markup=moderation_keyboard(story_id, story["user_id"]),
                    )
                except Exception as error:
                    print(f"RESTORE CONTACT AFTER SEND ERROR: {error}")
        await state.clear()
        await message.answer("✅ Сообщение отправлено.", reply_markup=admin_keyboard)
    except Exception as error:
        print(f"CONTACT ERROR: {error}")
        await state.clear()
        await message.answer("❌ Не удалось отправить сообщение.", reply_markup=admin_keyboard)


# =========================================================
# SUPPORT
# =========================================================

@callback_router.callback_query(F.data.startswith("dialog_open:"))
async def dialog_open_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = get_dialog(dialog_id) if dialog_id else None
    if not dialog:
        await callback.answer("❌ Диалог не найден.", show_alert=True)
        return
    if dialog["status"] != "open":
        await callback.answer("ℹ️ Диалог закрыт.", show_alert=True)
        return
    admin_id = callback.from_user.id
    assigned = dialog["assigned_admin_id"]
    if assigned and assigned != admin_id:
        await callback.answer("👨‍💼 Диалог уже ведёт другой сотрудник.", show_alert=True)
        return
    mark_dialog_read_by_admin(dialog_id)
    assign_dialog(dialog_id, admin_id)
    set_dialog_status(dialog_id, "in_progress")
    await state.clear()
    await state.update_data(moderator_dialog_id=dialog_id)
    await state.set_state(StoryState.moderator_dialog)

    # Кнопки и текст всегда живут в одной карточке.
    try:
        await callback.message.edit_text(
            dialog_card_text(dialog_id),
            parse_mode="HTML",
            reply_markup=support_dialog_keyboard(dialog_id),
        )
        set_admin_control_message(dialog_id, callback.message.chat.id, callback.message.message_id)
    except Exception:
        sent = await callback.message.answer(
            dialog_card_text(dialog_id),
            parse_mode="HTML",
            reply_markup=support_dialog_keyboard(dialog_id),
        )
        set_admin_control_message(dialog_id, callback.message.chat.id, sent.message_id)
    await callback.answer()


@callback_router.message(StoryState.moderator_dialog, F.text == "⬅️ Назад")
async def moderator_back(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    dialog_id = data.get("moderator_dialog_id")
    if dialog_id:
        dialog = get_dialog(dialog_id)
        if dialog and dialog["assigned_admin_id"] == message.from_user.id:
            unassign_dialog(dialog_id)
            set_dialog_status(dialog_id, "new")
    await state.clear()
    await message.answer("↩️ Вы вышли из режима диалога.", reply_markup=admin_keyboard)


async def _check_dialog_owner(callback: CallbackQuery, dialog_id: int):
    dialog = get_dialog(dialog_id)
    if not dialog:
        await callback.answer("❌ Диалог не найден.", show_alert=True)
        return None
    assigned = dialog["assigned_admin_id"]
    if assigned and assigned != callback.from_user.id:
        await callback.answer("⛔ Диалог ведёт другой сотрудник.", show_alert=True)
        return None
    return dialog


@callback_router.callback_query(F.data.startswith("dialog_waiting:"))
async def dialog_waiting_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = await _check_dialog_owner(callback, dialog_id) if dialog_id else None
    if not dialog:
        return
    set_dialog_status(dialog_id, "waiting_user")
    try:
        await callback.bot.send_message(
            dialog["user_id"],
            "🟠 Сотрудник поддержки ожидает вашего ответа.\n\nНапишите сообщение в этом чате, когда будете готовы.",
        )
    except Exception as error:
        print(f"WAITING USER NOTIFY ERROR: {error}")
    await refresh_dialog_card(callback.bot, dialog_id)
    await callback.answer("🟠 Диалог ожидает пользователя.")


@callback_router.callback_query(F.data.startswith("dialog_resolved:"))
async def dialog_resolved_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = await _check_dialog_owner(callback, dialog_id) if dialog_id else None
    if not dialog:
        return
    set_dialog_status(dialog_id, "resolved")
    try:
        await callback.bot.send_message(dialog["user_id"], "🟢 Сотрудник поддержки отметил вопрос как решённый. Если понадобится помощь снова — напишите нам.")
    except Exception as error:
        print(f"RESOLVED NOTIFY ERROR: {error}")
    await refresh_dialog_card(callback.bot, dialog_id)
    await callback.answer("🟢 Диалог отмечен как решённый.")


@callback_router.callback_query(F.data.startswith("dialog_exit:"))
async def dialog_exit_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = await _check_dialog_owner(callback, dialog_id) if dialog_id else None
    if not dialog:
        return
    unassign_dialog(dialog_id)
    set_dialog_status(dialog_id, "new")
    await state.clear()
    await callback.answer("↩️ Вы вышли из диалога.")
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer("💬 Вы вышли из текущего диалога.", reply_markup=admin_keyboard)


@callback_router.callback_query(F.data.startswith("dialog_personal:"))
async def dialog_personal_handler(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = get_dialog(dialog_id) if dialog_id else None
    if not dialog:
        await callback.answer("❌ Диалог не найден.", show_alert=True)
        return
    await callback.answer("📞 Профиль пользователя готов.")
    await callback.message.answer(
        "📞 <b>Личный контакт</b>\n\n"
        f"Диалог #{dialog_id}\nUser ID: <code>{dialog['user_id']}</code>",
        parse_mode="HTML",
        reply_markup=personal_request_keyboard(dialog_id, dialog["user_id"]),
    )


@callback_router.callback_query(F.data.startswith("dialog_close:"))
async def dialog_close_handler(callback: CallbackQuery, state: FSMContext):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = await _check_dialog_owner(callback, dialog_id) if dialog_id else None
    if not dialog:
        return
    close_dialog(dialog_id)
    clear_admin_control_message(dialog_id)
    await state.clear()
    try:
        await callback.bot.send_message(
            dialog["user_id"],
            "💙 Диалог с поддержкой завершён.\n\nЕсли вам снова понадобится помощь, используйте «🆘 Экстренная поддержка»."
        )
    except Exception as error:
        print(f"CLOSE USER ERROR: {error}")
    try:
        await callback.message.edit_text(
            dialog_card_text(dialog_id),
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        await safe_remove_keyboard(callback)
    await callback.answer("🔴 Диалог закрыт.")
    await callback.message.answer("🔴 Диалог закрыт.", reply_markup=admin_keyboard)


@callback_router.message(StoryState.moderator_dialog)
async def moderator_dialog_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    text = (message.text or "").strip()
    if not text:
        await message.answer("❗ Отправьте текст.")
        return
    data = await state.get_data()
    dialog_id = data.get("moderator_dialog_id")
    dialog = get_dialog(dialog_id) if dialog_id else None
    if not dialog or dialog["status"] != "open":
        await state.clear()
        await message.answer("❌ Диалог закрыт.", reply_markup=admin_keyboard)
        return
    assigned = dialog["assigned_admin_id"]
    if assigned and assigned != message.from_user.id:
        await state.clear()
        await message.answer("⛔ Диалог ведёт другой сотрудник.", reply_markup=admin_keyboard)
        return
    add_support_message(dialog_id, message.from_user.id, "admin", text)
    set_dialog_status(dialog_id, "in_progress")
    try:
        await message.bot.send_message(
            dialog["user_id"],
            "💙 <b>Сообщение от сотрудника поддержки:</b>\n\n" + escape(text),
            parse_mode="HTML",
        )
        await refresh_dialog_card(message.bot, dialog_id)
        await message.answer("✅ Сообщение отправлено.")
    except Exception as error:
        print(f"MODERATOR SEND ERROR: {error}")
        await message.answer("❌ Не удалось отправить сообщение.")


# =========================================================
# MATERIALS
# =========================================================

@callback_router.callback_query(F.data == "open_emergency_support")
async def open_emergency_support_callback(callback: CallbackQuery, state: FSMContext):
    register_user(callback.from_user.id)
    await state.clear()
    await state.set_state(StoryState.waiting_for_support_method)
    from keyboards import support_method_keyboard
    await callback.answer("🆘 Открываем поддержку…")
    await callback.message.answer(
        "🆘 <b>Экстренная поддержка</b>\n\n"
        "Если вам тяжело, вы можете рассказать о том, что происходит.\n\n"
        "Выберите способ общения:",
        parse_mode="HTML",
        reply_markup=support_method_keyboard(),
    )


@callback_router.callback_query(F.data.startswith("user_profile:"))
async def user_profile_callback(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    user_id = get_id_from_callback(callback)
    if user_id is None:
        await callback.answer("❌ Некорректный ID.", show_alert=True)
        return
    user, stories, dialogs, counts = get_user_profile(user_id)
    if not user:
        await callback.answer("❌ Пользователь не найден.", show_alert=True)
        return
    published = sum(1 for s in stories if s["status"] == "published")
    waiting = sum(1 for s in stories if s["status"] == "waiting")
    rejected = sum(1 for s in stories if s["status"] == "rejected")
    text = (
        "👤 <b>Профиль пользователя</b>\n\n"
        f"User ID: <code>{user_id}</code>\n"
        f"📅 Регистрация: {escape(str(user['created_at'] or ''))}\n\n"
        f"📚 Историй: {counts['total']}\n"
        f"⏳ На модерации: {counts['waiting']}\n"
        f"✅ Опубликовано: {counts['published']}\n"
        f"❌ Отклонено: {counts['rejected']}\n"
        f"💬 Диалогов: {counts['dialogs']}"
    )
    await callback.answer()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=user_profile_keyboard(user_id))


@callback_router.callback_query(F.data.startswith("user_dialog:"))
async def user_dialog_callback(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    user_id = get_id_from_callback(callback)
    dialog = get_open_dialog_by_user(user_id) if user_id else None
    if not dialog:
        await callback.answer("ℹ️ Открытого диалога нет.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        f"💬 Открытый диалог #{dialog['id']} пользователя <code>{user_id}</code>",
        parse_mode="HTML",
        reply_markup=__import__('keyboards').support_new_message_keyboard(dialog['id']),
    )


@callback_router.callback_query(F.data.startswith("dialog_user:"))
async def dialog_user_profile_callback(callback: CallbackQuery):
    if not await check_admin(callback):
        return
    dialog_id = get_id_from_callback(callback)
    dialog = get_dialog(dialog_id) if dialog_id else None
    if not dialog:
        await callback.answer("❌ Диалог не найден.", show_alert=True)
        return
    user, stories, dialogs, counts = get_user_profile(dialog['user_id'])
    await callback.answer()
    await callback.message.answer(
        "👤 <b>Профиль пользователя</b>\n\n"
        f"User ID: <code>{dialog['user_id']}</code>\n"
        f"📚 Историй: {counts['total']}\n"
        f"💬 Диалогов: {counts['dialogs']}",
        parse_mode="HTML",
        reply_markup=user_profile_keyboard(dialog['user_id']),
    )


@callback_router.callback_query(F.data.startswith("material:"))
async def material_handler(callback: CallbackQuery):
    material_key = callback.data.split(":", 1)[1]
    if material_key == "support":
        await callback.answer()
        await callback.message.answer(
            "🆘 Если вам нужна поддержка, нажмите «🆘 Экстренная поддержка» в главном меню."
        )
        return
    try:
        from handlers import MATERIALS
        material_text = MATERIALS.get(material_key)
    except Exception:
        material_text = None
    if not material_text:
        await callback.answer("❌ Материал не найден.", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(
        material_text,
        parse_mode="HTML",
        reply_markup=material_actions_keyboard(),
    )
