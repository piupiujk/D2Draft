"""FSM-состояния для хендлера /build."""

from aiogram.fsm.state import State, StatesGroup


class BuildStates(StatesGroup):
    """Состояния диалога ввода героя для билда."""

    waiting_hero_name = State()
