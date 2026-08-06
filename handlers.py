from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states import StoryState
from config import ADMIN_ID


router = Router()


@router.message(F.text == "📝 Поделиться историей")
async def start_story(message: Message, state: FSMContext):
    await state.set_state(StoryState.waiting_for_story)

    await message.answer(
        "💙 Расскажите, что вас беспокоит.\n\n"
        "Напишите всё одним сообщением. "
        "Ваша история будет рассмотрена анонимно."
    )


@router.message(StoryState.waiting_for_story)
async def receive_story(message: Message, state: FSMContext):

    story = message.text

    await message.bot.send_message(
        ADMIN_ID,
        "📥 Новая история:\n\n"
        f"{story}"
    )

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    await state.clear()
