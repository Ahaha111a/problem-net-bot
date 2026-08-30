from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo

from config import ADMIN_MINIAPP_URL, FOUNDER_URL, CHANNEL_ID


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Поделиться историей")],
            [KeyboardButton(text="📖 Смотреть истории")],
            [KeyboardButton(text="💡 Совет дня"), KeyboardButton(text="📚 Полезные материалы")],
            [KeyboardButton(text="🆘 Экстренная поддержка"), KeyboardButton(text="❤️ Поддержка")],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def admin_keyboard() -> ReplyKeyboardMarkup:
    rows = []
    if ADMIN_MINIAPP_URL:
        rows.append([KeyboardButton(text="🖥 Админ-панель", web_app=WebAppInfo(url=ADMIN_MINIAPP_URL))])
    if FOUNDER_URL:
        rows.append([KeyboardButton(text="👑 Кабинет основателя", web_app=WebAppInfo(url=FOUNDER_URL))])
    rows.extend([
        [KeyboardButton(text="⏳ Модерация"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📁 Все истории"), KeyboardButton(text="⬅️ Назад")],
    ])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, is_persistent=True)


def moderation_keyboard(story_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"story:publish:{story_id}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"story:reject:{story_id}")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"story:edit:{story_id}"),
         InlineKeyboardButton(text="🤖 ИИ-модерация", callback_data=f"story:ai:{story_id}")],
        [InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f"story:lock:{story_id}")],
    ])


def channel_story_keyboard(story_id: int, link: str | None = None, reactions=None) -> InlineKeyboardMarkup:
    buttons = []
    if link:
        buttons.append([InlineKeyboardButton(text="👀 Посмотреть", url=link)])
    if reactions is not None:
        buttons.append([InlineKeyboardButton(text=f"❤️ {reactions.get('heart', 0)}", callback_data=f"react:{story_id}:heart"),
                        InlineKeyboardButton(text=f"💙 {reactions.get('support', 0)}", callback_data=f"react:{story_id}:support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def published_story_keyboard(link: str | None, story_id: int, reactions=None) -> InlineKeyboardMarkup:
    rows = []
    if link:
        rows.append([InlineKeyboardButton(text="👀 Посмотреть", url=link)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆘 Начать разговор", callback_data="support:start")],
    ])
