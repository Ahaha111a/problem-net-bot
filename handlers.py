from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

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

from states import StoryState

from keyboards import (
    main_keyboard,
    admin_keyboard,
    moderation_keyboard,
)


router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# =========================================================
# START
# =========================================================

@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит.",
        reply_markup=main_keyboard,
    )


# =========================================================
# HELP
# =========================================================

@router.message(F.text == "/help")
async def help_handler(message: Message):
    await message.answer(
        "ℹ️ Помощь\n\n"
        "📝 Поделиться историей — отправить свою историю анонимно.\n\n"
        "💡 Совет дня — получить полезный совет.\n\n"
        "📚 Полезные материалы — полезная информация.\n\n"
        "❤️ Поддержка — слова поддержки."
    )


# =========================================================
# ПОДЕЛИТЬСЯ ИСТОРИЕЙ
# =========================================================

@router.message(F.text == "📝 Поделиться историей")
async def share_story_handler(
    message: Message,
    state: FSMContext,
):
    await state.set_state(
        StoryState.waiting_for_story
    )

    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит."
    )


# =========================================================
# ПОЛУЧЕНИЕ ИСТОРИИ
# =========================================================

@router.message(StoryState.waiting_for_story)
async def receive_story_handler(
    message: Message,
    state: FSMContext,
):
    story = message.text

    if not story:
        await message.answer(
            "❗ Пожалуйста, отправь историю текстом."
        )
        return

    story = story.strip()

    if len(story) < 10:
        await message.answer(
            "✏️ История слишком короткая.\n\n"
            "Попробуй написать немного подробнее."
        )
        return

    await message.answer(
        "⏳ Спасибо. Обрабатываю твою историю..."
    )

    # Сохраняем историю
    story_id = create_story(
        user_id=message.from_user.id,
        text=story,
    )

    # =====================================================
    # АНАЛИЗ ИИ
    # =====================================================

    try:
        ai_result = await analyze_story(story)

        update_ai_result(
            story_id,
            ai_result,
        )

    except Exception as error:
        print(
            f"AI ANALYZE ERROR: {error}"
        )

        ai_result = (
            "Анализ временно недоступен."
        )

        update_ai_result(
            story_id,
            ai_result,
        )

    # =====================================================
    # СОЗДАНИЕ ПОСТА
    # =====================================================

    try:
        post_text = await create_post(story)

        update_post(
            story_id,
            post_text,
        )

    except Exception as error:
        print(
            f"POST GENERATION ERROR: {error}"
        )

        await message.answer(
            "❌ Не удалось подготовить историю "
            "для публикации.\n\n"
            "Попробуй ещё раз немного позже."
        )

        await state.clear()
        return

    # =====================================================
    # ОТВЕТ ПОЛЬЗОВАТЕЛЮ
    # =====================================================

    await message.answer(
        "✅ История получена!\n\n"
        "Она отправлена на модерацию.\n\n"
        "🔒 Твои личные данные не публикуются."
    )

    # =====================================================
    # ОТПРАВКА АДМИНИСТРАТОРАМ
    # =====================================================

    moderation_text = (
        f"📥 <b>Новая история #{story_id}</b>\n\n"
        "🔒 История отправлена анонимно.\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "💭 <b>Исходный текст:</b>\n\n"
        f"{story}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        "🧠 <b>Анализ ИИ:</b>\n\n"
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
                parse_mode="HTML",
                reply_markup=moderation_keyboard(
                    story_id
                ),
            )

        except Exception as error:
            print(
                f"ADMIN SEND ERROR ({admin_id}): {error}"
            )

    await state.clear()


# =========================================================
# СОВЕТ ДНЯ
# =========================================================

@router.message(F.text == "💡 Совет дня")
async def daily_tip_handler(
    message: Message,
):
    await message.answer(
        "💡 <b>Совет дня</b>\n\n"
        "Не требуй от себя решить всю проблему сразу.\n\n"
        "Попробуй выбрать один маленький шаг, "
        "который ты можешь сделать сегодня.",
        parse_mode="HTML",
    )


# =========================================================
# ПОЛЕЗНЫЕ МАТЕРИАЛЫ
# =========================================================

@router.message(F.text == "📚 Полезные материалы")
async def materials_handler(
    message: Message,
):
    await message.answer(
        "📚 <b>Полезные материалы</b>\n\n"
        "Здесь скоро появятся материалы "
        "о тревоге, стрессе, самооценке, отношениях "
        "и эмоциональном состоянии.",
        parse_mode="HTML",
    )


# =========================================================
# ПОДДЕРЖКА
# =========================================================

@router.message(F.text == "❤️ Поддержка")
async def support_handler(
    message: Message,
):
    await message.answer(
        "❤️ Ты не обязан справляться со всем один.\n\n"
        "Иногда уже сам факт того, что ты смог "
        "рассказать о своей проблеме, — важный шаг.\n\n"
        "Береги себя."
    )


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

@router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel_handler(
    message: Message,
):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "👨‍💼 <b>Панель администратора</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# СТАТИСТИКА
# =========================================================

@router.message(F.text == "📊 Статистика")
async def stats_handler(
    message: Message,
):
    if not is_admin(message.from_user.id):
        return

    stats = get_stats()

    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        f"📚 Всего историй: {stats['total']}\n\n"
        f"⏳ На модерации: {stats['waiting']}\n"
        f"✅ Опубликовано: {stats['published']}\n"
        f"❌ Отклонено: {stats['rejected']}",
        parse_mode="HTML",
    )


# =========================================================
# МОДЕРАЦИЯ
# =========================================================

@router.message(F.text == "⏳ Модерация")
async def moderation_handler(
    message: Message,
):
    if not is_admin(message.from_user.id):
        return

    stories = get_waiting_stories()

    if not stories:
        await message.answer(
            "🟢 Сейчас нет историй на модерации."
        )
        return

    await message.answer(
        f"⏳ <b>Истории на модерации: "
        f"{len(stories)}</b>",
        parse_mode="HTML",
    )

    for story in stories[:20]:
        story_id = story["id"]
        text = story["text"]

        await message.answer(
            f"📥 <b>История #{story_id}</b>\n\n"
            f"{text}",
            parse_mode="HTML",
            reply_markup=moderation_keyboard(
                story_id
            ),
        )


# =========================================================
# ВСЕ ИСТОРИИ
# =========================================================

@router.message(F.text == "📁 Все истории")
async def all_stories_handler(
    message: Message,
):
    if not is_admin(message.from_user.id):
        return

    stories = get_all_stories()

    if not stories:
        await message.answer(
            "📁 Историй пока нет."
        )
        return

    text = "📁 <b>Последние истории:</b>\n\n"

    for story in stories[:20]:
        text += (
            f"#{story['id']} — "
            f"{story['status']}\n"
        )

    await message.answer(
        text,
        parse_mode="HTML",
    )


# =========================================================
# НАЗАД
# =========================================================

@router.message(F.text == "⬅️ Назад")
async def back_handler(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await message.answer(
        "↩️ Главное меню",
        reply_markup=main_keyboard,
    )
