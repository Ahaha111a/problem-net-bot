from html import escape

from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from states import StoryState
from config import ADMIN_IDS

from database import (
    create_story,
    update_ai_result,
    update_post,
    get_waiting_stories,
    get_all_stories,
    get_stats,

    get_open_dialog_by_user,
    create_support_dialog,
    add_support_message,
    get_open_dialogs,
)

from ai import analyze_story
from post_generator import create_post

from keyboards import (
    main_keyboard,
    admin_keyboard,
    moderation_keyboard,
    support_new_message_keyboard,
    personal_contact_keyboard,
)


router = Router()


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(user_id: int) -> bool:

    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

@router.message(Command("start"))
async def start_command(
    message: Message,
):

    await message.answer(
        "👋 Добро пожаловать в «Проблем нет»\n\n"
        "Это пространство, где можно поделиться тем, "
        "что тревожит, беспокоит или давно лежит внутри.\n\n"
        "💙 Здесь:\n"
        "• истории рассматриваются анонимно;\n"
        "• нет осуждения и оценок;\n"
        "• каждая история может помочь кому-то ещё.\n\n"
        "📝 Нажмите кнопку ниже и расскажите свою историю.\n\n"
        "Помните: проблем нет.",
        reply_markup=main_keyboard,
    )

    if is_admin(message.from_user.id):

        await message.answer(
            "👨‍💼 Вы вошли как администратор.\n"
            "Для управления проектом используйте "
            "админ-панель.",
            reply_markup=admin_keyboard,
        )


# =========================================================
# HELP
# =========================================================

@router.message(Command("help"))
async def help_command(
    message: Message,
):

    await message.answer(
        "💡 Как пользоваться ботом:\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал для публикации.\n"
        "4️⃣ Администратор проверит материал.\n\n"
        "🆘 Если вам нужна срочная поддержка, "
        "используйте «Экстренная поддержка».\n\n"
        "📞 Если вы хотите, чтобы с вами связался "
        "сотрудник лично, это можно запросить "
        "в любой момент.\n\n"
        "Спасибо за доверие 💙"
    )


# =========================================================
# ЭКСТРЕННАЯ ПОДДЕРЖКА
# =========================================================

