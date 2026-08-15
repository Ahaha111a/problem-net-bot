from html import escape
import random

from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter

from states import StoryState
from config import ADMIN_IDS, CHANNEL_ID

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
    set_dialog_status,
    register_user,
    get_extended_stats,
    get_admin_control_message,
    get_published_stories,
    get_user_summary,
    search_stories,
    get_analytics,
    get_favorite_stories,
)

from ai import analyze_story
from post_generator import create_post

from callbacks import refresh_dialog_card

from keyboards import (
    main_keyboard,
    admin_keyboard,
    admin_user_keyboard,
    moderation_keyboard,
    support_new_message_keyboard,
    personal_contact_keyboard,
    material_actions_keyboard,
    published_story_keyboard,
)


router = Router()


# =========================================================
# MATERIALS
# =========================================================

MATERIALS = {
    "anxiety": (
        "🧠 <b>Если тревога не отпускает</b>\n\n"
        "Тревога может ощущаться как постоянное напряжение "
        "или ощущение, что вот-вот произойдёт что-то плохое.\n\n"
        "Попробуйте остановиться на несколько минут и обратить "
        "внимание на дыхание.\n\n"
        "Сделайте несколько медленных вдохов и выдохов. "
        "Назовите про себя 5 вещей, которые видите, "
        "4 вещи, которых можете коснуться, "
        "3 звука, которые слышите."
    ),
    "stress": (
        "🌿 <b>Как немного снизить стресс</b>\n\n"
        "Попробуйте сделать небольшой перерыв, "
        "выйти на свежий воздух, выпить воды "
        "или убрать хотя бы одну небольшую задачу.\n\n"
        "Иногда пауза помогает двигаться дальше."
    ),
    "sleep": (
        "🌙 <b>Если трудно уснуть</b>\n\n"
        "Перед сном попробуйте уменьшить количество "
        "яркого света и отложить телефон.\n\n"
        "Можно сделать несколько спокойных вдохов и выдохов."
    ),
    "self_esteem": (
        "💙 <b>Когда кажется, что вы недостаточно хороши</b>\n\n"
        "Попробуйте вспомнить хотя бы три вещи, "
        "которые у вас сегодня получились.\n\n"
        "Ваша ценность не определяется одной ошибкой."
    ),
}


def materials_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="😟 Тревога",
                    callback_data="material:anxiety",
                ),
                InlineKeyboardButton(
                    text="😣 Стресс",
                    callback_data="material:stress",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌙 Сон",
                    callback_data="material:sleep",
                ),
                InlineKeyboardButton(
                    text="💙 Самооценка",
                    callback_data="material:self_esteem",
                ),
            ],
        ],
    )


DAILY_TIPS = [
    "Не обязательно решать всю проблему сегодня. Иногда достаточно сделать один небольшой шаг.",
    "Если мысли постоянно возвращаются к одной проблеме, попробуйте записать их.",
    "Не требуйте от себя максимальной продуктивности каждый день.",
    "Если ситуация кажется огромной, разделите её на самое маленькое действие.",
    "Просить о помощи — нормально.",
]


def daily_tip_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆘 Нужна поддержка",
                    callback_data="material:support",
                ),
            ],
        ],
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# CHANNEL LINKS
# =========================================================

async def get_channel_message_link(
    bot,
    message_id: int,
):
    """
    Создаёт ссылку на конкретное сообщение канала.

    Для публичного канала:
        https://t.me/channel_username/message_id

    Для приватного канала:
        https://t.me/c/channel_id/message_id
    """

    try:
        chat = await bot.get_chat(
            chat_id=CHANNEL_ID
        )

        # Публичный канал
        if chat.username:
            return (
                f"https://t.me/"
                f"{chat.username}/"
                f"{message_id}"
            )

        # Приватный канал
        chat_id = str(chat.id)

        if chat_id.startswith("-100"):
            internal_id = chat_id[4:]

            return (
                f"https://t.me/c/"
                f"{internal_id}/"
                f"{message_id}"
            )

    except Exception as error:
        print(
            f"CHANNEL LINK ERROR: {error}"
        )

    return None


# =========================================================
# START
# =========================================================

