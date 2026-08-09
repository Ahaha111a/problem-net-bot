from aiogram.fsm.state import State, StatesGroup

class StoryState(StatesGroup):
# История пользователя
waiting_for_story = State()

# Экстренная поддержка
waiting_for_support_method = State()
waiting_for_support_message = State()

# Редактирование истории администратором
waiting_for_edit = State()

# Сообщение пользователю по истории
waiting_for_contact_message = State()

# Ответ администратора в поддержке
waiting_for_support_reply = State()

# Работа администратора внутри диалога
moderator_dialog = State()
