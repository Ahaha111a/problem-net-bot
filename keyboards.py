from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import CHANNEL_ID


# =========================================================
# CHANNEL HELPERS
# =========================================================

def get_channel_message_url(message_id: int) -> str:
    """
    Создаёт ссылку на конкретное сообщение канала.

    Для приватного/числового ID:
    -1001234567890 -> https://t.me/c/1234567890/123

    Для публичного канала с @username:
    @my_channel -> https://t.me/my_channel/123
    """

    channel_id = str(CHANNEL_ID).strip()

    if channel_id.startswith("-100"):
        internal_id = channel_id[4:]
        return f"https://t.me/c/{internal_id}/{message_id}"

    if channel_id.startswith("@"):
        username = channel_id[1:]
        return f"https://t.me/{username}/{message_id}"

    # Если в CHANNEL_ID указано имя без @
    return f"https://t.me/{channel_id}/{message_id}"


def get_channel_first_message_url() -> str:
    """
    Ссылка на самое первое сообщение канала.
    """

    return get_channel_message_url(1)


# =========================================================
# USER MENU
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📝 Поделиться историей"
            ),
        ],
        [
            KeyboardButton(
                text="💡 Совет дня"
            ),
            KeyboardButton(
                text="📚 Полезные материалы"
            ),
        ],
        [
            KeyboardButton(
                text="🆘 Экстренная поддержка"
            ),
        ],
        [
            KeyboardButton(
                text="📖 Смотреть истории"
            ),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# ADMIN — USER MODE
# =========================================================

admin_user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📝 Поделиться историей"
            ),
        ],
        [
            KeyboardButton(
                text="💡 Совет дня"
            ),
            KeyboardButton(
                text="📚 Полезные материалы"
            ),
        ],
        [
            KeyboardButton(
                text="🆘 Экстренная поддержка"
            ),
        ],
        [
            KeyboardButton(
                text="📖 Смотреть истории"
            ),
        ],
        [
            KeyboardButton(
                text="👨‍💼 Админ-панель"
            ),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# ADMIN PANEL
# =========================================================

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="⏳ Модерация"
            ),
            KeyboardButton(
                text="📊 Статистика"
            ),
        ],
        [
            KeyboardButton(
                text="💬 Диалоги"
            ),
        ],
        [
            KeyboardButton(
                text="📁 Все истории"
            ),
        ],
        [
            KeyboardButton(
                text="👤 Режим пользователя"
            ),
        ],
        [
            KeyboardButton(
                text="⬅️ Назад"
            ),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# SUPPORT METHOD
# =========================================================

def support_method_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Продолжить в боте",
                    callback_data="support_method:bot",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📞 Пусть со мной свяжется сотрудник",
                    callback_data="support_method:personal",
                ),
            ],
        ],
    )


# =========================================================
# PERSONAL CONTACT — USER
# =========================================================

def personal_contact_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Связаться со мной лично",
                    callback_data="support_personal_request",
                ),
            ],
        ],
    )


# =========================================================
# MATERIALS
# =========================================================

def material_actions_keyboard():
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


# =========================================================
# STORIES — VIEW CHANNEL
# =========================================================

def view_stories_keyboard():
    """
    Кнопка для перехода к историям в канале.
    Открывает первое сообщение канала.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📖 Смотреть истории",
                    url=get_channel_first_message_url(),
                ),
            ],
        ],
    )


def view_published_story_keyboard(
    message_id: int,
):
    """
    Кнопка для перехода непосредственно
    к опубликованной истории.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👀 Посмотреть",
                    url=get_channel_message_url(message_id),
                ),
            ],
        ],
    )


# =========================================================
# STORIES — MODERATION
# =========================================================

def moderation_keyboard(
    story_id: int,
    user_id: int,
):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=f"edit:{story_id}",
                ),
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"publish:{story_id}",
                ),
            ],