@router.message(Command("start"))
async def start_command(
    message: Message,
    state: FSMContext,
):
    await state.clear()
    register_user(message.from_user.id)

    if is_admin(message.from_user.id):
        await message.answer(
            "👋 Добро пожаловать в «Проблем нет».\n\n"
            "👨‍💼 Вы вошли как администратор.\n\n"
            "Сейчас открыт режим пользователя.\n\n"
            "🆘 Если кому-то нужна помощь, "
            "можно воспользоваться функцией "
            "«Экстренная поддержка».",
            parse_mode="HTML",
            reply_markup=admin_user_keyboard,
        )
        return

    await message.answer(
        "👋 Добро пожаловать в «Проблем нет».\n\n"
        "Это пространство, где можно поделиться тем, "
        "что тревожит или беспокоит.\n\n"
        "💙 Здесь нет осуждения.\n\n"
        "📝 Нажмите «Поделиться историей».\n\n"
        "🆘 Если вам нужна помощь или просто хочется "
        "поговорить с сотрудником поддержки, "
        "воспользуйтесь функцией «Экстренная поддержка».\n\n"
        "📖 Также вы можете посмотреть истории "
        "других пользователей.\n\n"
        "Помните: проблем нет.",
        reply_markup=main_keyboard,
    )


# =========================================================
# HELP
# =========================================================

@router.message(Command("help"))
async def help_command(
    message: Message,
):
    await message.answer(
        "💡 <b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал.\n"
        "4️⃣ Администратор проверит его.\n\n"
        "🆘 Если нужна поддержка — используйте "
        "«Экстренная поддержка».\n\n"
        "📖 Опубликованные истории можно посмотреть "
        "через «Смотреть истории».",
        parse_mode="HTML",
    )


# =========================================================
# VIEW STORIES
# =========================================================

@router.message(F.text == "📖 Смотреть истории")
async def view_stories(
    message: Message,
):
    """
    Открывает самое первое сообщение канала.
    """

    link = await get_channel_message_link(
        message.bot,
        1,
    )

    if not link:
        await message.answer(
            "❌ Не удалось сформировать ссылку "
            "на канал.\n\n"
            "Проверь настройки CHANNEL_ID "
            "и права бота в канале."
        )
        return

    await message.answer(
        "📖 <b>Истории пользователей</b>\n\n"
        "Здесь собраны опубликованные истории.\n\n"
        "Нажмите кнопку ниже, чтобы открыть канал:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📖 Смотреть истории",
                        url=link,
                    ),
                ],
            ],
        ),
    )


# =========================================================
# ADMIN MODE
# =========================================================

@router.message(F.text == "👨‍💼 Админ-панель")
async def switch_to_admin_mode(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    stats = get_extended_stats()

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
# USER MODE
# =========================================================

@router.message(F.text == "👤 Режим пользователя")
async def switch_to_user_mode(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        "👤 <b>Режим пользователя</b>",
        parse_mode="HTML",
        reply_markup=admin_user_keyboard,
    )


# =========================================================
# DAILY TIP
# =========================================================

@router.message(F.text == "💡 Совет дня")
async def daily_tip(
    message: Message,
):
    await message.answer(
        "💡 <b>Совет дня</b>\n\n"
        + random.choice(DAILY_TIPS),
        parse_mode="HTML",
        reply_markup=daily_tip_keyboard(),
    )


# =========================================================
# MATERIALS
# =========================================================

@router.message(F.text == "📚 Полезные материалы")
async def useful_materials(
    message: Message,
):
    await message.answer(
        "📚 <b>Полезные материалы</b>\n\n"
        "Выберите тему:",
        parse_mode="HTML",
        reply_markup=materials_keyboard(),
    )


# =========================================================
# SUPPORT
# =========================================================

@router.message(F.text == "🆘 Экстренная поддержка")
async def emergency_support(
    message: Message,
    state: FSMContext,
):
    register_user(message.from_user.id)
    await state.clear()

    await state.set_state(
        StoryState.waiting_for_support_method
    )

    from keyboards import support_method_keyboard

    await message.answer(
        "🆘 <b>Экстренная поддержка</b>\n\n"
        "Если вам тяжело, вы можете рассказать "
        "о том, что происходит.\n\n"
        "Выберите способ общения:",
        parse_mode="HTML",
        reply_markup=support_method_keyboard(),
    )


# =========================================================
# SUPPORT MESSAGE
# =========================================================

@router.message(
    StoryState.waiting_for_support_message
)
async def receive_support_message(
    message: Message,
    state: FSMContext,
):
    register_user(message.from_user.id)
    if not message.text:
        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )
        return

    text = message.text.strip()

    if len(text) < 2:
        await message.answer(
            "✏️ Напишите немного подробнее."
        )
        return

    user_id = message.from_user.id

    dialog = get_open_dialog_by_user(
        user_id
    )

    if dialog:
        dialog_id = dialog["id"]

        add_support_message(
            dialog_id,
            user_id,
            "user",
            text,
        )

        set_dialog_status(
            dialog_id,
            "in_progress",
        )

    else:
        dialog_id = create_support_dialog(
            user_id,
            text,
        )

    await notify_admins_about_message(
        message,
        dialog_id,
        text,
    )

    await state.clear()

    await message.answer(
        "💙 Сообщение передано сотруднику поддержки.\n\n"
        "Диалог остаётся открытым.",
        reply_markup=personal_contact_keyboard(),
    )


