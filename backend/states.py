from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):
    waiting_for_story = State()

    waiting_for_support_method = State()
    waiting_for_support_message = State()

    waiting_for_edit = State()
    waiting_for_contact_message = State()
    waiting_for_reject_reason = State()

    moderator_dialog = State()

    schedule_custom = State()
    role_management = State()
