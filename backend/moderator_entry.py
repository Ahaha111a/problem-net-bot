from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config import ADMIN_IDS
from keyboards import admin_miniapp_keyboard

router = Router()

moderator_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='🖥 Открыть Mini App')],
        [KeyboardButton(text='⏳ Модерация'), KeyboardButton(text='💬 Диалоги')],
        [KeyboardButton(text='📊 Статистика'), KeyboardButton(text='📈 Аналитика')],
        [KeyboardButton(text='🗓 Планировщик'), KeyboardButton(text='📁 Все истории')],
        [KeyboardButton(text='👥 Роли администраторов'), KeyboardButton(text='📜 Журнал действий')],
    ], resize_keyboard=True
)


def allowed(uid):
    return uid in ADMIN_IDS

@router.message(Command('start'))
async def start(message: Message):
    if not allowed(message.from_user.id):
        await message.answer('⛔ Этот бот предназначен только для сотрудников.')
        return
    await message.answer(
        '🛡 <b>Центр сотрудников «Проблем нет»</b>\n\n'
        'Ежедневная работа выполняется в Mini App.\n\n'
        '🖥 Откройте панель ниже.',
        parse_mode='HTML', reply_markup=moderator_menu
    )
    await message.answer('🖥 <b>Открыть Mini App</b>', parse_mode='HTML', reply_markup=admin_miniapp_keyboard())

@router.message(Command('panel'))
@router.message(F.text == '🖥 Открыть Mini App')
async def panel(message: Message):
    if not allowed(message.from_user.id): return
    await message.answer('🖥 <b>Панель сотрудников</b>', parse_mode='HTML', reply_markup=admin_miniapp_keyboard())
