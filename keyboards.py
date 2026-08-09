from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================================================
# ГЛАВНОЕ МЕНЮ ПОЛЬЗОВАТЕЛЯ
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
                text="⬅️ Назад"
            ),
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# ВЫБОР СПОСОБА ЭКСТРЕННОЙ ПОДДЕРЖКИ
# =========================================================

def support_method_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Продолжить в боте",
                    callback_data="support_method:bot",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📞 Пусть со мной свяжется сотрудник",
                    callback_data="support_method:personal",
                )
            ],
        ]
    )


# =========================================================
# ПОЛЬЗОВАТЕЛЬ МОЖЕТ ЗАПРОСИТЬ ЛИЧНЫЙ КОНТАКТ
# =========================================================

def personal_contact_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Связаться со мной лично",
                    callback_data="support_personal_request",
                )
            ]
        ]
    )


# =========================================================
# МОДЕРАЦИЯ ИСТОРИИ
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
# НОВОЕ СООБЩЕНИЕ В ДИАЛОГЕ
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
            ],
            [
                InlineKeyboardButton(
                    text="📞 Связаться лично",
                    callback_data=f"dialog_personal:{dialog_id}",
                )
            ],
        ]
    )


# =========================================================
# УПРАВЛЕНИЕ ОТКРЫТЫМ ДИАЛОГОМ
# =========================================================

def support_dialog_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Связаться лично",
                    callback_data=f"dialog_personal:{dialog_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Выйти из диалога",
                    callback_data=f"dialog_exit:{dialog_id}",
                )
            ],
        ]
    )


# =========================================================
# ЗАПРОС ЛИЧНОГО КОНТАКТА ДЛЯ МОДЕРАТОРА
# =========================================================

def personal_request_keyboard(
    dialog_id: int,
    user_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Открыть профиль пользователя",
                    url=f"tg://user?id={user_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💬 Открыть диалог",
                    callback_data=f"dialog_open:{dialog_id}",
                )
            ],
        ]
    )
