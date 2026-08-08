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
    get_dialog_messages,
)

from ai import analyze_story
from post_generator import create_post

from keyboards import (
    main_keyboard,
    admin_keyboard,
    moderation_keyboard,
    support_new_message_keyboard,
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
async def start_command(message: Message):

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
async def help_command(message: Message):

    await message.answer(
        "💡 Как пользоваться ботом:\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал для публикации.\n"
        "4️⃣ Администратор проверит материал.\n\n"
        "Если вам нужна срочная поддержка, "
        "используйте кнопку «🆘 Экстренная поддержка».\n\n"
        "Спасибо за доверие 💙"
    )


# =========================================================
# ЭКСТРЕННАЯ ПОДДЕРЖКА
# =========================================================

@router.message(F.text == "🆘 Экстренная поддержка")
async def emergency_support(
    message: Message,
    state: FSMContext,
):

    dialog = get_open_dialog_by_user(
        message.from_user.id
    )

    await state.clear()

    if dialog:

        messages = get_dialog_messages(
            dialog["id"]
        )

        await message.answer(
            "💬 У вас уже есть открытый диалог с модератором.\n\n"
            "Просто напишите сообщение — оно будет "
            "передано модератору."
        )

        return

    await state.set_state(
        StoryState.waiting_for_support_message
    )

    await message.answer(
        "🆘 <b>Экстренная поддержка</b>\n\n"
        "Если вам сейчас очень тяжело или вам "
        "нужна помощь, расскажите нам, что происходит.\n\n"
        "Ваше сообщение будет передано модератору. "
        "После этого вы сможете продолжить диалог "
        "прямо через этот бот.\n\n"
        "⚠️ Если вы находитесь в непосредственной опасности, "
        "обратитесь в местные экстренные службы.\n\n"
        "Напишите сообщение ниже.",
        parse_mode="HTML",
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

    support_text = message.text

    if not support_text:

        await message.answer(
            "❗ Пожалуйста, отправьте сообщение обычным текстом."
        )

        return

    support_text = support_text.strip()

    if len(support_text) < 2:

        await message.answer(
            "✏️ Напишите немного подробнее, "
            "чтобы модератор смог вам ответить."
        )

        return

    user_id = message.from_user.id

    dialog_id = create_support_dialog(
        user_id=user_id,
        first_message=support_text,
    )

    support_text_for_admin = (
        "🆘 <b>НОВЫЙ ДИАЛОГ</b>\n\n"
        f"💬 <b>Диалог #{dialog_id}</b>\n"
        f"👤 <b>User ID:</b> "
        f"<code>{user_id}</code>\n\n"
        "Сообщение пользователя:\n\n"
        f"{support_text}"
    )

    sent_to_admin = False

    for admin_id in ADMIN_IDS:

        try:

            await message.bot.send_message(
                admin_id,
                support_text_for_admin,
                reply_markup=support_new_message_keyboard(
                    dialog_id
                ),
                parse_mode="HTML",
            )

            sent_to_admin = True

        except Exception as error:

            print(
                f"SUPPORT ADMIN SEND ERROR: {error}"
            )

    if sent_to_admin:

        await message.answer(
            "💙 Ваше сообщение передано модератору.\n\n"
            "Вы можете продолжать писать сюда. "
            "Все ваши сообщения будут передаваться "
            "в этот диалог."
        )

    else:

        await message.answer(
            "❌ Сейчас не удалось передать сообщение "
            "модератору.\n\n"
            "Попробуйте немного позже."
        )

    await state.clear()


# =========================================================
# СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ В АКТИВНЫЙ ДИАЛОГ
# =========================================================

@router.message(
    F.chat.type == "private",
    F.text,
)
async def active_support_message(
    message: Message,
    state: FSMContext,
):

    # Администраторов здесь не обрабатываем
    if is_admin(message.from_user.id):
        return

    # Не перехватываем команды и кнопки
    if message.text in [
        "📝 Поделиться историей",
        "💡 Совет дня",
        "📚 Полезные материалы",
        "🆘 Экстренная поддержка",
    ]:
        return

    dialog = get_open_dialog_by_user(
        message.from_user.id
    )

    if not dialog:
        return

    dialog_id = dialog["id"]

    add_support_message(
        dialog_id=dialog_id,
        sender_id=message.from_user.id,
        sender_type="user",
        text=message.text,
    )

    admin_text = (
        "💬 <b>Новое сообщение в диалоге</b>\n\n"
        f"Диалог #{dialog_id}\n"
        f"👤 User ID: "
        f"<code>{message.from_user.id}</code>\n\n"
        f"{message.text}"
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

    await message.answer(
        "💙 Сообщение передано модератору."
    )


# =========================================================
# ПОДЕЛИТЬСЯ ИСТОРИЕЙ
# =========================================================

@router.message(F.text == "📝 Поделиться историей")
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

@router.message(StoryState.waiting_for_story)
async def receive_story(
    message: Message,
    state: FSMContext,
):

    story = message.text

    if not story:

        await message.answer(
            "❗ Отправьте историю обычным текстовым сообщением."
        )

        return

    story = story.strip()

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
        f"{story}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Анализ ИИ:</b>\n\n"
        f"{ai_result}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📌 <b>Готовый пост:</b>\n\n"
        f"{post_text}"
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

@router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    stats = get_stats()

    await message.answer(
        "👨‍💼 <b>Панель администратора</b>\n\n"
        f"⏳ На модерации: {stats['waiting']}\n"
        f"📚 Всего историй: {stats['total']}\n"
        f"✅ Опубликовано: {stats['published']}\n"
        f"❌ Отклонено: {stats['rejected']}\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ДИАЛОГИ
# =========================================================

@router.message(F.text == "💬 Диалоги")
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
        f"💬 <b>Открытые диалоги: {len(dialogs)}</b>",
        parse_mode="HTML",
    )

    for dialog in dialogs[:50]:

        last_message = dialog["last_message"] or ""

        if len(last_message) > 100:
            last_message = last_message[:100] + "..."

        text = (
            f"💬 <b>Диалог #{dialog['id']}</b>\n\n"
            f"👤 User ID: "
            f"<code>{dialog['user_id']}</code>\n\n"
            f"Последнее сообщение:\n"
            f"{last_message}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Открыть",
                        callback_data=(
                            f"dialog_open:{dialog['id']}"
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

@router.message(F.text == "⏳ Модерация")
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
        f"⏳ <b>На модерации: {len(stories)}</b>",
        parse_mode="HTML",
    )

    for story in stories[:20]:

        await message.answer(
            f"📥 <b>История #{story['id']}</b>\n\n"
            f"👤 User ID: "
            f"<code>{story['user_id']}</code>\n\n"
            f"{story['text']}",
            parse_mode="HTML",
            reply_markup=moderation_keyboard(
                story["id"],
                story["user_id"],
            ),
        )


# =========================================================
# СТАТИСТИКА
# =========================================================

@router.message(F.text == "📊 Статистика")
async def statistics(
    message: Message,
):

    if not is_admin(message.from_user.id):
        return

    stats = get_stats()

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"📚 Всего историй: {stats['total']}\n\n"
        f"⏳ На модерации: {stats['waiting']}\n"
        f"✅ Опубликовано: {stats['published']}\n"
        f"❌ Отклонено: {stats['rejected']}",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ВСЕ ИСТОРИИ
# =========================================================

@router.message(F.text == "📁 Все истории")
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

    text = "📁 <b>Все истории</b>\n\n"

    for story in stories[:30]:

        status = story["status"]

        if status == "waiting":
            status_icon = "⏳"
        elif status == "published":
            status_icon = "✅"
        elif status == "rejected":
            status_icon = "❌"
        else:
            status_icon = "📌"

        text += (
            f"{status_icon} #{story['id']} — "
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

@router.message(F.text == "⬅️ Назад")
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
        )2
