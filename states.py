from aiogram.fsm.state import StatesGroup, State


class StoryState(StatesGroup):
    waiting_for_story = State()
