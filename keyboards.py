from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
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


def moderation_keyboard(story_id: int):

    return InlineKeyboardMarkup(
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
