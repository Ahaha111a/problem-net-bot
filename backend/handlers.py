from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS, CHANNEL_ID
from database import (
    create_story, update_ai_result, update_post, get_waiting_stories,
    get_all_stories, get_stats, register_user, create_support_dialog,
    get_open_dialog_by_user, add_support_message, get_story_reaction_counts,
)
from ai import analyze_story
from post_generator import create_post
from keyboards import main_keyboard, admin_keyboard, moderation_keyboard, support_keyboard

router = Router()

class StoryState(StatesGroup):
    waiting_for_story = State()
    support_waiting = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(F.text == "/help")
async def help_handler(message: Message):
    await message.answer("ℹ️ Помощь\n\n📝 Поделиться историей — отправить историю анонимно.\n📖 Смотреть истории — открыть канал.\n🆘 Экстренная поддержка — связаться с сотрудником.")


@router.message(F.text == "📝 Поделиться историей")
async def share_story(message: Message, state: FSMContext):
    register_user(message.from_user.id)
    await state.set_state(StoryState.waiting_for_story)
    await message.answer("💙 Расскажите свою историю. Можно написать всё, что вас беспокоит.")


@router.message(StoryState.waiting_for_story)
async def receive_story(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 10:
        await message.answer("✏️ История слишком короткая. Напишите немного подробнее.")
        return
    story_id = create_story(message.from_user.id, text)
    await message.answer("⏳ Спасибо! История сохранена и отправлена на обработку.", reply_markup=main_keyboard())
    try:
        ai_result = await analyze_story(text)
        update_ai_result(story_id, ai_result)
    except Exception as exc:
        update_ai_result(story_id, f"⚠️ Автоматический анализ временно недоступен. История сохранена. Ошибка: {exc}")
    try:
        post = await create_post(text)
        update_post(story_id, post)
    except Exception as exc:
        update_post(story_id, text)
    await state.clear()


@router.message(F.text == "📖 Смотреть истории")
async def stories_link(message: Message):
    if str(CHANNEL_ID).startswith("-100"):
        await message.answer("📖 Истории публикуются в нашем канале. Откройте канал из описания проекта.")
    else:
        await message.answer("📖 Откройте наш Telegram-канал.")


@router.message(F.text == "💡 Совет дня")
async def tip(message: Message):
    await message.answer("💡 Не пытайтесь решить всё сразу. Выберите один небольшой шаг, который можно сделать сегодня.")


@router.message(F.text == "📚 Полезные материалы")
async def materials(message: Message):
    await message.answer("📚 Здесь будут материалы о тревоге, стрессе, самооценке, отношениях и эмоциональном состоянии.")


@router.message(F.text == "❤️ Поддержка")
async def support(message: Message):
    await message.answer("❤️ Ты не обязан справляться со всем один. Если хочется поговорить — воспользуйся экстренной поддержкой.")


@router.message(F.text == "🆘 Экстренная поддержка")
async def emergency_support(message: Message, state: FSMContext):
    await state.set_state(StoryState.support_waiting)
    await message.answer("🆘 Опишите, что происходит. Сообщение увидит сотрудник поддержки.")


@router.message(StoryState.support_waiting)
async def support_message(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        return
    dialog = get_open_dialog_by_user(message.from_user.id)
    if dialog:
        add_support_message(dialog["id"], message.from_user.id, "user", text)
    else:
        create_support_dialog(message.from_user.id, text)
    await state.clear()
    await message.answer("💙 Сообщение передано сотруднику. Мы постараемся ответить как можно быстрее.", reply_markup=main_keyboard())


@router.message(F.text == "👨‍💼 Админ-панель")
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🛡 <b>Панель сотрудников</b>", reply_markup=admin_keyboard())


@router.message(F.text == "📊 Статистика")
async def stats(message: Message):
    if not is_admin(message.from_user.id): return
    s = get_stats()
    await message.answer(f"📊 <b>Статистика</b>\n\nВсего историй: {s['total']}\nНа модерации: {s['waiting']}\nОпубликовано: {s['published']}\nОтклонено: {s['rejected']}")


@router.message(F.text == "⏳ Модерация")
async def moderation(message: Message):
    if not is_admin(message.from_user.id): return
    stories = get_waiting_stories()
    if not stories:
        await message.answer("🟢 Историй на модерации нет.")
        return
    for story in stories[:20]:
        await message.answer(f"📥 <b>История #{story['id']}</b>\n\n{story['text']}", reply_markup=moderation_keyboard(story['id']))


@router.message(F.text == "📁 Все истории")
async def all_stories(message: Message):
    if not is_admin(message.from_user.id): return
    rows = get_all_stories()[:20]
    if not rows:
        await message.answer("📁 Историй пока нет."); return
    await message.answer("📁 <b>Последние истории</b>\n\n" + "\n".join(f"#{r['id']} — {r['status']}" for r in rows))


@router.message(F.text == "⬅️ Назад")
async def back(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("↩️ Главное меню", reply_markup=main_keyboard())
