from datetime import date
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
    moderation_keyboard,
    support_new_message_keyboard,
    personal_contact_keyboard,
    support_method_keyboard,
    materials_keyboard,
    material_actions_keyboard,
)


router = Router()


# =========================================================
# ПРОВЕРКА АДМИНИСТРАТОРА
# =========================================================

def is_admin(
    user_id: int,
) -> bool:

    return user_id in ADMIN_IDS


# =========================================================
# СОВЕТЫ ДНЯ
# =========================================================

DAILY_TIPS = [
    (
        "💡 <b>Совет дня</b>\n\n"
        "Не обязательно решить всю проблему сразу.\n\n"
        "Попробуйте определить только один небольшой "
        "шаг, который вы можете сделать сегодня.\n\n"
        "Иногда движение вперёд начинается именно "
        "с маленького действия."
    ),
    (
        "💡 <b>Совет дня</b>\n\n"
        "Если мысли постоянно возвращаются к одной "
        "и той же проблеме, попробуйте записать их "
        "на бумаге.\n\n"
        "Отделите то, что вы можете изменить, от того, "
        "на что прямо сейчас повлиять нельзя.\n\n"
        "Сосредоточьтесь на первой группе."
    ),
    (
        "💡 <b>Совет дня</b>\n\n"
        "Когда тревога становится сильной, верните "
        "внимание в настоящий момент.\n\n"
        "Посмотрите вокруг и назовите:\n"
        "5 вещей, которые видите;\n"
        "4 вещи, которых можете коснуться;\n"
        "3 звука, которые слышите.\n\n"
        "Это может помочь немного переключить внимание."
    ),
    (
        "💡 <b>Совет дня</b>\n\n"
        "Не требуйте от себя максимальной продуктивности "
        "в каждый момент жизни.\n\n"
        "Отдых — это не бездействие и не слабость.\n\n"
        "Иногда восстановление сил — самое полезное "
        "действие, которое можно сделать."
    ),
    (
        "💡 <b>Совет дня</b>\n\n"
        "Если вам тяжело, не обязательно справляться "
        "со всем в одиночку.\n\n"
        "Попробуйте написать человеку, которому доверяете, "
        "даже если пока не знаете, что именно сказать.\n\n"
        "Фраза «Мне сейчас тяжело, можешь просто "
        "побыть со мной?» — уже достаточная причина "
        "обратиться за поддержкой."
    ),
    (
        "💡 <b>Совет дня</b>\n\n"
        "Сравнение себя с другими часто показывает "
        "только внешнюю сторону их жизни.\n\n"
        "Вместо вопроса «Почему у меня не так?» "
        "попробуйте спросить себя:\n\n"
        "«Что я могу сделать сегодня, чтобы моя "
        "ситуация стала хотя бы немного лучше?»"
    ),
    (
        "💡 <b>Совет дня</b>\n\n"
        "Если эмоции зашкаливают, не принимайте важные "
        "решения в самый острый момент.\n\n"
        "Сначала дайте себе немного времени, воды, "
        "воздуха и пространства.\n\n"
        "Решение, принятое после того, как эмоции немного "
        "стихли, часто выглядит совсем иначе."
    ),
]


def get_daily_tip() -> str:

    day_number = date.today().toordinal()

    index = day_number % len(DAILY_TIPS)

    return DAILY_TIPS[index]


# =========================================================
# ПОЛЕЗНЫЕ МАТЕРИАЛЫ
# =========================================================

