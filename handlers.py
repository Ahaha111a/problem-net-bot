from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states import StoryState
from config import ADMIN_ID
from database import save_story
from ai import analyze_story
from post_generator import create_post
from keyboards import moderation_keyboard


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

    story_id = save_story(
        message.from_user.id,
        story
    )

    await message.answer(
        "🤖 Анализирую вашу историю..."
    )

    try:
    print("Запускаю анализ истории")

    ai_result = await analyze_story(story)

    print("Анализ готов")

    post_text = await create_post(story)

    print("Пост готов")

except Exception as e:
    ai_result = f"Ошибка ИИ: {e}"
    post_text = "Не удалось создать пост"
    print(f"Ошибка ИИ: {e}")

    except Exception as e:
        ai_result = f"Ошибка ИИ: {e}"
        post_text = "Не удалось создать пост"
        print(f"Ошибка ИИ: {e}")

    await message.bot.send_message(
    ADMIN_ID,
    f"📥 <b>Новая история #{story_id}</b>\n\n"
    f"👤 Пользователь: {message.from_user.id}\n\n"
    f"💭 Текст:\n{story}\n\n"
    f"🤖 <b>Анализ ИИ:</b>\n\n"
    f"{ai_result}\n\n"
    f"━━━━━━━━━━━━━━\n\n"
    f"📌 <b>Готовый пост:</b>\n\n"
    f"{post_text}",
    reply_markup=moderation_keyboard()
)

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    await state.clear()