async def notify_admins_about_message(
    message: Message,
    dialog_id: int,
    text: str,
):
    dialog = get_open_dialog_by_user(message.from_user.id)
    assigned_admin = dialog["assigned_admin_id"] if dialog else None

    # Если диалог уже взят конкретным сотрудником,
    # обновляем его существующую карточку. Так кнопки всегда
    # находятся вместе с актуальным состоянием диалога.
    if assigned_admin:
        try:
            await refresh_dialog_card(message.bot, dialog_id)
            return
        except Exception as error:
            print(f"ACTIVE DIALOG REFRESH ERROR: {error}")

    admin_text = (
        "💬 <b>Новое сообщение в диалоге</b>\n\n"
        f"Диалог #{dialog_id}\n"
        f"👤 User ID: <code>{message.from_user.id}</code>\n\n"
        f"{escape(text)}"
    )

    for admin_id in ADMIN_IDS:
        try:
            sent = await message.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=support_new_message_keyboard(dialog_id),
                parse_mode="HTML",
            )
            # Запоминаем последнее управляющее сообщение.
            from database import set_admin_control_message
            set_admin_control_message(dialog_id, admin_id, sent.message_id)
        except Exception as error:
            print(f"DIALOG ADMIN ERROR ({admin_id}): {error}")


# =========================================================
# STORY CREATION
# =========================================================

@router.message(F.text == "📝 Поделиться историей")
async def start_story(
    message: Message,
    state: FSMContext,
):
    register_user(message.from_user.id)
    await state.clear()

    await state.set_state(
        StoryState.waiting_for_story
    )

    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит.\n\n"
        "🔒 История будет обработана анонимно."
    )


@router.message(
    StoryState.waiting_for_story
)
async def receive_story(
    message: Message,
    state: FSMContext,
):
    if not message.text:
        await message.answer(
            "❗ Отправьте историю обычным текстом."
        )
        return

    story = message.text.strip()

    if len(story) < 10:
        await message.answer(
            "✏️ История слишком короткая."
        )
        return

    story_id = create_story(
        message.from_user.id,
        story,
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
            "⚠️ Автоматический анализ временно "
            "недоступен. История сохранена. "
            "Администратор сможет обработать её вручную."
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

        post_text = ""

    update_post(
        story_id,
        post_text,
    )

    moderation_text = (
        f"📥 <b>Новая история #{story_id}</b>\n\n"
        f"👤 User ID: "
        f"<code>{message.from_user.id}</code>\n\n"
        f"💭 <b>Текст:</b>\n\n"
        f"{escape(story)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Анализ ИИ:</b>\n\n"
        f"{escape(ai_result)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Готовый пост:</b>\n\n"
        f"{escape(post_text) if post_text else '⚠️ Пост не сгенерирован. Используйте «✏️ Изменить».'}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                moderation_text,
                reply_markup=(
                    moderation_keyboard(
                        story_id,
                        message.from_user.id,
                    )
                ),
                parse_mode="HTML",
            )

        except Exception as error:
            print(
                f"ADMIN SEND ERROR: {error}"
            )

    await state.clear()

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    if is_admin(message.from_user.id):
        await message.answer(
            "👤 Вы остались в режиме пользователя.",
            reply_markup=admin_user_keyboard,
        )


# =========================================================
# ACTIVE USER SUPPORT
# =========================================================

@router.message(
    StateFilter(None),
    F.chat.type == "private",
    F.text,
    ~F.text.in_(
        {
            "📝 Поделиться историей",
            "💡 Совет дня",
            "📚 Полезные материалы",
            "🆘 Экстренная поддержка",
            "📖 Смотреть истории",
            "⬅️ Назад",
            "👨‍💼 Админ-панель",
            "👤 Режим пользователя",
            "⏳ Модерация",
            "📊 Статистика",
            "💬 Диалоги",
            "📁 Все истории",
            "📚 Публикации",
            "👥 Пользователи",
            "⭐ Избранное",
            "🔎 Поиск",
            "📈 Аналитика",
        }
    ),
)
async def active_support_message(
    message: Message,
    state: FSMContext,
):
    if is_admin(message.from_user.id):
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
        dialog_id,
        message.from_user.id,
        "user",
        text,
    )

    set_dialog_status(
        dialog_id,
        "in_progress",
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
# ADMIN — DIALOGS
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

        last_message = (
            dialog["last_message"] or ""
        )

        if len(last_message) > 100:
            last_message = (
                last_message[:100] + "..."
            )

        unread = (
            dialog["unread_admin"] or 0
        )

        status_names = {
            "new": "🔴 Новый",
            "in_progress": "🟡 В работе",
            "waiting_user": "🟠 Ожидает пользователя",
            "resolved": "🟢 Решён",
        }
        support_status = dialog["support_status"] or "new"
        text = (
            f"💬 <b>Диалог #{dialog['id']}</b>\n\n"
            f"👤 User ID: "
            f"<code>{dialog['user_id']}</code>\n\n"
            f"{'🔴 Новых сообщений: ' + str(unread) if unread else '🟢 Нет новых сообщений'}\n\n"
            f"Последнее сообщение:\n"
            f"{escape(last_message)}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Открыть",
                        callback_data=(
                            f"dialog_open:{dialog['id']}"
                        ),
                    ),
                ],
            ],
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# =========================================================
# ADMIN — MODERATION
# =========================================================

