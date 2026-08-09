from html import escape

from aiogram import Router, F
from aiogram.types import (
Message,
InlineKeyboardMarkup,
InlineKeyboardButton,
)
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
get_open_dialog_by_user,
create_support_dialog,
add_support_message,
get_open_dialogs,
)

from ai import analyze_story
from post_generator import create_post

from keyboards import (
main_keyboard,
admin_keyboard,
admin_user_keyboard,
moderation_keyboard,
support_new_message_keyboard,
support_method_keyboard,
personal_contact_keyboard,
material_actions_keyboard,
)

router = Router()

=========================================================

МАТЕРИАЛЫ

=========================================================

MATERIALS = {
"anxiety": (
"🧠 <b>Если тревога не отпускает</b>\n\n"
"Попробуйте остановиться на несколько минут и "
"сосредоточиться на том, что происходит прямо сейчас.\n\n"
"Можно сделать несколько медленных вдохов и выдохов, "
"убрать лишние раздражители и дать себе немного времени."
),
"stress": (
"🌿 <b>Если вы сильно устали</b>\n\n"
"Иногда лучший первый шаг — не пытаться решить всё сразу.\n\n"
"Выберите одну небольшую задачу, которую можно выполнить "
"прямо сейчас, а остальное временно отложите."
),
"relationships": (
"💙 <b>Если сложности связаны с отношениями</b>\n\n"
"Попробуйте отделить факты от предположений и эмоций.\n\n"
"Спокойный разговор часто начинается с описания собственных "
"чувств, а не с обвинений другого человека."
),
}

=========================================================

ПРОВЕРКА АДМИНИСТРАТОРА

=========================================================

def is_admin(user_id: int) -> bool:
return user_id in ADMIN_IDS

=========================================================

START

=========================================================

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
        "Сейчас включён <b>режим пользователя</b>.\n"
        "Вы можете полноценно тестировать бота "
        "так же, как обычный пользователь.\n\n"
        "Для управления проектом нажмите "
        "«👨‍💼 Админ-панель».",
        parse_mode="HTML",
        reply_markup=admin_user_keyboard,
    )
    return

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

=========================================================

HELP

=========================================================

@router.message(Command("help"))
async def help_command(
message: Message,
state: FSMContext,
):
await state.clear()

await message.answer(
    "💡 <b>Как пользоваться ботом</b>\n\n"
    "📝 <b>Поделиться историей</b> — отправить свою историю "
    "на анонимное рассмотрение.\n\n"
    "💡 <b>Совет дня</b> — получить небольшой совет.\n\n"
    "📚 <b>Полезные материалы</b> — открыть подборку материалов.\n\n"
    "🆘 <b>Экстренная поддержка</b> — связаться с модератором.\n\n"
    "Спасибо за доверие 💙",
    parse_mode="HTML",
    reply_markup=(
        admin_user_keyboard
        if is_admin(message.from_user.id)
        else main_keyboard
    ),
)

=========================================================

АДМИН-ПАНЕЛЬ

=========================================================

@router.message(F.text == "👨‍💼 Админ-панель")
async def switch_to_admin_mode(
message: Message,
state: FSMContext,
):
if not is_admin(message.from_user.id):
await message.answer("⛔ У вас нет доступа.")
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

=========================================================

РЕЖИМ ПОЛЬЗОВАТЕЛЯ

=========================================================

@router.message(F.text == "👤 Режим пользователя")
async def switch_to_user_mode(
message: Message,
state: FSMContext,
):
if not is_admin(message.from_user.id):
return

await state.clear()

await message.answer(
    "👤 <b>Режим пользователя</b>\n\n"
    "Теперь вы можете тестировать бота "
    "как обычный пользователь.",
    parse_mode="HTML",
    reply_markup=admin_user_keyboard,
)

=========================================================

СОВЕТ ДНЯ

=========================================================

