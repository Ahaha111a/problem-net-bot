from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# Главное меню

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📝 Поделиться историей")
        ],
        [
            KeyboardButton(text="💡 Совет дня"),
            KeyboardButton(text="📚 Полезные материалы")
        ],
        [
            KeyboardButton(text="❤️ Поддержка")
        ],
        [
            KeyboardButton(text="👨‍💼 Админ-панель")
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)


# Панель администратора

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="⏳ Модерация")
        ],
        [
            KeyboardButton(text="📁 Все истории"),
            KeyboardButton(text="📢 Последний пост")
        ],
        [
            KeyboardButton(text="⬅️ Назад")
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Панель администратора"
)


# Кнопки модерации

def moderation_keyboard(story_id: int):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=f"publish:{story_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=f"edit:{story_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reject:{story_id}"
                )
            ]
        ]
    )

    return keyboard
