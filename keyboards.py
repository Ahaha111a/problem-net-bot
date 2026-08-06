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
