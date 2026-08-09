from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):

    # История пользователя
    waiting_for_story = State()

    # Редактирование поста администратором
    waiting_for_edit = State()

    # Написать пользователю по истории
    waiting_for_contact_message = State()

    # Пользовательский диалог с поддержкой
    waiting_for_support_message = State()

    # Выбор способа экстренной поддержки
    waiting_for_support_method = State()

    # Модератор находится внутри диалога
    moderator_dialog = State()
