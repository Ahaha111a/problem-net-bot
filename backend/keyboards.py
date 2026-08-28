import os

from aiogram.types import (
    ReplyKeyboardMarkup,
    WebAppInfo,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Поделиться историей")],
        [KeyboardButton(text="💡 Совет дня"), KeyboardButton(text="📚 Полезные материалы")],
        [KeyboardButton(text="🆘 Экстренная поддержка")],
        [KeyboardButton(text="📖 Смотреть истории")],
    ],
    resize_keyboard=True,
)


admin_user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Поделиться историей")],
        [KeyboardButton(text="💡 Совет дня"), KeyboardButton(text="📚 Полезные материалы")],
        [KeyboardButton(text="🆘 Экстренная поддержка")],
        [KeyboardButton(text="📖 Смотреть истории")],
    ],
    resize_keyboard=True,
)


admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🖥 Открыть Mini App")],
        [KeyboardButton(text="⏳ Модерация"), KeyboardButton(text="💬 Диалоги")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="📈 Аналитика")],
        [KeyboardButton(text="🗓 Планировщик"), KeyboardButton(text="📁 Все истории")],
        [KeyboardButton(text="👥 Роли администраторов"), KeyboardButton(text="📜 Журнал действий")],
        [KeyboardButton(text="⬅️ Назад")],
    ],
    resize_keyboard=True,
)


def admin_miniapp_keyboard():
    url = os.getenv("ADMIN_MINIAPP_URL", "").strip()
    if not url:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ ADMIN_MINIAPP_URL не настроен", callback_data="admin_miniapp_missing")]
        ])
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥 Открыть панель модератора", web_app=WebAppInfo(url=url))]
    ])


def support_method_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Продолжить в боте", callback_data="support_method:bot")],
        [InlineKeyboardButton(text="📞 Пусть со мной свяжется сотрудник", callback_data="support_method:personal")],
    ])


def personal_contact_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Связаться со мной лично", callback_data="support_personal_request")],
    ])


def material_actions_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Нужна поддержка", callback_data="material:support")],
    ])


def moderation_keyboard(story_id: int, user_id: int, scheduled: bool = False):
    schedule_row = [
        InlineKeyboardButton(text="❌ Снять расписание", callback_data=f"schedule_cancel:{story_id}")
    ] if scheduled else [
        InlineKeyboardButton(text="🗓 Запланировать", callback_data=f"schedule:{story_id}")
    ]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=f"edit:{story_id}"),
            InlineKeyboardButton(text="🔄 Повторить ИИ", callback_data=f"ai_retry:{story_id}"),
        ],
        [
            InlineKeyboardButton(text="👀 Предпросмотр", callback_data=f"preview:{story_id}"),
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish:{story_id}"),
        ],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{story_id}"), InlineKeyboardButton(text="🛡 Проверка ИИ", callback_data=f"ai_moderate:{story_id}")],
        [InlineKeyboardButton(text="👤 Написать пользователю", callback_data=f"contact:{story_id}")],
        schedule_row,
    ])


def _reaction_buttons(story_id: int, counts: dict | None = None, selected: str | None = None):
    counts = counts or {"heart": 0, "understand": 0, "support": 0}

    def label(key, emoji):
        mark = " ✓" if selected == key else ""
        return f"{emoji} {counts.get(key, 0)}{mark}"

    return [
        InlineKeyboardButton(text=label("heart", "❤️"), callback_data=f"reaction:{story_id}:heart"),
        InlineKeyboardButton(text=label("understand", "💙"), callback_data=f"reaction:{story_id}:understand"),
        InlineKeyboardButton(text=label("support", "🤝"), callback_data=f"reaction:{story_id}:support"),
    ]


def channel_story_keyboard(story_id: int, message_link: str | None = None, counts: dict | None = None, selected: str | None = None):
    buttons = [_reaction_buttons(story_id, counts, selected)]
    if message_link:
        buttons.append([InlineKeyboardButton(text="👀 Посмотреть", url=message_link)])
    buttons.append([InlineKeyboardButton(text="⚠️ Пожаловаться", callback_data=f"complaint:{story_id}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def published_story_keyboard(message_link: str, story_id: int | None = None, counts: dict | None = None):
    rows = []
    if story_id is not None:
        rows.append(_reaction_buttons(story_id, counts))
    rows.append([InlineKeyboardButton(text="👀 Посмотреть", url=message_link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_new_message_keyboard(dialog_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Открыть диалог", callback_data=f"dialog_open:{dialog_id}")],
        [InlineKeyboardButton(text="📞 Связаться лично", callback_data=f"dialog_personal:{dialog_id}")],
    ])


def support_dialog_keyboard(dialog_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📞 Связаться лично", callback_data=f"dialog_personal:{dialog_id}")],
        [InlineKeyboardButton(text="🟠 Ожидает пользователя", callback_data=f"dialog_waiting:{dialog_id}")],
        [InlineKeyboardButton(text="🟢 Решён", callback_data=f"dialog_resolved:{dialog_id}")],
        [InlineKeyboardButton(text="⬅️ Выйти из диалога", callback_data=f"dialog_exit:{dialog_id}")],
        [InlineKeyboardButton(text="🔴 Закрыть диалог", callback_data=f"dialog_close:{dialog_id}")],
    ])


def personal_request_keyboard(dialog_id: int, user_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Открыть профиль пользователя", url=f"tg://user?id={user_id}")],
        [InlineKeyboardButton(text="💬 Открыть диалог", callback_data=f"dialog_open:{dialog_id}")],
    ])


def schedule_keyboard(story_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏰ Через 1 час", callback_data=f"schedule_set:{story_id}:1h")],
        [InlineKeyboardButton(text="⏰ Через 3 часа", callback_data=f"schedule_set:{story_id}:3h")],
        [InlineKeyboardButton(text="🌅 Завтра 12:00", callback_data=f"schedule_set:{story_id}:tomorrow")],
        [InlineKeyboardButton(text="🕐 Указать любое время", callback_data=f"schedule_custom:{story_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"schedule_cancel_ui:{story_id}")],
    ])
