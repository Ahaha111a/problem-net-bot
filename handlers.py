from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from states import StoryState
from config import ADMIN_IDS

from database import (
    create_story,
    update_ai_result,
    update_post,
    get_waiting_stories,
    get_all_stories,
    get_stats,
)

from ai import analyze_story
from post_generator import create_post

from keyboards import (
    main_keyboard,
    admin_keyboard,
    moderation_keyboard,
)


router = Router()


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

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
        "Помните: проблем нет.",
        reply_markup=main_keyboard,
    )

    if is_admin(message.from_user.id):
        await message.answer(
            "👨‍💼 Вы вошли как администратор.\n"
            "Для управления проектом используйте "
            "админ-панель.",
            reply_markup=admin_keyboard,
        )


# =========================================================
# HELP
# =========================================================

@router.message(Command("help"))
async def help_command(message: Message):

    await message.answer(
        "💡 Как пользоваться ботом:\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал для публикации.\n"
        "4️⃣ Администратор проверит материал.\n\n"
        "Спасибо за доверие 💙"
    )


# =========================================================
# ПОДЕЛИТЬСЯ ИСТОРИЕЙ
# =========================================================

@router.message(F.text == "📝 Поделиться историей")
async def start_story(
    message: Message,
    state: FSMContext,
):

    await state.set_state(
        StoryState.waiting_for_story
    )

    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит.\n\n"
        "🔒 История будет обработана анонимно."
    )


# =========================================================
# ПОЛУЧЕНИЕ ИСТОРИИ
# =========================================================

@router.message(StoryState.waiting_for_story)
async def receive_story(
    message: Message,
    state: FSMContext,
):

    story = message.text

    if not story:
        await message.answer(
            "❗ Отправьте историю обычным текстовым сообщением."
        )
        return

    story = story.strip()

    if len(story) < 10:
        await message.answer(
            "✏️ История слишком короткая.\n\n"
            "Напишите немного подробнее."
        )
        return

    story_id = create_story(
        user_id=message.from_user.id,
        text=story,
    )

    await message.answer(
        "🤖 Анализирую вашу историю..."
    )

    # =====================================================
    # АНАЛИЗ ИИ
    # =====================================================

    try:

        ai_result = await analyze_story(
            story
        )

    except Exception as error:

        print(
            f"AI ERROR: {error}"
        )

        ai_result = (
            "Не удалось выполнить анализ."
        )

    update_ai_result(
        story_id,
        ai_result,
    )

    # =====================================================
    # СОЗДАНИЕ ПОСТА
    # =====================================================

    try:

        post_text = await create_post(
            story
        )

    except Exception as error:

        print(
            f"POST ERROR: {error}"
        )

        post_text = (
            "Не удалось создать пост."
        )

    update_post(
        story_id,
        post_text,
    )

    # =====================================================
    # СООБЩЕНИЕ МОДЕРАТОРУ
    # =====================================================

    moderation_text = (
        f"📥 <b>Новая история #{story_id}</b>\n\n"
        f"👤 <b>User ID:</b> "
        f"<code>{message.from_user.id}</code>\n\n"
        "🔒 История отправлена анонимно.\n\n"
        "💭 <b>Текст:</b>\n\n"
        f"{story}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🤖 <b>Анализ ИИ:</b>\n\n"
        f"{ai_result}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "📌 <b>Готовый пост:</b>\n\n"
        f"{post_text}"
    )

    for admin_id in ADMIN_IDS:

        try:

            await message.bot.send_message(
                admin_id,
                moderation_text,
                reply_markup=moderation_keyboard(
                    story_id,
                    message.from_user.id,
                ),
                parse_mode="HTML",
            )

        except Exception as error:

            print(
                f"ADMIN SEND ERROR: {error}"
            )

    # =====================================================
    # ОТВЕТ ПОЛЬЗОВАТЕЛЮ
    # =====================================================

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    await state.clear()


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

@router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    stats = get_stats()

    await message.answer(
        "👨‍💼 <b>Панель администратора</b>\n\n"
        f"⏳ На модерации: {stats['waiting']}\n"
        f"📚 Всего историй: {stats['total']}\n"
        f"✅ Опубликовано: {stats['published']}\n"
        f"❌ Отклонено: {stats['rejected']}\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# МОДЕРАЦИЯ
# =========================================================

@router.message(F.text == "⏳ Модерация")
async def moderation(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    stories = get_waiting_stories()

    if not stories:

        await message.answer(
            "🟢 На модерации сейчас ничего нет.",
            reply_markup=admin_keyboard,
        )

        return

    await message.answer(
        f"⏳ <b>На модерации: {len(stories)}</b>",
        parse_mode="HTML",
    )

    for story in stories[:20]:

        await message.answer(
            f"📥 <b>История #{story['id']}</b>\n\n"
            f"👤 User ID: "
            f"<code>{story['user_id']}</code>\n\n"
            f"{story['text']}",
            parse_mode="HTML",
            reply_markup=moderation_keyboard(
                story["id"],
                story["user_id"],
            ),
        )


# =========================================================
# СТАТИСТИКА
# =========================================================

@router.message(F.text == "📊 Статистика")
async def statistics(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    stats = get_stats()

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"📚 Всего историй: {stats['total']}\n\n"
        f"⏳ На модерации: {stats['waiting']}\n"
        f"✅ Опубликовано: {stats['published']}\n"
        f"❌ Отклонено: {stats['rejected']}",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ВСЕ ИСТОРИИ
# =========================================================

@router.message(F.text == "📁 Все истории")
async def all_stories(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    stories = get_all_stories()

    if not stories:

        await message.answer(
            "📁 Историй пока нет.",
            reply_markup=admin_keyboard,
        )

        return

    text = "📁 <b>Все истории</b>\n\n"

    for story in stories[:30]:

        status = story["status"]

        if status == "waiting":
            status_icon = "⏳"
        elif status == "published":
            status_icon = "✅"
        elif status == "rejected":
            status_icon = "❌"
        else:
            status_icon = "📌"

        text += (
            f"{status_icon} #{story['id']} — "
            f"{status}\n"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# НАЗАД
# =========================================================

@router.message(F.text == "⬅️ Назад")
async def back(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    await message.answer(
        "↩️ Главное меню",
        reply_markup=main_keyboard,
    )
