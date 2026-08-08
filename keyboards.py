from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================================================
# ГЛАВНОЕ МЕНЮ
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📝 Поделиться историей"
            )
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
    ],
    resize_keyboard=True,
)


# =========================================================
# АДМИН-ПАНЕЛЬ
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
                text="📁 Все истории"
            ),
        ],
        [
            KeyboardButton(
                text="💬 Диалоги"
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
# МОДЕРАЦИЯ
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
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{story_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 Написать пользователю",
                    callback_data=f"contact:{story_id}",
                ),
            ],
        ]
    )


# =========================================================
# КНОПКА НОВОГО ДИАЛОГА
# =========================================================

def support_new_message_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Открыть диалог",
                    callback_data=f"dialog_open:{dialog_id}",
                )
            ]
        ]
    )


# =========================================================
# КНОПКИ ВНУТРИ ДИАЛОГА
# =========================================================

def support_dialog_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ К диалогам",
                    callback_data=f"dialog_exit:{dialog_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔴 Закрыть диалог",
                    callback_data=f"dialog_close:{dialog_id}",
                )
            ],
        ]
    )


# =========================================================
# СПИСОК ДИАЛОГОВ
# =========================================================

def dialog_list_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Открыть",
                    callback_data=f"dialog_open:{dialog_id}",
                )
            ]
        ]
    )
