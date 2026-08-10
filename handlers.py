from html import escape
import random

from aiogram import Router, F
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, StateFilter

from states import StoryState
from config import ADMIN_IDS

from database import (
    create_story,
    update_ai_result,
    update_post,
    get_waiting_stories,
    get_all_stories,
    get_stats,
    get_open_dialog_by_user,
    create_support_dialog,
    add_support_message,
    get_open_dialogs,
    set_dialog_status,
)

from ai import analyze_story
from post_generator import create_post

from keyboards import (
    main_keyboard,
    admin_keyboard,
    admin_user_keyboard,
    moderation_keyboard,
    support_new_message_keyboard,
    personal_contact_keyboard,
    material_actions_keyboard,
)


router = Router()


MATERIALS = {
    "anxiety": (
        "🧠 <b>Если тревога не отпускает</b>\n\n"
        "Тревога может ощущаться как постоянное напряжение "
        "или ощущение, что вот-вот произойдёт что-то плохое.\n\n"
        "Попробуйте остановиться на несколько минут и обратить "
        "внимание на дыхание.\n\n"
        "Сделайте несколько медленных вдохов и выдохов. "
        "Назовите про себя 5 вещей, которые видите, "
        "4 вещи, которых можете коснуться, "
        "3 звука, которые слышите."
    ),
    "stress": (
        "🌿 <b>Как немного снизить стресс</b>\n\n"
        "Попробуйте сделать небольшой перерыв, "
        "выйти на свежий воздух, выпить воды "
        "или убрать хотя бы одну небольшую задачу.\n\n"
        "Иногда пауза помогает двигаться дальше."
    ),
    "sleep": (
        "🌙 <b>Если трудно уснуть</b>\n\n"
        "Перед сном попробуйте уменьшить количество "
        "яркого света и отложить телефон.\n\n"
        "Можно сделать несколько спокойных вдохов и выдохов."
    ),
    "self_esteem": (
        "💙 <b>Когда кажется, что вы недостаточно хороши</b>\n\n"
        "Попробуйте вспомнить хотя бы три вещи, "
        "которые у вас сегодня получились.\n\n"
        "Ваша ценность не определяется одной ошибкой."
    ),
}


def materials_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="😟 Тревога",
                    callback_data="material:anxiety",
                ),
                InlineKeyboardButton(
                    text="😣 Стресс",
                    callback_data="material:stress",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌙 Сон",
                    callback_data="material:sleep",
                ),
                InlineKeyboardButton(
                    text="💙 Самооценка",
                    callback_data="material:self_esteem",
                ),
            ],
        ]
    )


DAILY_TIPS = [
    "Не обязательно решать всю проблему сегодня. Иногда достаточно сделать один небольшой шаг.",
    "Если мысли постоянно возвращаются к одной проблеме, попробуйте записать их.",
    "Не требуйте от себя максимальной продуктивности каждый день.",
    "Если ситуация кажется огромной, разделите её на самое маленькое действие.",
    "Просить о помощи — нормально.",
]


