import os

from aiogram.types import (
    ReplyKeyboardMarkup,
    WebAppInfo,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# =========================================================
# MINI APP URL
# =========================================================

ADMIN_MINIAPP_URL = os.getenv(
    "ADMIN_MINIAPP_URL",
    "",
).strip()


# =========================================================
# USER MENU
# =========================================================

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📝 Поделиться историей"
            )
        ],
        [
            KeyboardButton(
                text="💡 Совет дня"
            ),
            KeyboardButton(
                text="📚 Полезные материалы"
            ),
        ],
        [
            KeyboardButton(
                text="🆘 Экстренная поддержка"
            )
        ],
        [
            KeyboardButton(
                text="📖 Смотреть истории"
            )
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# ADMIN USER MENU
# =========================================================

admin_user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📝 Поделиться историей"
            )
        ],
        [
            KeyboardButton(
                text="💡 Совет дня"
            ),
            KeyboardButton(
                text="📚 Полезные материалы"
            ),
        ],
        [
            KeyboardButton(
                text="🆘 Экстренная поддержка"
            )
        ],
        [
            KeyboardButton(
                text="📖 Смотреть истории"
            )
        ],

        *(
            [
                [
                    KeyboardButton(
                        text="🖥 Панель администратора",
                        web_app=WebAppInfo(
                            url=ADMIN_MINIAPP_URL
                        ),
                    )
                ]
            ]
            if ADMIN_MINIAPP_URL
            else []
        ),
    ],
    resize_keyboard=True,
)


# =========================================================
# LEGACY ADMIN MENU
#
# Оставляем в коде временно как резерв.
# В пользовательском меню эта кнопка больше
# не показывается.
# =========================================================

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="⏳ Модерация"
            ),
            KeyboardButton(
                text="📊 Статистика"
            ),
        ],
        [
            KeyboardButton(
                text="📈 Аналитика"
            ),
            KeyboardButton(
                text="💬 Диалоги"
            ),
        ],
        [
            KeyboardButton(
                text="🗓 Планировщик"
            ),
            KeyboardButton(
                text="📜 Журнал действий"
            ),
        ],
        [
            KeyboardButton(
                text="📁 Все истории"
            )
        ],
        [
            KeyboardButton(
                text="👥 Роли администраторов"
            )
        ],
        *(
            [
                [
                    KeyboardButton(
                        text="🖥 Mini App",
                        web_app=WebAppInfo(
                            url=ADMIN_MINIAPP_URL
                        ),
                    )
                ]
            ]
            if ADMIN_MINIAPP_URL
            else []
        ),
        [
            KeyboardButton(
                text="👤 Режим пользователя"
            )
        ],
        [
            KeyboardButton(
                text="⬅️ Назад"
            )
        ],
    ],
    resize_keyboard=True,
)


# =========================================================
# SUPPORT
# =========================================================

def support_method_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Продолжить в боте",
                    callback_data=(
                        "support_method:bot"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text=(
                        "📞 Пусть со мной "
                        "свяжется сотрудник"
                    ),
                    callback_data=(
                        "support_method:personal"
                    ),
                )
            ],
        ]
    )


def personal_contact_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=(
                        "📞 Связаться со мной лично"
                    ),
                    callback_data=(
                        "support_personal_request"
                    ),
                )
            ]
        ]
    )


def material_actions_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆘 Нужна поддержка",
                    callback_data=(
                        "material:support"
                    ),
                )
            ]
        ]
    )


# =========================================================
# MODERATION
# =========================================================

