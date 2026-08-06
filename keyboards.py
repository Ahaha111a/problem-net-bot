from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
)

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
        ]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие..."
)

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def moderation_keyboard():

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data="publish"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data="edit"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data="reject"
                )
            ]
        ]
    )

    return keyboard2
