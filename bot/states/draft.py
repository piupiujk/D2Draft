"""FSM-состояния для анализа драфта."""

from aiogram.fsm.state import State, StatesGroup


class DraftStates(StatesGroup):
    """Состояния FSM для flow анализа драфта."""

    waiting_screenshot = State()
    confirming_heroes = State()