@router.message(
    F.text == "🆘 Экстренная поддержка"
)
async def emergency_support(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    await state.set_state(
        StoryState.waiting_for_support_method
    )

    from keyboards import support_method_keyboard

    await message.answer(
        "🆘 <b>Экстренная поддержка</b>\n\n"
        "Выберите, как вы хотите продолжить общение:\n\n"
        "💬 <b>Продолжить в боте</b>\n"
        "Вы будете переписываться с сотрудником "
        "поддержки прямо здесь.\n\n"
        "📞 <b>Связаться лично</b>\n"
        "Мы передадим сотруднику ваш запрос, "
        "и он сможет открыть ваш Telegram-профиль "
        "и написать вам напрямую.\n\n"
        "💙 Вы сможете изменить решение позже.",
        parse_mode="HTML",
        reply_markup=support_method_keyboard(),
    )


# =========================================================
# ЛИЧНЫЙ КОНТАКТ В ЛЮБОЙ МОМЕНТ
# =========================================================

@router.message(
    F.text == "📞 Связь с сотрудником"
)
async def personal_contact_anytime(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    user_id = message.from_user.id

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

    from callbacks import send_personal_request_to_admins

    await send_personal_request_to_admins(
        bot=message.bot,
        dialog_id=dialog_id,
        user_id=user_id,
    )

    await message.answer(
        "📞 <b>Запрос отправлен</b>\n\n"
        "Мы передали сотруднику поддержки "
        "запрос на личный контакт.\n\n"
        "Сотрудник сможет открыть ваш профиль "
        "и написать вам напрямую.\n\n"
        "💬 При этом вы можете продолжать "
        "общение с поддержкой прямо здесь.",
        parse_mode="HTML",
        reply_markup=personal_contact_keyboard(),
    )


# =========================================================
# ПЕРВОЕ СООБЩЕНИЕ ПОДДЕРЖКИ
# =========================================================

@router.message(
    StoryState.waiting_for_support_message
)
async def receive_support_message(
    message: Message,
    state: FSMContext,
):

    if not message.text:

        await message.answer(
            "❗ Пожалуйста, отправьте сообщение "
            "обычным текстом."
        )

        return

    support_text = message.text.strip()

    if len(support_text) < 2:

        await message.answer(
            "✏️ Напишите немного подробнее, "
            "чтобы сотрудник смог вам ответить."
        )

        return

    user_id = message.from_user.id

    dialog = get_open_dialog_by_user(
        user_id
    )

    if dialog:

        dialog_id = dialog["id"]

        add_support_message(
            dialog_id=dialog_id,
            sender_id=user_id,
            sender_type="user",
            text=support_text,
        )

    else:

        dialog_id = create_support_dialog(
            user_id=user_id,
            first_message=support_text,
        )

    await notify_admins_about_message(
        message,
        dialog_id,
        support_text,
    )

    await state.clear()

    await message.answer(
        "💙 Сообщение передано сотруднику поддержки.\n\n"
        "Вы можете продолжать писать сюда.\n"
        "Диалог останется открытым.\n\n"
        "Если захотите, нажмите "
        "«📞 Связаться со мной лично».",
        reply_markup=personal_contact_keyboard(),
    )


# =========================================================
# СООБЩЕНИЯ В АКТИВНЫЙ ДИАЛОГ
# =========================================================

@router.message(
    F.chat.type == "private",
    F.text,
)
async def active_support_message(
    message: Message,
    state: FSMContext,
):

    if is_admin(message.from_user.id):
        return

    if message.text in [
        "📝 Поделиться историей",
        "💡 Совет дня",
        "📚 Полезные материалы",
        "🆘 Экстренная поддержка",
        "📞 Связь с сотрудником",
        "⬅️ Назад",
    ]:
        return

    dialog = get_open_dialog_by_user(
        message.from_user.id
    )

    if not dialog:
        return

    text = message.text.strip()

    if not text:
        return

    dialog_id = dialog["id"]

    add_support_message(
        dialog_id=dialog_id,
        sender_id=message.from_user.id,
        sender_type="user",
        text=text,
    )

    await notify_admins_about_message(
        message,
        dialog_id,
        text,
    )

    await message.answer(
        "💙 Сообщение передано сотруднику поддержки.",
        reply_markup=personal_contact_keyboard(),
    )


# =========================================================
# УВЕДОМИТЬ МОДЕРАТОРОВ
# =========================================================

async def notify_admins_about_message(
    message: Message,
    dialog_id: int,
    text: str,
):

    admin_text = (
        "🔴 <b>Новое сообщение в диалоге</b>\n\n"
        f"💬 Диалог #{dialog_id}\n"
        f"👤 User ID: "
        f"<code>{message.from_user.id}</code>\n\n"
        f"{escape(text)}"
    )

    for admin_id in ADMIN_IDS:

        try:

            await message.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=support_new_message_keyboard(
                    dialog_id
                ),
                parse_mode="HTML",
            )

        except Exception as error:

            print(
                f"DIALOG MESSAGE ADMIN ERROR: {error}"
            )


# =========================================================
# ПОДЕЛИТЬСЯ ИСТОРИЕЙ
# =========================================================

@router.message(
    F.text == "📝 Поделиться историей"
)
async def start_story(
    message: Message,
    state: FSMContext,
):

    await state.set_state(
        StoryState.waiting_for_story
    )

    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит.\n\n"
        "🔒 История будет обработана анонимно."
    )


# =========================================================
# ПОЛУЧЕНИЕ ИСТОРИИ
# =========================================================

@router.message(
    StoryState.waiting_for_story
)
async def receive_story(
    message: Message,
    state: FSMContext,
):

    if not message.text:

        await message.answer(
            "❗ Отправьте историю обычным "
            "текстовым сообщением."
        )

        return

    story = message.text.strip()

    if len(story) < 10:

        await message.answer(
            "✏️ История слишком короткая.\n\n"
            "Напишите немного подробнее."
        )

        return

    story_id = create_story(
        user_id=message.from_user.id,
        text=story,
    )

    await message.answer(
        "🤖 Анализирую вашу историю..."
    )

    try:

        ai_result = await analyze_story(
            story
        )

    except Exception as error:

        print(
            f"AI ERROR: {error}"
        )

        ai_result = (
            "Не удалось выполнить анализ."
        )

    update_ai_result(
        story_id,
        ai_result,
    )

    try:

        post_text = await create_post(
            story
        )

    except Exception as error:

        print(
            f"POST ERROR: {error}"
        )

        post_text = (
            "Не удалось создать пост."
        )

    update_post(
        story_id,
        post_text,
    )

    moderation_text = (
        f"📥 <b>Новая история #{story_id}</b>\n\n"
        f"👤 <b>User ID:</b> "
        f"<code>{message.from_user.id}</code>\n\n"
        "🔒 История отправлена анонимно.\n\n"
        "💭 <b>Текст:</b>\n\n"
        f"{escape(story)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Анализ ИИ:</b>\n\n"
        f"{escape(ai_result)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📌 <b>Готовый пост:</b>\n\n"
        f"{escape(post_text)}"
    )

    for admin_id in ADMIN_IDS:

        try:

            await message.bot.send_message(
                admin_id,
                moderation_text,
                reply_markup=moderation_keyboard(
                    story_id,
                    message.from_user.id,
                ),
                parse_mode="HTML",
            )

        except Exception as error:

            print(
                f"ADMIN SEND ERROR: {error}"
            )

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    await state.clear()


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