@router.message(F.text == "⏳ Модерация")
async def moderation(message: Message):
    if not is_admin(message.from_user.id):
        return

    stories = get_waiting_stories()
    if not stories:
        await message.answer("🟢 На модерации сейчас ничего нет.", reply_markup=admin_keyboard)
        return

    await message.answer(
        f"⏳ <b>На модерации: {len(stories)}</b>",
        parse_mode="HTML",
    )

    from callbacks import story_card_text
    for story in stories[:20]:
        await message.answer(
            story_card_text(story),
            parse_mode="HTML",
            reply_markup=moderation_keyboard(story["id"], story["user_id"]),
        )


# =========================================================
# ADMIN — STATISTICS
# =========================================================

@router.message(F.text == "📊 Статистика")
async def statistics(message: Message):
    if not is_admin(message.from_user.id):
        return

    stats = get_extended_stats()
    support = stats["support"]

    await message.answer(
        "📊 <b>Расширенная статистика</b>\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"📚 Всего историй: {stats['total']}\n"
        f"⏳ На модерации: {stats['waiting']}\n"
        f"✅ Опубликовано: {stats['published']}\n"
        f"❌ Отклонено: {stats['rejected']}\n"
        f"\n📅 Опубликовано сегодня: {stats['published_today']}\n"
        f"📅 Отклонено сегодня: {stats['rejected_today']}\n"
        f"\n💬 Открытых диалогов: {support['open']}\n"
        f"🔴 Новых диалогов: {support['new']}\n"
        f"🟡 В работе: {support['in_progress']}\n"
        f"💬 Среднее сообщений в диалоге: {stats['avg_dialog_messages']}",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ADMIN — ALL STORIES
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

        icons = {
            "waiting": "⏳",
            "published": "✅",
            "rejected": "❌",
        }

        icon = icons.get(
            story["status"],
            "📌",
        )

        text += (
            f"{icon} #{story['id']} — "
            f"{story['status']}\n"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ADMIN — PUBLICATIONS
# =========================================================

@router.message(F.text == "📚 Публикации")
async def publications(message: Message):
    if not is_admin(message.from_user.id):
        return

    stories = get_published_stories(30)
    if not stories:
        await message.answer("📚 Опубликованных историй пока нет.", reply_markup=admin_keyboard)
        return

    await message.answer(
        f"📚 <b>Последние публикации: {len(stories)}</b>",
        parse_mode="HTML",
    )

    from callbacks import get_channel_message_link
    for story in stories:
        link = None
        if story["channel_message_id"]:
            link = await get_channel_message_link(message.bot, story["channel_message_id"])
        text = (
            f"✅ <b>История #{story['id']}</b>\n"
            f"👤 User ID: <code>{story['user_id']}</code>\n"
            f"📅 {escape(str(story['published_at'] or story['created_at'] or ''))}"
        )
        markup = None
        if link:
            markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="👀 Посмотреть", url=link)
            ]])
        await message.answer(text, parse_mode="HTML", reply_markup=markup)


