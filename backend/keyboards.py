from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from config import ADMIN_MINIAPP_URL, FOUNDER_URL, CHANNEL_ID, CHANNEL_USERNAME, CHANNEL_FIRST_MESSAGE_ID

def _channel_first_url():
    if CHANNEL_USERNAME:
        return f"https://t.me/{CHANNEL_USERNAME}/{CHANNEL_FIRST_MESSAGE_ID}"
    raw=str(CHANNEL_ID)
    if raw.startswith('-100'):
        return f"https://t.me/c/{raw[4:]}/{CHANNEL_FIRST_MESSAGE_ID}"
    return ''

def main_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text='📝 Поделиться историей')],
        [KeyboardButton(text='📖 Смотреть истории')],
        [KeyboardButton(text='💡 Совет дня'),KeyboardButton(text='📚 Полезные материалы')],
        [KeyboardButton(text='🆘 Экстренная поддержка'),KeyboardButton(text='❤️ Поддержка')],
    ],resize_keyboard=True,is_persistent=True)

def admin_keyboard():
    rows=[]
    if ADMIN_MINIAPP_URL: rows.append([KeyboardButton(text='🖥 Админ-панель',web_app=WebAppInfo(url=ADMIN_MINIAPP_URL))])
    if FOUNDER_URL: rows.append([KeyboardButton(text='👑 Кабинет основателя',web_app=WebAppInfo(url=FOUNDER_URL))])
    rows += [
        [KeyboardButton(text='⏳ Модерация'),KeyboardButton(text='📊 Статистика')],
        [KeyboardButton(text='💬 Поддержка'),KeyboardButton(text='📈 KPI')],
        [KeyboardButton(text='🖥 Мониторинг'),KeyboardButton(text='🤖 AI Control')],
        [KeyboardButton(text='👥 Сотрудники'),KeyboardButton(text='🎓 Обучение')],
        [KeyboardButton(text='👑 Founder Center')],
        [KeyboardButton(text='📁 Все истории')],
    ]
    return ReplyKeyboardMarkup(keyboard=rows,resize_keyboard=True,is_persistent=True)

def moderation_keyboard(story_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='✅ Опубликовать',callback_data=f'story:publish:{story_id}'),InlineKeyboardButton(text='❌ Отклонить',callback_data=f'story:reject:{story_id}')],
        [InlineKeyboardButton(text='✏️ Редактировать',callback_data=f'story:edit:{story_id}'),InlineKeyboardButton(text='🤖 ИИ-проверка',callback_data=f'story:ai:{story_id}')],
        [InlineKeyboardButton(text='🔒 Заблокировать',callback_data=f'story:lock:{story_id}'),InlineKeyboardButton(text='🔓 Разблокировать',callback_data=f'story:unlock:{story_id}')],
    ])

def channel_story_keyboard(story_id,link=None,reactions=None):
    rows=[]
    if link: rows.append([InlineKeyboardButton(text='👀 Посмотреть',url=link)])
    if reactions is not None: rows.append([InlineKeyboardButton(text=f"❤️ {reactions.get('heart',0)}",callback_data=f'react:{story_id}:heart'),InlineKeyboardButton(text=f"💙 {reactions.get('support',0)}",callback_data=f'react:{story_id}:support')])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def published_story_keyboard(link,story_id,reactions=None):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='👀 Посмотреть',url=link)]] if link else [])

def support_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🆘 Начать разговор',callback_data='support:start')]])

def channel_first_keyboard():
    url=_channel_first_url()
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📖 Открыть истории',url=url)]]) if url else InlineKeyboardMarkup(inline_keyboard=[])