MATERIALS = {
    "anxiety": (
        "😟 <b>Тревога</b>\n\n"
        "Тревога часто заставляет мозг искать опасность "
        "даже тогда, когда прямо сейчас её нет.\n\n"
        "Попробуйте:\n"
        "• сделать несколько медленных вдохов и выдохов;\n"
        "• поставить ноги на пол и почувствовать опору;\n"
        "• назвать несколько предметов вокруг себя;\n"
        "• спросить себя: «Что происходит прямо сейчас, "
        "а не что может произойти потом?»\n\n"
        "Не нужно заставлять себя немедленно перестать "
        "тревожиться. Иногда достаточно немного снизить "
        "интенсивность переживания."
    ),

    "mood": (
        "😔 <b>Плохое настроение</b>\n\n"
        "Плохое настроение не всегда нужно немедленно "
        "исправлять.\n\n"
        "Иногда полезнее признать своё состояние и "
        "сделать что-то очень простое:\n"
        "• поесть;\n"
        "• выпить воды;\n"
        "• принять душ;\n"
        "• выйти ненадолго на улицу;\n"
        "• написать близкому человеку.\n\n"
        "Маленькие действия не решают всё сразу, "
        "но помогают вернуть немного контроля."
    ),

    "stress": (
        "😤 <b>Стресс</b>\n\n"
        "При сильном стрессе организм работает так, "
        "будто нужно срочно реагировать на угрозу.\n\n"
        "Попробуйте временно уменьшить количество "
        "задач до самого необходимого.\n\n"
        "Спросите себя:\n"
        "«Что действительно нужно сделать сегодня?»\n\n"
        "Остальное можно перенести."
    ),

    "thoughts": (
        "💭 <b>Навязчивые мысли</b>\n\n"
        "Наличие неприятной мысли не означает, что вы "
        "хотите её реализовать или что она обязательно "
        "что-то говорит о вас.\n\n"
        "Попробуйте воспринимать мысль как событие "
        "в сознании, а не как факт.\n\n"
        "Вместо «Это точно случится» попробуйте:\n"
        "«У меня появилась мысль, что это может случиться»."
    ),

    "relationships": (
        "🤝 <b>Отношения</b>\n\n"
        "В конфликте легко начать доказывать, кто прав.\n\n"
        "Иногда полезнее сначала объяснить своё состояние:\n"
        "«Мне было неприятно, когда произошло...»,\n"
        "вместо:\n"
        "«Ты всегда всё делаешь неправильно».\n\n"
        "Так разговор чаще остаётся диалогом, а не "
        "превращается в соревнование."
    ),

    "sleep": (
        "💤 <b>Сон</b>\n\n"
        "Если мысли не дают заснуть, не обязательно "
        "лежать и бороться с ними.\n\n"
        "Можно записать то, что беспокоит, и рядом "
        "написать: «Вернусь к этому завтра».\n\n"
        "Также постарайтесь сделать последние минуты "
        "перед сном спокойнее: меньше яркого света, "
        "новостей и активных разговоров."
    ),

    "selfesteem": (
        "💪 <b>Самооценка</b>\n\n"
        "Ваша ценность не определяется одной ошибкой, "
        "неудачей или мнением другого человека.\n\n"
        "Попробуйте вспомнить три вещи, которые у вас "
        "получились за последнее время.\n\n"
        "Даже если они кажутся совсем маленькими."
    ),

    "calm": (
        "🧘 <b>Как немного успокоиться сейчас</b>\n\n"
        "Попробуйте сделать следующее:\n\n"
        "1. Поставьте ноги на пол.\n"
        "2. Медленно вдохните.\n"
        "3. Сделайте более длинный выдох.\n"
        "4. Посмотрите на окружающее пространство.\n"
        "5. Назовите про себя несколько предметов, "
        "которые видите.\n\n"
        "Не требуйте от себя полного спокойствия. "
        "Цель — сделать состояние хотя бы немного легче."
    ),
}


# =========================================================
# START
# =========================================================

@router.message(Command("start"))
async def start_command(
    message: Message,
):

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

    if is_admin(
        message.from_user.id
    ):

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
async def help_command(
    message: Message,
):

    await message.answer(
        "💡 Как пользоваться ботом:\n\n"
        "1️⃣ Нажмите «📝 Поделиться историей».\n"
        "2️⃣ Напишите свою историю.\n"
        "3️⃣ Бот подготовит материал для публикации.\n"
        "4️⃣ Администратор проверит материал.\n\n"
        "💡 В разделе «Совет дня» можно найти "
        "небольшой практический совет.\n\n"
        "📚 В «Полезных материалах» собраны "
        "короткие материалы по разным ситуациям.\n\n"
        "Если вам нужна срочная поддержка, "
        "используйте кнопку «🆘 Экстренная поддержка».\n\n"
        "Спасибо за доверие 💙"
    )


# =========================================================
# СОВЕТ ДНЯ
# =========================================================

@router.message(
    F.text == "💡 Совет дня"
)
async def daily_tip(
    message: Message,
):

    await message.answer(
        get_daily_tip(),
        parse_mode="HTML",
    )


# =========================================================
# ПОЛЕЗНЫЕ МАТЕРИАЛЫ
# =========================================================

@router.message(
    F.text == "📚 Полезные материалы"
)
async def useful_materials(
    message: Message,
):

    await message.answer(
        "📚 <b>Полезные материалы</b>\n\n"
        "Выберите тему, которая сейчас вам ближе.\n\n"
        "Материалы не заменяют помощь специалиста, "
        "но могут помочь лучше понять своё состояние "
        "и попробовать сделать первый шаг.",
        parse_mode="HTML",
        reply_markup=materials_keyboard(),
    )


# =========================================================
# ЭКСТРЕННАЯ ПОДДЕРЖКА
# =========================================================

@router.message(
    F.text == "🆘 Экстренная поддержка"
)
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
        "💬 <b>В боте</b> — вы будете "
        "переписываться с модератором здесь.\n\n"
        "📞 <b>Лично</b> — мы передадим сотруднику "
        "запрос, чтобы он смог связаться с вами напрямую.\n\n"
        "Диалог в боте при этом не закрывается.",
        parse_mode="HTML",
        reply_markup=support_method_keyboard(),
    )


# =========================================================
# ПЕРВОЕ СООБЩЕНИЕ ПОДДЕРЖКИ
# =========================================================

