from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from states import StoryState
from config import ADMIN_ID
from database import save_story, save_post
from ai import analyze_story
from post_generator import create_post
from keyboards import main_keyboard, moderation_keyboard


router = Router()


@router.message(Command("start"))
async def start_command(message: Message):

    await message.answer(
        "👋 Добро пожаловать в «Проблем нет»\n\n"
        "Это пространство, где можно поделиться тем, "
        "что тревожит, беспокоит или давно лежит внутри.\n\n"
        "💙 Здесь:\n"
        "• истории рассматриваются анонимно;\n"
        "• нет осуждения и оценок;\n"
        "• каждая история может помочь кому-то ещё.\n\n"
        "📝 Нажмите кнопку ниже и расскажите свою историю.\n\n"
        "Помните: проблем нет. ",
        reply_markup=main_keyboard
    )


@router.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "💡 Как пользоваться ботом:\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал для публикации.\n\n"
        "Спасибо за доверие 💙"
    )


@router.message(F.text == "📝 Поделиться историей")
async def start_story(message: Message, state: FSMContext):

    await state.set_state(
        StoryState.waiting_for_story
    )

    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит."
    )


@router.message(StoryState.waiting_for_story)
async def receive_story(
    message: Message,
    state: FSMContext
):

    story = message.text


    story_id = save_story(
        message.from_user.id,
        story
    )


    await message.answer(
        "🤖 Анализирую вашу историю..."
    )


    try:

        ai_result = await analyze_story(story)

        post_text = await create_post(story)

        save_post(
            story_id,
            post_text
        )


    except Exception as e:

        print(
            f"Ошибка ИИ: {e}"
        )

        ai_result = "Не удалось выполнить анализ."
        post_text = "Не удалось создать пост."


    await message.bot.send_message(
        ADMIN_ID,

        f"📥 <b>Новая история #{story_id}</b>\n\n"
        f"👤 Пользователь: {message.from_user.id}\n\n"
        f"💭 <b>Текст:</b>\n"
        f"{story}\n\n"
        f"🤖 <b>Анализ ИИ:</b>\n"
        f"{ai_result}\n\n"
        f"━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Готовый пост:</b>\n\n"
        f"{post_text}",

        reply_markup=moderation_keyboard(
            story_id
        ),

        parse_mode="HTML"
    )


    await message.answer(
        "💙 Спасибо, что поделились.\n"
        "Ваша история отправлена на рассмотрение."
    )


    await state.clear()



@router.message(StoryState.waiting_for_edit)
async def edit_post(
    message: Message,
    state: FSMContext
):

    data = await state.get_data()

    story_id = data.get(
        "edit_story_id"
    )


    save_post(
        story_id,
        message.text
    )


    await message.answer(
        "✅ Новый текст поста сохранён."
    )


    await state.clear()
    @router.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "💡 Как пользоваться ботом:\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите, что вас беспокоит.\n"
        "3️⃣ История будет обработана анонимно.\n\n"
        "Спасибо, что доверяете нам 💙"
    )