@router.message(F.text == "💡 Совет дня")
async def daily_advice(
message: Message,
state: FSMContext,
):
await state.clear()

await message.answer(
    "💡 <b>Совет дня</b>\n\n"
    "Не обязательно решать всю проблему сегодня.\n\n"
    "Иногда достаточно сделать один небольшой шаг "
    "в сторону того, что для вас важно.\n\n"
    "Даже маленькое движение вперёд — это движение 💙",
    parse_mode="HTML",
    reply_markup=(
        admin_user_keyboard
        if is_admin(message.from_user.id)
        else main_keyboard
    ),
)

=========================================================

ПОЛЕЗНЫЕ МАТЕРИАЛЫ

=========================================================

@router.message(F.text == "📚 Полезные материалы")
async def useful_materials(
message: Message,
state: FSMContext,
):
await state.clear()

keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🧠 Тревога",
                callback_data="material:anxiety",
            ),
            InlineKeyboardButton(
                text="🌿 Стресс",
                callback_data="material:stress",
            ),
        ],
        [
            InlineKeyboardButton(
                text="💙 Отношения",
                callback_data="material:relationships",
            )
        ],
        [
            InlineKeyboardButton(
                text="🆘 Нужна поддержка",
                callback_data="material:support",
            )
        ],
    ]
)

await message.answer(
    "📚 <b>Полезные материалы</b>\n\n"
    "Выберите тему:",
    parse_mode="HTML",
    reply_markup=keyboard,
)

=========================================================

ЭКСТРЕННАЯ ПОДДЕРЖКА

=========================================================

@router.message(F.text == "🆘 Экстренная поддержка")
async def emergency_support(
message: Message,
state: FSMContext,
):
await state.clear()

await state.set_state(
    StoryState.waiting_for_support_method
)

await message.answer(
    "🆘 <b>Экстренная поддержка</b>\n\n"
    "Выберите, как вы хотите продолжить общение:\n\n"
    "💬 <b>В боте</b> — переписка с модератором здесь.\n\n"
    "📞 <b>Лично</b> — сотрудник сможет связаться "
    "с вами напрямую.\n\n"
    "Диалог в боте при этом не закрывается.",
    parse_mode="HTML",
    reply_markup=support_method_keyboard(),
)

=========================================================

ПОДЕЛИТЬСЯ ИСТОРИЕЙ

=========================================================

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
    "🔒 История будет обработана анонимно.\n\n"
    "Чтобы отменить отправку, нажмите «⬅️ Назад»."
)

=========================================================

НАЗАД

=========================================================

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

=========================================================

ПОЛУЧЕНИЕ ИСТОРИИ

=========================================================

@router.message(StoryState.waiting_for_story)
async def receive_story(
message: Message,
state: FSMContext,
):
if not message.text:
await message.answer(
"❗ Отправьте историю обычным текстовым сообщением."
)
return

story = message.text.strip()

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

try:
    ai_result = await analyze_story(story)
except Exception as error:
    print(f"AI ERROR: {error}")
    ai_result = "Не удалось выполнить анализ."

update_ai_result(
    story_id,
    ai_result,
)

try:
    post_text = await create_post(story)
except Exception as error:
    print(f"POST ERROR: {error}")
    post_text = "Не удалось создать пост."

update_post(
    story_id,
    post_text,
)

moderation_text = (
    f"📥 <b>Новая история #{story_id}</b>\n\n"
    f"👤 <b>User ID:</b> "
    f"<code>{message.from_user.id}</code>\n\n"
    "🔒 История отправлена анонимно.\n\n"
    "💭 <b>Текст:</b>\n\n"
    f"{escape(story)}\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "🤖 <b>Анализ ИИ:</b>\n\n"
    f"{escape(ai_result)}\n\n"
    "━━━━━━━━━━━━━━\n\n"
    "📌 <b>Готовый пост:</b>\n\n"
    f"{escape(post_text)}"
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
    "Ваша история отправлена на рассмотрение.",
    reply_markup=(
        admin_user_keyboard
        if is_admin(message.from_user.id)
        else main_keyboard
    ),
)