@router.message(
    StoryState.waiting_for_support_message
)
async def receive_support_message(
    message: Message,
    state: FSMContext,
):

    if not message.text:

        await message.answer(
            "❗ Пожалуйста, отправьте сообщение "
            "обычным текстом."
        )

        return

    support_text = message.text.strip()

    if len(support_text) < 2:

        await message.answer(
            "✏️ Напишите немного подробнее, "
            "чтобы модератор смог вам ответить."
        )

        return

    user_id = message.from_user.id

    dialog = get_open_dialog_by_user(
        user_id
    )

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


# =========================================================
# СООБЩЕНИЯ В АКТИВНЫЙ ДИАЛОГ
# =========================================================

@router.message(
    F.chat.type == "private",
    F.text,
)
async def active_support_message(
    message: Message,
    state: FSMContext,
):

    if is_admin(
        message.from_user.id
    ):
        return

    if message.text in [
        "📝 Поделиться историей",
        "💡 Совет дня",
        "📚 Полезные материалы",
        "🆘 Экстренная поддержка",
        "⬅️ Назад",
    ]:
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
        dialog_id=dialog_id,
        sender_id=message.from_user.id,
        sender_type="user",
        text=text,
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


# =========================================================
# УВЕДОМИТЬ МОДЕРАТОРОВ
# =========================================================

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


# =========================================================
# ПОДЕЛИТЬСЯ ИСТОРИЕЙ
# =========================================================

@router.message(
    F.text == "📝 Поделиться историей"
)
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

@router.message(
    StoryState.waiting_for_story
)
async def receive_story(
    message: Message,
    state: FSMContext,
):

    if not message.text:

        await message.answer(
            "❗ Отправьте историю обычным "
            "текстовым сообщением."
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

            print(
                f"ADMIN SEND ERROR: {error}"
            )

    await message.answer(
        "💙 Спасибо, что поделились.\n\n"
        "Ваша история отправлена на рассмотрение."
    )

    await state.clear()


# =========================================================
# АДМИН-ПАНЕЛЬ
# =========================================================

@router.message(
    F.text == "👨‍💼 Админ-панель"
)
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
        f"⏳ На модерации: "
        f"{stats['waiting']}\n"
        f"📚 Всего историй: "
        f"{stats['total']}\n"
        f"✅ Опубликовано: "
        f"{stats['published']}\n"
        f"❌ Отклонено: "
        f"{stats['rejected']}\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ДИАЛОГИ
# =========================================================

@router.message(
    F.text == "💬 Диалоги"
)
async def dialogs_menu(
    message: Message,
):

    if not is_admin(
        message.from_user.id
    ):
        return

    dialogs = get_open_dialogs()

    if not dialogs:

        await message.answer(
            "💬 Открытых диалогов сейчас нет.",
            reply_markup=admin_keyboard,
        )

        return

    await message.answer(
        f"💬 <b>Открытые диалоги: "
        f"{len(dialogs)}</b>",
        parse_mode="HTML",
    )

    for dialog in dialogs[:50]:

        last_message = (
            dialog["last_message"] or ""
        )

        if len(last_message) > 100:

            last_message = (
                last_message[:100] + "..."
            )

        unread = (
            dialog["unread_admin"] or 0
        )

        if unread:

            unread_text = (
                f"🔴 Новых сообщений: {unread}"
            )

        else:

            unread_text = (
                "🟢 Нет новых сообщений"
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
                        callback_data=(
                            f"dialog_open:"
                            f"{dialog['id']}"
                        ),
                    )
                ]
            ]
        )

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )


# =========================================================
# МОДЕРАЦИЯ
# =========================================================

@router.message(
    F.text == "⏳ Модерация"
)
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
        f"⏳ <b>На модерации: "
        f"{len(stories)}</b>",
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


# =========================================================
# СТАТИСТИКА
# =========================================================

@router.message(
    F.text == "📊 Статистика"
)
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
        f"📚 Всего историй: "
        f"{stats['total']}\n\n"
        f"⏳ На модерации: "
        f"{stats['waiting']}\n"
        f"✅ Опубликовано: "
        f"{stats['published']}\n"
        f"❌ Отклонено: "
        f"{stats['rejected']}",
        parse_mode="HTML",
        reply_markup=admin_keyboard,
    )


# =========================================================
# ВСЕ ИСТОРИИ
# =========================================================

@router.message(
    F.text == "📁 Все истории"
)
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

    text = (
        "📁 <b>Все истории</b>\n\n"
    )

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

        text += (
            f"{icon} #{story['id']} — "
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

@router.message(
    F.text == "⬅️ Назад"
)
async def back(
    message: Message,
    state: FSMContext,
):

    await state.clear()

    if is_admin(
        message.from_user.id
    ):

        await message.answer(
            "↩️ Админ-панель",
            reply_markup=admin_keyboard,
        )

    else:

        await message.answer(
            "↩️ Главное меню",
            reply_markup=main_keyboard,
        )
