from aiogram import Router, F
from aiogram.types import Message

from config import ADMIN_IDS
from keyboards import admin_keyboard

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text == "/start")
async def start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("Этот бот предназначен для сотрудников проекта.")
        return
    await message.answer("🛡 <b>Панель сотрудников</b>\n\nВыберите нужный раздел.", reply_markup=admin_keyboard())


@router.message(F.text == "🖥 Админ-панель")
async def admin_app(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🖥 Откройте Mini App через кнопку выше.", reply_markup=admin_keyboard())
