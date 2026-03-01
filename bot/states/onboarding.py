"""FSM-состояния онбординга нового пользователя."""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """Состояния диалога онбординга (/start для нового пользователя)."""

    waiting_steam_id = State()
    confirming_nickname = State()
    waiting_mmr = State()
    waiting_role = State()