def daily_tip_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆘 Нужна поддержка",
                    callback_data="material:support",
                )
            ]
        ]
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("start"))
async def start_command(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if is_admin(message.from_user.id):
        await message.answer(
            "👋 Добро пожаловать в «Проблем нет»\n\n"
            "👨‍💼 Вы вошли как администратор.\n\n"
            "Сейчас включён режим пользователя.",
            parse_mode="HTML",
            reply_markup=admin_user_keyboard,
        )
        return

    await message.answer(
        "👋 Добро пожаловать в «Проблем нет»\n\n"
        "Это пространство, где можно поделиться тем, "
        "что тревожит или беспокоит.\n\n"
        "💙 Здесь нет осуждения.\n\n"
        "📝 Нажмите «Поделиться историей».\n\n"
        "Помните: проблем нет.",
        reply_markup=main_keyboard,
    )


@router.message(F.text == "💡 Совет дня")
async def daily_tip(message: Message):
    await message.answer(
        "💡 <b>Совет дня</b>\n\n"
        + random.choice(DAILY_TIPS),
        parse_mode="HTML",
        reply_markup=daily_tip_keyboard(),
    )


@router.message(F.text == "📚 Полезные материалы")
async def useful_materials(message: Message):
    await message.answer(
        "📚 <b>Полезные материалы</b>\n\n"
        "Выберите тему:",
        parse_mode="HTML",
        reply_markup=materials_keyboard(),
    )


@router.message(F.text == "👨‍💼 Админ-панель")
async def switch_to_admin_mode(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

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


@router.message(F.text == "👤 Режим пользователя")
async def switch_to_user_mode(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message.from_user.id):
        return

    await state.clear()

    await message.answer(
        "👤 <b>Режим пользователя</b>",
        parse_mode="HTML",
        reply_markup=admin_user_keyboard,
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await message.answer(
        "💡 <b>Как пользоваться ботом:</b>\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал.\n"
        "4️⃣ Администратор проверит его.\n\n"
        "Если нужна поддержка — используйте "
        "«🆘 Экстренная поддержка».",
        parse_mode="HTML",
    )


@router.message(F.text == "🆘 Экстренная поддержка")
async def emergency_support(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await state.set_state(
        StoryState.waiting_for_support_method
    )

    from keyboards import support_method_keyboard

    await message.answer(
        "🆘 <b>Экстренная поддержка</b>\n\n"
        "Выберите способ общения:",
        parse_mode="HTML",
        reply_markup=support_method_keyboard(),
    )


@router.message(StoryState.waiting_for_support_message)
async def receive_support_message(
    message: Message,
    state: FSMContext,
):
    if not message.text:
        await message.answer(
            "❗ Отправьте текстовое сообщение."
        )
        return

    support_text = message.text.strip()

    if len(support_text) < 2:
        await message.answer(
            "✏️ Напишите немного подробнее."
        )
        return

    user_id = message.from_user.id

    dialog = get_open_dialog_by_user(user_id)

    if dialog:
        dialog_id = dialog["id"]

        add_support_message(
            dialog_id,
            user_id,
            "user",
            support_text,
        )
        set_dialog_status(
            dialog_id,
            "in_progress",
        )
    else:
        dialog_id = create_support_dialog(
            user_id,
            support_text,
        )

    await notify_admins_about_message(
        message,
        dialog_id,
        support_text,
    )

    await state.clear()

    await message.answer(
        "💙 Сообщение передано модератору.\n\n"
        "Диалог остаётся открытым.",
        reply_markup=personal_contact_keyboard(),
    )


async def notify_admins_about_message(
    message: Message,
    dialog_id: int,
    text: str,
):
    admin_text = (
        "💬 <b>Новое сообщение в диалоге</b>\n\n"
        f"Диалог #{dialog_id}\n"
        f"👤 User ID: <code>{message.from_user.id}</code>\n\n"
        f"{escape(text)}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                admin_text,
                reply_markup=support_new_message_keyboard(
                    dialog_id
                ),
                parse_mode="HTML",
            )
        except Exception as error:
            print(f"DIALOG ADMIN ERROR: {error}")


@router.message(F.text == "📝 Поделиться историей")
async def start_story(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    await state.set_state(
        StoryState.waiting_for_story
    )

    await message.answer(
        "💙 Расскажите свою историю.\n\n"
        "Можно написать всё, что вас беспокоит.\n\n"
        "🔒 История будет обработана анонимно."
    )


@router.message(StoryState.waiting_for_story)
async def receive_story(
    message: Message,
    state: FSMContext,
):
    if not message.text:
        await message.answer(
            "❗ Отправьте историю обычным текстом."
        )
        return

    story = message.text.strip()

    if len(story) < 10:
        await message.answer(
            "✏️ История слишком короткая."
        )
        return

    story_id = create_story(
        message.from_user.id,
        story,
    )

    await message.answer(
        "🤖 Анализирую вашу историю..."
    )

    try:
        ai_result = await analyze_story(story)
    except Exception as error:
        print(f"AI ERROR: {error}")
        ai_result = (
            "⚠️ Автоматический анализ временно недоступен. "
            "История сохранена, администратор может обработать её вручную."
        )

    update_ai_result(
        story_id,
        ai_result,
    )

    try:
        post_text = await create_post(story)
    except Exception as error:
        print(f"POST ERROR: {error}")
        post_text = ""

    update_post(
        story_id,
        post_text,
    )

    moderation_text = (
        f"📥 <b>Новая история #{story_id}</b>\n\n"
        f"👤 User ID: <code>{message.from_user.id}</code>\n\n"
        f"💭 <b>Текст:</b>\n\n"
        f"{escape(story)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"🤖 <b>Анализ ИИ:</b>\n\n"
        f"{escape(ai_result)}\n\n"
        "━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Готовый пост:</b>\n\n"
        f"{escape(post_text) if post_text else '⚠️ Пост не сгенерирован. Нажмите «✏️ Изменить», чтобы подготовить текст вручную.'}"
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
            print(f"ADMIN SEND ERROR: {error}")

    await state.clear()

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    if is_admin(message.from_user.id):
        await message.answer(
            "👤 Вы остались в режиме пользователя.",
            reply_markup=admin_user_keyboard,
        )


@router.message(
    StateFilter(None),
    F.chat.type == "private",
    F.text,
)
async def active_support_message(
    message: Message,
    state: FSMContext,
):
    if is_admin(message.from_user.id):
        return

    if message.text in {
        "📝 Поделиться историей",
        "💡 Совет дня",
        "📚 Полезные материалы",
        "🆘 Экстренная поддержка",
        "⬅️ Назад",
        "👨‍💼 Админ-панель",
        "👤 Режим пользователя",
    }:
        return

    dialog = get_open_dialog_by_user(
        message.from_user.id
    )

    if not dialog:
        return

    text = message.text.strip()

    if not text:
        return

    dialog_id = dialog["id"]

    add_support_message(
        dialog_id,
        message.from_user.id,
        "user",
        text,
    )
    set_dialog_status(
        dialog_id,
        "in_progress",
    )

    await notify_admins_about_message(
        message,
        dialog_id,
        text,
    )

    await message.answer(
        "💙 Сообщение передано модератору.",
        reply_markup=personal_contact_keyboard(),
    )


@router.message(F.text == "💬 Диалоги")
async def dialogs_menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    dialogs = get_open_dialogs()

    if not dialogs:
        await message.answer(
            "💬 Открытых диалогов сейчас нет.",
            reply_markup=admin_keyboard,
        )
        return

    await message.answer(
        f"💬 <b>Открытые диалоги: {len(dialogs)}</b>",
        parse_mode="HTML",
    )

    for dialog in dialogs[:50]:
        last_message = dialog["last_message"] or ""

        if len(last_message) > 100:
            last_message = last_message[:100] + "..."

        unread = dialog["unread_admin"] or 0

        text = (
            f"💬 <b>Диалог #{dialog['id']}</b>\n\n"
            f"👤 User ID: <code>{dialog['user_id']}</code>\n\n"
            f"{'🔴 Новых сообщений: ' + str(unread) if unread else '🟢 Нет новых сообщений'}\n\n"
            f"Последнее сообщение:\n"
            f"{escape(last_message)}"
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💬 Открыть",
                        callback_data=f"dialog_open:{dialog['id']}",
                    )
                ]
            ]
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


@router.message(F.text == "⏳ Модерация")
async def moderation(message: Message):
    if not is_admin(message.from_user.id):
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
            f"👤 User ID: <code>{story['user_id']}</code>\n\n"
            f"{escape(story['text'])}",
            parse_mode="HTML",
            reply_markup=moderation_keyboard(
                story["id"],
                story["user_id"],
            ),
        )


@router.message(F.text == "📊 Статистика")
async def statistics(message: Message):
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
        reply_markup=admin_keyboard,
    )


@router.message(F.text == "📁 Все истории")
async def all_stories(message: Message):
    if not is_admin(message.from_user.id):
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
        icons = {
            "waiting": "⏳",
            "published": "✅",
            "rejected": "❌",
        }

        icon = icons.get(
            story["status"],
            "📌",
        )

        text += (
            f"{icon} #{story['id']} — "
            f"{story['status']}\n"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


@router.message(F.text == "⬅️ Назад")
async def back(
    message: Message,
    state: FSMContext,
):
    await state.clear()

    if is_admin(message.from_user.id):
        await message.answer(
            "👤 Режим пользователя",
            reply_markup=admin_user_keyboard,
        )
    else:
        await message.answer(
            "↩️ Главное меню",
            reply_markup=main_keyboard,
        )