@router.message(
    F.text == "👨‍💼 Админ-панель"
)
async def admin_panel(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    stats = get_stats()

    await message.answer(
        "👨‍💼 <b>Панель администратора</b>\n\n"
        f"⏳ На модерации: "
        f"{stats['waiting']}\n"
        f"📚 Всего историй: "
        f"{stats['total']}\n"
        f"✅ Опубликовано: "
        f"{stats['published']}\n"
        f"❌ Отклонено: "
        f"{stats['rejected']}\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ДИАЛОГИ
# =========================================================

@router.message(
    F.text == "💬 Диалоги"
)
async def dialogs_menu(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    dialogs = get_open_dialogs()

    if not dialogs:

        await message.answer(
            "💬 Открытых диалогов сейчас нет.",
            reply_markup=admin_keyboard,
        )

        return

    await message.answer(
        f"💬 <b>Открытые диалоги: "
        f"{len(dialogs)}</b>",
        parse_mode="HTML",
    )

    for dialog in dialogs[:50]:

        last_message = (
            dialog["last_message"] or ""
        )

        if len(last_message) > 100:

            last_message = (
                last_message[:100] + "..."
            )

        unread = dialog["unread_admin"] or 0

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

        if unread:

            unread_text = (
                f"🔴 Новых сообщений: {unread}"
            )

        else:

            unread_text = (
                "🟢 Нет новых сообщений"
            )

        assigned_admin = (
            dialog["assigned_admin_id"]
        )

        if assigned_admin:

            assigned_text = (
                f"👨‍💼 В работе у: "
                f"<code>{assigned_admin}</code>"
            )

        else:

            assigned_text = (
                "👨‍💼 Никому не назначен"
            )

        text = (
            f"💬 <b>Диалог #{dialog['id']}</b>\n\n"
            f"👤 User ID: "
            f"<code>{dialog['user_id']}</code>\n\n"
            f"{status_text}\n"
            f"{assigned_text}\n"
            f"{unread_text}\n\n"
            f"Последнее сообщение:\n"
            f"{escape(last_message)}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Открыть",
                        callback_data=(
                            f"dialog_open:"
                            f"{dialog['id']}"
                        ),
                    )
                ]
            ]
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# =========================================================
# МОДЕРАЦИЯ
# =========================================================

@router.message(
    F.text == "⏳ Модерация"
)
async def moderation(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    stories = get_waiting_stories()

    if not stories:

        await message.answer(
            "🟢 На модерации сейчас ничего нет.",
            reply_markup=admin_keyboard,
        )

        return

    await message.answer(
        f"⏳ <b>На модерации: "
        f"{len(stories)}</b>",
        parse_mode="HTML",
    )

    for story in stories[:20]:

        await message.answer(
            f"📥 <b>История #{story['id']}</b>\n\n"
            f"👤 User ID: "
            f"<code>{story['user_id']}</code>\n\n"
            f"{escape(story['text'])}",
            parse_mode="HTML",
            reply_markup=moderation_keyboard(
                story["id"],
                story["user_id"],
            ),
        )


# =========================================================
# СТАТИСТИКА
# =========================================================

@router.message(
    F.text == "📊 Статистика"
)
async def statistics(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    stats = get_stats()

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"📚 Всего историй: "
        f"{stats['total']}\n\n"
        f"⏳ На модерации: "
        f"{stats['waiting']}\n"
        f"✅ Опубликовано: "
        f"{stats['published']}\n"
        f"❌ Отклонено: "
        f"{stats['rejected']}",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ВСЕ ИСТОРИИ
# =========================================================

@router.message(
    F.text == "📁 Все истории"
)
async def all_stories(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    stories = get_all_stories()

    if not stories:

        await message.answer(
            "📁 Историй пока нет.",
            reply_markup=admin_keyboard,
        )

        return

    text = (
        "📁 <b>Все истории</b>\n\n"
    )

    for story in stories[:30]:

        status = story["status"]

        if status == "waiting":
            icon = "⏳"

        elif status == "published":
            icon = "✅"

        elif status == "rejected":
            icon = "❌"

        else:
            icon = "📌"

        text += (
            f"{icon} #{story['id']} — "
            f"{status}\n"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# НАЗАД
# =========================================================

@router.message(
    F.text == "⬅️ Назад"
)
async def back(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    if is_admin(message.from_user.id):

        await message.answer(
            "↩️ Админ-панель",
            reply_markup=admin_keyboard,
        )

    else:

        await message.answer(
            "↩️ Главное меню",
            reply_markup=main_keyboard,
        )