=========================================================

ПЕРВОЕ СООБЩЕНИЕ ПОДДЕРЖКИ

=========================================================

@router.message(StoryState.waiting_for_support_message)
async def receive_support_message(
message: Message,
state: FSMContext,
):
if not message.text:
await message.answer(
"❗ Пожалуйста, отправьте сообщение обычным текстом."
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
        dialog_id=dialog_id,
        sender_id=user_id,
        sender_type="user",
        text=support_text,
    )
else:
    dialog_id = create_support_dialog(
        user_id=user_id,
        first_message=support_text,
    )

await notify_admins_about_message(
    message,
    dialog_id,
    support_text,
)

await state.clear()

await message.answer(
    "💙 Сообщение передано модератору.\n\n"
    "Вы можете продолжать писать сюда.\n"
    "Диалог останется открытым.",
    reply_markup=personal_contact_keyboard(),
)

=========================================================

УВЕДОМЛЕНИЕ АДМИНИСТРАТОРОВ

=========================================================

async def notify_admins_about_message(
message: Message,
dialog_id: int,
text: str,
):
admin_text = (
"💬 <b>Новое сообщение в диалоге</b>\n\n"
f"Диалог #{dialog_id}\n"
f"👤 User ID: "
f"<code>{message.from_user.id}</code>\n\n"
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
        print(
            f"DIALOG MESSAGE ADMIN ERROR: {error}"
        )

=========================================================

АДМИН: МОДЕРАЦИЯ

=========================================================

@router.message(F.text == "⏳ Модерация")
async def moderation(
message: Message,
):
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
        f"👤 User ID: "
        f"<code>{story['user_id']}</code>\n\n"
        f"{escape(story['text'])}",
        parse_mode="HTML",
        reply_markup=moderation_keyboard(
            story["id"],
            story["user_id"],
        ),
    )

=========================================================

АДМИН: ДИАЛОГИ

=========================================================

@router.message(F.text == "💬 Диалоги")
async def dialogs_menu(
message: Message,
):
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

    unread_text = (
        f"🔴 Новых сообщений: {unread}"
        if unread
        else "🟢 Нет новых сообщений"
    )

    text = (
        f"💬 <b>Диалог #{dialog['id']}</b>\n\n"
        f"👤 User ID: "
        f"<code>{dialog['user_id']}</code>\n\n"
        f"{unread_text}\n\n"
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

=========================================================

АДМИН: СТАТИСТИКА

=========================================================

@router.message(F.text == "📊 Статистика")
async def statistics(
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
    reply_markup=admin_keyboard,
)

=========================================================

АДМИН: ВСЕ ИСТОРИИ

=========================================================

@router.message(F.text == "📁 Все истории")
async def all_stories(
message: Message,
):
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
    status = story["status"]

    if status == "waiting":
        icon = "⏳"
    elif status == "published":
        icon = "✅"
    elif status == "rejected":
        icon = "❌"
    else:
        icon = "📌"

    text += f"{icon} #{story['id']} — {status}\n"

await message.answer(
    text,
    parse_mode="HTML",
    reply_markup=admin_keyboard,
)

=========================================================

НЕОБЫЧНОЕ СООБЩЕНИЕ

=========================================================

@router.message(F.chat.type == "private", F.text)
async def unknown_message(
message: Message,
state: FSMContext,
):
current_state = await state.get_state()

# Если пользователь уже находится в FSM,
# этот handler не должен мешать другим обработчикам.
if current_state:
    return

if is_admin(message.from_user.id):
    await message.answer(
        "ℹ️ Используйте кнопки меню.",
        reply_markup=admin_user_keyboard,
    )
else:
    await message.answer(
        "ℹ️ Используйте кнопки меню ниже.",
        reply_markup=main_keyboard,
    )
