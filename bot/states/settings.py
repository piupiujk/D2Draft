"""FSM-состояния для хендлера /settings."""

from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    """Состояния диалога настроек."""

    waiting_new_mmr = State()
    waiting_new_steam = State()
