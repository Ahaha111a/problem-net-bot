from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):
    waiting_for_story = State()
    waiting_for_edit = State()

    waiting_for_contact_message = State()
    waiting_for_support_reply = State()

    # Пользовательский диалог с модератором
    waiting_for_support_message = State()

    # Выбор способа экстренной поддержки
    waiting_for_support_method = State()

    # Модератор находится внутри диалога
    moderator_dialog = State()
