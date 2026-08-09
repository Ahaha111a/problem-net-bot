from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):
    waiting_for_story = State()
    waiting_for_edit = State()

    # Старый контакт по истории
    waiting_for_contact_message = State()

    # Старый ответ на поддержку
    waiting_for_support_reply = State()

    # Диалог пользователь ↔ модератор
    waiting_for_support_message = State()
    moderator_dialog = State()

    # Выбор способа экстренной поддержки
    waiting_for_support_method = State()
