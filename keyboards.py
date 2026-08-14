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
    Создаёт ссылку на сообщение Telegram-канала.

    Публичный канал:
        @my_channel
        https://t.me/my_channel/123

    Приватный канал:
        -1001234567890
        https://t.me/c/1234567890/123
    """

    channel_id = str(CHANNEL_ID).strip()

    if channel_id.startswith("-100"):
        internal_id = channel_id[4:]
        return (
            f"https://t.me/c/"
            f"{internal_id}/{message_id}"
        )

    if channel_id.startswith("@"):
        username = channel_id[1:]
        return (
            f"https://t.me/"
            f"{username}/{message_id}"
        )

    # Если указано имя канала без @
    return (
        f"https://t.me/"
        f"{channel_id}/{message_id}"
    )


def get_channel_first_message_url() -> str:
    """
    Переход к первому сообщению канала.
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
                    text=(
                        "📞 Пусть со мной "
                        "свяжется сотрудник"
                    ),
                    callback_data=(
                        "support_method:personal"
                    ),
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
                    text=(
                        "📞 Связаться со мной лично"
                    ),
                    callback_data=(
                        "support_personal_request"
                    ),
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


# =========================================================
# STORIES — VIEW PUBLISHED STORY
# =========================================================

def view_published_story_keyboard(
    message_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👀 Посмотреть",
                    url=get_channel_message_url(
                        message_id
                    ),
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
                    callback_data=(
                        f"edit:{story_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=(
                        f"publish:{story_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=(
                        f"reject:{story_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 Написать пользователю",
                    callback_data=(
                        f"contact:{story_id}"
                    ),
                ),
            ],
        ],
    )


# =========================================================
# SUPPORT — NEW MESSAGE
# =========================================================

def support_new_message_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Открыть диалог",
                    callback_data=(
                        f"dialog_open:{dialog_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📞 Связаться лично",
                    callback_data=(
                        f"dialog_personal:{dialog_id}"
                    ),
                ),
            ],
        ],
    )


# =========================================================
# SUPPORT — ACTIVE DIALOG
# =========================================================

def support_dialog_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Связаться лично",
                    callback_data=(
                        f"dialog_personal:{dialog_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🟠 Ожидает пользователя",
                    callback_data=(
                        f"dialog_waiting:{dialog_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Выйти из диалога",
                    callback_data=(
                        f"dialog_exit:{dialog_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🔴 Закрыть диалог",
                    callback_data=(
                        f"dialog_close:{dialog_id}"
                    ),
                ),
            ],
        ],
    )


# =========================================================
# PERSONAL REQUEST — ADMIN
# =========================================================

def personal_request_keyboard(
    dialog_id: int,
    user_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        "👤 Открыть профиль "
                        "пользователя"
                    ),
                    url=f"tg://user?id={user_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💬 Открыть диалог",
                    callback_data=(
                        f"dialog_open:{dialog_id}"
                    ),
                ),
            ],
        ],
    )