# =========================================================
# ADMIN — USERS
# =========================================================

@router.message(F.text == "👥 Пользователи")
async def users_menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    users = get_user_summary(30)
    if not users:
        await message.answer("👥 Пользователей пока нет.", reply_markup=admin_keyboard)
        return

    await message.answer(
        f"👥 <b>Пользователи: {len(users)}</b>\n\n"
        "Нажмите на пользователя, чтобы открыть подробный профиль.",
        parse_mode="HTML",
    )

    from keyboards import user_profile_keyboard
    for user in users:
        await message.answer(
            f"👤 <b>User ID:</b> <code>{user['user_id']}</code>\n"
            f"📚 Историй: {user['stories_total'] or 0}\n"
            f"✅ Опубликовано: {user['stories_published'] or 0}\n"
            f"💬 Диалогов: {user['dialogs_total'] or 0}",
            parse_mode="HTML",
            reply_markup=user_profile_keyboard(user['user_id']),
        )


# =========================================================
# ADMIN — SEARCH / FAVORITES / ANALYTICS
# =========================================================

@router.message(F.text == "🔎 Поиск")
async def search_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await state.clear(); await state.set_state(StoryState.search_stories)
    await message.answer("🔎 <b>Поиск</b>\n\nВведите ID истории, User ID, тему или слово из текста.",parse_mode="HTML",reply_markup=admin_keyboard)

@router.message(StoryState.search_stories)
async def search_results(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id): await state.clear(); return
    query=(message.text or "").strip()
    if not query: await message.answer("❗ Введите запрос."); return
    rows=search_stories(query,30); await state.clear()
    if not rows: await message.answer("🔎 Ничего не найдено.",reply_markup=admin_keyboard); return
    await message.answer(f"🔎 <b>Найдено: {len(rows)}</b>",parse_mode="HTML")
    for story in rows:
        await message.answer(f"📥 <b>#{story['id']}</b> · {story['status']}\n👤 User ID: <code>{story['user_id']}</code>\n🏷 {escape(str(story['category'] or 'другое'))}\n\n{escape(story['text'][:800])}",parse_mode="HTML",reply_markup=moderation_keyboard(story['id'],story['user_id']) if story['status']=='waiting' else None)

@router.message(F.text == "⭐ Избранное")
async def favorites_menu(message: Message):
    if not is_admin(message.from_user.id): return
    rows=get_favorite_stories(30)
    if not rows: await message.answer("⭐ Избранных историй пока нет.",reply_markup=admin_keyboard); return
    await message.answer(f"⭐ <b>Избранное: {len(rows)}</b>",parse_mode="HTML")
    for story in rows:
        await message.answer(f"⭐ <b>История #{story['id']}</b>\n👤 User ID: <code>{story['user_id']}</code>\n🏷 {escape(str(story['category'] or 'другое'))}\n\n{escape(story['text'][:800])}",parse_mode="HTML",reply_markup=moderation_keyboard(story['id'],story['user_id']) if story['status']=='waiting' else None)

@router.message(F.text == "📈 Аналитика")
async def analytics_menu(message: Message):
    if not is_admin(message.from_user.id): return
    d=get_analytics()
    cats="\n".join(f"• {escape(str(k))}: {v}" for k,v in d['categories']) or "• нет данных"
    recent="\n".join(f"• {day}: {n}" for day,n in d['recent']) or "• нет данных"
    await message.answer("📈 <b>Аналитика проекта</b>\n\n" f"👥 Пользователей: {d['users']}\n📚 Историй: {d['total']}\n⏳ На модерации: {d['waiting']}\n✅ Опубликовано: {d['published']}\n❌ Отклонено: {d['rejected']}\n⭐ Избранных: {d['favorites']}\n💬 Диалогов: {d['dialogs']}\n\n🏷 <b>Темы:</b>\n{cats}\n\n📅 <b>Последние дни:</b>\n{recent}",parse_mode="HTML",reply_markup=admin_keyboard)

# =========================================================
# ADMIN — BACK
# =========================================================

@router.message(F.text == "⬅️ Назад")
async def back(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if is_admin(message.from_user.id):
        await message.answer(
            "👤 <b>Режим пользователя</b>",
            parse_mode="HTML",
            reply_markup=admin_user_keyboard,
        )

    else:
        await message.answer(
            "↩️ <b>Главное меню</b>",
            parse_mode="HTML",
            reply_markup=main_keyboard,
        )
