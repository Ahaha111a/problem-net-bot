"""Notifications sent by the user-facing bot.

The moderator bot must never be used to initiate a private chat with an end user:
users started the User Bot, not the Moderator Bot. This helper keeps that boundary
explicit and centralised.
"""
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN


async def notify_user(user_id: int, text: str, reply_markup=None) -> bool:
    if not BOT_TOKEN:
        return False
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot.send_message(int(user_id), text, reply_markup=reply_markup)
        return True
    finally:
        await bot.session.close()
