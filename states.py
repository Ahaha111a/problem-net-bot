from aiogram.fsm.state import State, StatesGroup


class StoryState(StatesGroup):
    waiting_for_story = State()
    waiting_for_edit = State()
