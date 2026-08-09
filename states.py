from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):
    # Истории
    waiting_for_story = State()
    waiting_for_edit = State()

    # Связь с пользователем по истории
    waiting_for_contact_message = State()

    # Старый ответ поддержки
    waiting_for_support_reply = State()

    # Пользовательский диалог с поддержкой
    waiting_for_support_message = State()

    # Выбор способа экстренной поддержки
    waiting_for_support_method = State()

    # Модератор находится внутри диалога
    moderator_dialog = State()
