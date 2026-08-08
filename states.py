from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):

    # История
    waiting_for_story = State()

    # Редактирование истории
    waiting_for_edit = State()

    # Разовое сообщение автору истории
    waiting_for_contact_message = State()

    # Старый режим ответа на поддержку
    waiting_for_support_reply = State()

    # Первое сообщение пользователя в поддержку
    waiting_for_support_message = State()

    # Активный диалог модератора
    moderator_dialog = State()2