def moderation_keyboard(
    story_id: int,
    user_id: int,
    scheduled: bool = False,
):

    if scheduled:

        schedule_row = [
            InlineKeyboardButton(
                text="❌ Снять расписание",
                callback_data=(
                    f"schedule_cancel:{story_id}"
                ),
            )
        ]

    else:

        schedule_row = [
            InlineKeyboardButton(
                text="🗓 Запланировать",
                callback_data=(
                    f"schedule:{story_id}"
                ),
            )
        ]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить",
                    callback_data=(
                        f"edit:{story_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🔄 Повторить ИИ",
                    callback_data=(
                        f"ai_retry:{story_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👀 Предпросмотр",
                    callback_data=(
                        f"preview:{story_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="✅ Опубликовать",
                    callback_data=(
                        f"publish:{story_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=(
                        f"reject:{story_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🛡 Проверка ИИ",
                    callback_data=(
                        f"ai_moderate:{story_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 Написать пользователю",
                    callback_data=(
                        f"contact:{story_id}"
                    ),
                )
            ],
            schedule_row,
        ]
    )


# =========================================================
# REACTIONS
# =========================================================

def _reaction_buttons(
    story_id: int,
    counts: dict | None = None,
    selected: str | None = None,
):

    counts = counts or {
        "heart": 0,
        "understand": 0,
        "support": 0,
    }

    def label(
        key,
        emoji,
    ):

        mark = (
            " ✓"
            if selected == key
            else ""
        )

        return (
            f"{emoji} "
            f"{counts.get(key, 0)}"
            f"{mark}"
        )

    return [
        InlineKeyboardButton(
            text=label(
                "heart",
                "❤️",
            ),
            callback_data=(
                f"reaction:{story_id}:heart"
            ),
        ),
        InlineKeyboardButton(
            text=label(
                "understand",
                "💙",
            ),
            callback_data=(
                f"reaction:{story_id}:understand"
            ),
        ),
        InlineKeyboardButton(
            text=label(
                "support",
                "🤝",
            ),
            callback_data=(
                f"reaction:{story_id}:support"
            ),
        ),
    ]


def channel_story_keyboard(
    story_id: int,
    message_link: str | None = None,
    counts: dict | None = None,
    selected: str | None = None,
):

    buttons = [
        _reaction_buttons(
            story_id,
            counts,
            selected,
        )
    ]

    if message_link:

        buttons.append(
            [
                InlineKeyboardButton(
                    text="👀 Посмотреть",
                    url=message_link,
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⚠️ Пожаловаться",
                callback_data=(
                    f"complaint:{story_id}"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


def published_story_keyboard(
    message_link: str,
    story_id: int | None = None,
    counts: dict | None = None,
):

    rows = []

    if story_id is not None:

        rows.append(
            _reaction_buttons(
                story_id,
                counts,
            )
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="👀 Посмотреть",
                url=message_link,
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# =========================================================
# SUPPORT NEW MESSAGE
# =========================================================

def support_new_message_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Открыть",
                    callback_data=(
                        f"dialog_open:{dialog_id}"
                    ),
                )
            ]
        ]
    )


# =========================================================
# SCHEDULE
# =========================================================

def schedule_keyboard(
    story_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🕐 Выбрать время",
                    callback_data=(
                        f"schedule_custom:{story_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Отмена",
                    callback_data=(
                        f"schedule_cancel_ui:{story_id}"
                    ),
                )
            ],
        ]
    )


# =========================================================
# PERSONAL REQUEST
# =========================================================

def personal_request_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📞 Связаться",
                    callback_data=(
                        f"dialog_personal:{dialog_id}"
                    ),
                )
            ]
        ]
    )


# =========================================================
# SUPPORT DIALOG
# =========================================================

def support_dialog_keyboard(
    dialog_id: int,
):

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Назначить себе",
                    callback_data=(
                        f"dialog_assign:{dialog_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="⏳ Ждём пользователя",
                    callback_data=(
                        f"dialog_waiting:{dialog_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="✅ Решён",
                    callback_data=(
                        f"dialog_resolved:{dialog_id}"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📞 Личный контакт",
                    callback_data=(
                        f"dialog_personal:{dialog_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🚪 Выйти",
                    callback_data=(
                        f"dialog_exit:{dialog_id}"
                    ),
                ),
                InlineKeyboardButton(
                    text="🔒 Закрыть",
                    callback_data=(
                        f"dialog_close:{dialog_id}"
                    ),
                ),
            ],
        ]
    )
