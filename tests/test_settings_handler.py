"""Тесты для bot/handlers/settings.py — хендлер /settings."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Мокаем зависимости aiogram до импорта тестируемых модулей
# ---------------------------------------------------------------------------

if "aiogram" not in sys.modules:
    _aiogram = ModuleType("aiogram")

    class _BaseMiddleware:
        pass

    _aiogram.BaseMiddleware = _BaseMiddleware  # type: ignore[attr-defined]
    sys.modules["aiogram"] = _aiogram

# aiogram.types — создаём или дополняем существующий мок
if "aiogram.types" not in sys.modules:
    sys.modules["aiogram.types"] = ModuleType("aiogram.types")

_aiogram_types = sys.modules["aiogram.types"]

if not hasattr(_aiogram_types, "KeyboardButton"):
    class _KeyboardButton:
        def __init__(self, text: str, **kwargs):
            self.text = text
    _aiogram_types.KeyboardButton = _KeyboardButton  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "ReplyKeyboardMarkup"):
    class _ReplyKeyboardMarkup:
        def __init__(self, keyboard=None, resize_keyboard=False, **kwargs):
            self.keyboard = keyboard or []
            self.resize_keyboard = resize_keyboard
            for k, v in kwargs.items():
                setattr(self, k, v)
    _aiogram_types.ReplyKeyboardMarkup = _ReplyKeyboardMarkup  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "InlineKeyboardButton"):
    class _InlineKeyboardButton:
        def __init__(self, text: str, callback_data: str | None = None, **kwargs):
            self.text = text
            self.callback_data = callback_data
    _aiogram_types.InlineKeyboardButton = _InlineKeyboardButton  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "InlineKeyboardMarkup"):
    class _InlineKeyboardMarkup:
        def __init__(self, inline_keyboard=None, **kwargs):
            self.inline_keyboard = inline_keyboard or []
    _aiogram_types.InlineKeyboardMarkup = _InlineKeyboardMarkup  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "TelegramObject"):
    class _TelegramObject:
        pass
    _aiogram_types.TelegramObject = _TelegramObject  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "Update"):
    class _Update:
        def __init__(self):
            self.message = None
            self.callback_query = None
            self.inline_query = None
    _aiogram_types.Update = _Update  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "Message"):
    class _Message:
        pass
    _aiogram_types.Message = _Message  # type: ignore[attr-defined]

if not hasattr(_aiogram_types, "CallbackQuery"):
    class _CallbackQuery:
        pass
    _aiogram_types.CallbackQuery = _CallbackQuery  # type: ignore[attr-defined]

# aiogram.fsm
if "aiogram.fsm" not in sys.modules:
    sys.modules["aiogram.fsm"] = ModuleType("aiogram.fsm")

if "aiogram.fsm.state" not in sys.modules:
    _fsm_state = ModuleType("aiogram.fsm.state")

    class _State:
        def __init__(self, state=None, group_name=None):
            pass

    class _StatesGroupMeta(type):
        def __new__(mcs, name, bases, namespace):
            cls = super().__new__(mcs, name, bases, namespace)
            for attr_name, attr_value in namespace.items():
                if isinstance(attr_value, _State):
                    setattr(cls, attr_name, f"{name}:{attr_name}")
            return cls

    class _StatesGroup(metaclass=_StatesGroupMeta):
        pass

    _fsm_state.State = _State  # type: ignore[attr-defined]
    _fsm_state.StatesGroup = _StatesGroup  # type: ignore[attr-defined]
    sys.modules["aiogram.fsm.state"] = _fsm_state

if "aiogram.fsm.context" not in sys.modules:
    _fsm_context = ModuleType("aiogram.fsm.context")

    class _FSMContext:
        pass

    _fsm_context.FSMContext = _FSMContext  # type: ignore[attr-defined]
    sys.modules["aiogram.fsm.context"] = _fsm_context

# aiogram.filters
if "aiogram.filters" not in sys.modules:
    _filters = ModuleType("aiogram.filters")

    class _CommandStart:
        def __init__(self, **kwargs):
            pass

    class _Command:
        def __init__(self, *args, **kwargs):
            pass

    _filters.CommandStart = _CommandStart  # type: ignore[attr-defined]
    _filters.Command = _Command  # type: ignore[attr-defined]
    sys.modules["aiogram.filters"] = _filters
else:
    _filters = sys.modules["aiogram.filters"]
    if not hasattr(_filters, "Command"):
        class _Command:
            def __init__(self, *args, **kwargs):
                pass
        _filters.Command = _Command  # type: ignore[attr-defined]

# aiogram.Router и F
_aiogram_mod = sys.modules["aiogram"]

if not hasattr(_aiogram_mod, "Router"):
    class _PassthroughDecorator:
        def __call__(self, *args, **kwargs):
            def decorator(fn):
                return fn
            if args and callable(args[0]):
                return args[0]
            return decorator

    class _Router:
        def __init__(self, name=None):
            self.name = name
            self.message = _PassthroughDecorator()
            self.callback_query = _PassthroughDecorator()

        def include_router(self, r):
            pass

    _aiogram_mod.Router = _Router  # type: ignore[attr-defined]

if not hasattr(_aiogram_mod, "F"):
    class _FProxy:
        def __getattr__(self, name):
            return _FProxy()
        def __eq__(self, other):
            return _FProxy()
        def startswith(self, prefix):
            return _FProxy()

    _aiogram_mod.F = _FProxy()  # type: ignore[attr-defined]

if not hasattr(_aiogram_mod, "Bot"):
    class _Bot:
        def __init__(self, **kwargs):
            self.session = MagicMock()
            self.session.close = AsyncMock()

    _aiogram_mod.Bot = _Bot  # type: ignore[attr-defined]

if not hasattr(_aiogram_mod, "Dispatcher"):
    class _Dispatcher:
        def __init__(self, **kwargs):
            self.update = MagicMock()

        def include_router(self, r):
            pass

        async def start_polling(self, bot):
            pass

    _aiogram_mod.Dispatcher = _Dispatcher  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Мокаем pydantic_settings и bot.config
# ---------------------------------------------------------------------------

if "pydantic_settings" not in sys.modules:
    _ps = ModuleType("pydantic_settings")

    class _BaseSettings:
        model_config: dict = {}

        def __init__(self, **kwargs):
            pass

        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)

    _ps.BaseSettings = _BaseSettings  # type: ignore[attr-defined]
    sys.modules["pydantic_settings"] = _ps

if "bot.config" not in sys.modules:
    _bot_config = ModuleType("bot.config")

    class _MockSettings:
        BOT_TOKEN = "test_token"
        SUPABASE_URL = "https://test.supabase.co"
        SUPABASE_KEY = "test_key"
        STRATZ_TOKEN = "test_stratz"
        OPENDOTA_BASE_URL = "https://api.opendota.com/api"
        LLM_API_KEY = ""
        LLM_PROVIDER = "openai"
        STEAM_API_KEY = "test_steam_key"
        REDIS_URL = ""

    _bot_config.settings = _MockSettings()  # type: ignore[attr-defined]
    sys.modules["bot.config"] = _bot_config

# ---------------------------------------------------------------------------
# Мокаем supabase
# ---------------------------------------------------------------------------

if "supabase" not in sys.modules:
    _supabase_mod = ModuleType("supabase")
    _supabase_mod.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    _supabase_mod.create_async_client = AsyncMock()  # type: ignore[attr-defined]
    sys.modules["supabase"] = _supabase_mod
else:
    _supabase_mod = sys.modules["supabase"]
    if not hasattr(_supabase_mod, "AsyncClient"):
        _supabase_mod.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    if not hasattr(_supabase_mod, "create_async_client"):
        _supabase_mod.create_async_client = AsyncMock()  # type: ignore[attr-defined]
if "supabase._async" not in sys.modules:
    sys.modules["supabase._async"] = ModuleType("supabase._async")
if "supabase._async.client" not in sys.modules:
    _async_client_mod = ModuleType("supabase._async.client")
    _async_client_mod.create_client = AsyncMock()  # type: ignore[attr-defined]
    _async_client_mod.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    sys.modules["supabase._async.client"] = _async_client_mod

# ---------------------------------------------------------------------------
# Импортируем тестируемые модули
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

from bot.handlers.settings import (  # noqa: E402
    _CB_SETTINGS_ROLE_PREFIX,
    _settings_kb,
    _settings_menu_text,
    btn_settings,
    change_role_menu,
    change_steam_menu,
    cmd_settings,
    process_new_mmr,
    process_new_steam,
    process_role_change,
    toggle_notifications,
    update_mmr_settings,
)
from bot.states.settings import SettingsStates  # noqa: E402

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


def _make_message(text: str = "") -> MagicMock:
    """Создать мок Message."""
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 123456789
    return msg


def _make_callback(data: str = "") -> MagicMock:
    """Создать мок CallbackQuery."""
    cb = MagicMock()
    cb.data = data
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.from_user = MagicMock()
    cb.from_user.id = 123456789
    return cb


def _make_state() -> MagicMock:
    """Создать мок FSMContext."""
    state = MagicMock()
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    return state


def _sample_user() -> dict:
    """Тестовый зарегистрированный пользователь."""
    return {
        "id": 1,
        "telegram_id": 123456789,
        "steam_id": "76561198047104768",
        "username": "TestPlayer",
        "current_mmr": 3500,
        "main_role": 1,
        "notifications_enabled": True,
        "is_premium": False,
    }


# ========================================================================
# Тесты _settings_menu_text
# ========================================================================


class TestSettingsMenuText:
    """Тесты для текста меню настроек."""

    def test_contains_settings_header(self):
        text = _settings_menu_text(_sample_user())
        assert "Настройки" in text

    def test_contains_notifications_status_enabled(self):
        text = _settings_menu_text(_sample_user())
        assert "Вкл" in text

    def test_contains_notifications_status_disabled(self):
        user = _sample_user()
        user["notifications_enabled"] = False
        text = _settings_menu_text(user)
        assert "Выкл" in text

    def test_contains_role(self):
        text = _settings_menu_text(_sample_user())
        assert "Керри" in text

    def test_contains_mmr(self):
        text = _settings_menu_text(_sample_user())
        assert "3500" in text

    def test_contains_steam_id(self):
        text = _settings_menu_text(_sample_user())
        assert "76561198047104768" in text

    def test_no_role_shows_dash(self):
        user = _sample_user()
        user["main_role"] = None
        text = _settings_menu_text(user)
        assert "—" in text

    def test_no_mmr_shows_dash(self):
        user = _sample_user()
        user["current_mmr"] = None
        text = _settings_menu_text(user)
        # MMR строка содержит тире
        assert "—" in text

    def test_html_tags(self):
        text = _settings_menu_text(_sample_user())
        assert "<b>" in text


# ========================================================================
# Тесты _settings_kb
# ========================================================================


class TestSettingsKb:
    """Тесты для клавиатуры настроек."""

    def test_has_four_buttons(self):
        kb = _settings_kb(_sample_user())
        assert len(kb.inline_keyboard) == 4

    def test_toggle_text_when_enabled(self):
        kb = _settings_kb(_sample_user())
        assert "Выключить" in kb.inline_keyboard[0][0].text

    def test_toggle_text_when_disabled(self):
        user = _sample_user()
        user["notifications_enabled"] = False
        kb = _settings_kb(user)
        assert "Включить" in kb.inline_keyboard[0][0].text

    def test_change_role_button(self):
        kb = _settings_kb(_sample_user())
        assert "роль" in kb.inline_keyboard[1][0].text.lower()

    def test_update_mmr_button(self):
        kb = _settings_kb(_sample_user())
        assert "MMR" in kb.inline_keyboard[2][0].text

    def test_change_steam_button(self):
        kb = _settings_kb(_sample_user())
        assert "Steam" in kb.inline_keyboard[3][0].text


# ========================================================================
# Тесты cmd_settings
# ========================================================================


class TestCmdSettings:
    """Тесты для команды /settings."""

    def test_not_registered(self):
        msg = _make_message("/settings")
        state = _make_state()
        asyncio.run(cmd_settings(msg, state, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]

    def test_registered_shows_menu(self):
        msg = _make_message("/settings")
        state = _make_state()
        user = _sample_user()
        asyncio.run(cmd_settings(msg, state, user=user))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Настройки" in text
        assert "Керри" in text

    def test_uses_html_parse_mode(self):
        msg = _make_message("/settings")
        state = _make_state()
        asyncio.run(cmd_settings(msg, state, user=_sample_user()))
        kwargs = msg.answer.call_args[1]
        assert kwargs.get("parse_mode") == "HTML"

    def test_clears_state(self):
        msg = _make_message("/settings")
        state = _make_state()
        asyncio.run(cmd_settings(msg, state, user=_sample_user()))
        state.clear.assert_called_once()


# ========================================================================
# Тесты btn_settings
# ========================================================================


class TestBtnSettings:
    """Тесты для кнопки 'Настройки'."""

    def test_not_registered(self):
        msg = _make_message("Настройки")
        state = _make_state()
        asyncio.run(btn_settings(msg, state, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]

    def test_registered_shows_menu(self):
        msg = _make_message("Настройки")
        state = _make_state()
        user = _sample_user()
        asyncio.run(btn_settings(msg, state, user=user))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Настройки" in text


# ========================================================================
# Тесты toggle_notifications
# ========================================================================


class TestToggleNotifications:
    """Тесты для переключения уведомлений."""

    def test_not_registered(self):
        cb = _make_callback("settings:toggle_notif")
        asyncio.run(toggle_notifications(cb, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    @patch("bot.handlers.settings.UserRepository")
    def test_disables_notifications(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback("settings:toggle_notif")
        user = _sample_user()  # notifications_enabled=True
        asyncio.run(toggle_notifications(cb, user=user))

        mock_repo.update.assert_called_once_with(123456789, notifications_enabled=False)
        assert user["notifications_enabled"] is False
        cb.answer.assert_called_once()
        assert "выключены" in cb.answer.call_args[0][0]

    @patch("bot.handlers.settings.UserRepository")
    def test_enables_notifications(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback("settings:toggle_notif")
        user = _sample_user()
        user["notifications_enabled"] = False
        asyncio.run(toggle_notifications(cb, user=user))

        mock_repo.update.assert_called_once_with(123456789, notifications_enabled=True)
        assert user["notifications_enabled"] is True
        assert "включены" in cb.answer.call_args[0][0]

    @patch("bot.handlers.settings.UserRepository")
    def test_updates_message_after_toggle(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback("settings:toggle_notif")
        asyncio.run(toggle_notifications(cb, user=_sample_user()))

        cb.message.edit_text.assert_called_once()

    @patch("bot.handlers.settings.UserRepository")
    def test_error_handling(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback("settings:toggle_notif")
        asyncio.run(toggle_notifications(cb, user=_sample_user()))

        cb.answer.assert_called_once()
        assert "Не удалось" in cb.answer.call_args[0][0]


# ========================================================================
# Тесты change_role_menu
# ========================================================================


class TestChangeRoleMenu:
    """Тесты для меню смены роли."""

    def test_not_registered(self):
        cb = _make_callback("settings:change_role")
        asyncio.run(change_role_menu(cb, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    def test_shows_role_selection(self):
        cb = _make_callback("settings:change_role")
        asyncio.run(change_role_menu(cb, user=_sample_user()))
        cb.answer.assert_called_once()
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "роль" in text.lower()


# ========================================================================
# Тесты process_role_change
# ========================================================================


class TestProcessRoleChange:
    """Тесты для обработки смены роли."""

    def test_not_registered(self):
        cb = _make_callback(f"{_CB_SETTINGS_ROLE_PREFIX}3")
        asyncio.run(process_role_change(cb, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    def test_invalid_role(self):
        cb = _make_callback(f"{_CB_SETTINGS_ROLE_PREFIX}99")
        asyncio.run(process_role_change(cb, user=_sample_user()))
        cb.answer.assert_called_once()
        assert "Некорректный" in cb.answer.call_args[0][0]

    @patch("bot.handlers.settings.UserRepository")
    def test_changes_role(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback(f"{_CB_SETTINGS_ROLE_PREFIX}3")
        user = _sample_user()
        asyncio.run(process_role_change(cb, user=user))

        mock_repo.update.assert_called_once_with(123456789, main_role=3)
        assert user["main_role"] == 3
        cb.answer.assert_called_once()
        assert "Оффлейнер" in cb.answer.call_args[0][0]

    @patch("bot.handlers.settings.UserRepository")
    def test_updates_message_after_change(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback(f"{_CB_SETTINGS_ROLE_PREFIX}2")
        asyncio.run(process_role_change(cb, user=_sample_user()))

        cb.message.edit_text.assert_called_once()

    @patch("bot.handlers.settings.UserRepository")
    def test_error_handling(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback(f"{_CB_SETTINGS_ROLE_PREFIX}4")
        asyncio.run(process_role_change(cb, user=_sample_user()))

        cb.answer.assert_called_once()
        assert "Не удалось" in cb.answer.call_args[0][0]


# ========================================================================
# Тесты update_mmr_settings
# ========================================================================


class TestUpdateMmrSettings:
    """Тесты для кнопки обновления MMR."""

    def test_not_registered(self):
        cb = _make_callback("settings:update_mmr")
        state = _make_state()
        asyncio.run(update_mmr_settings(cb, state, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    def test_shows_mmr_prompt(self):
        cb = _make_callback("settings:update_mmr")
        state = _make_state()
        asyncio.run(update_mmr_settings(cb, state, user=_sample_user()))
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "MMR" in text
        state.set_state.assert_called_once()


# ========================================================================
# Тесты process_new_mmr
# ========================================================================


class TestProcessNewMmr:
    """Тесты для обработки ввода нового MMR."""

    def test_not_registered(self):
        msg = _make_message("3000")
        state = _make_state()
        asyncio.run(process_new_mmr(msg, state, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]
        state.clear.assert_called_once()

    def test_invalid_not_number(self):
        msg = _make_message("abc")
        state = _make_state()
        asyncio.run(process_new_mmr(msg, state, user=_sample_user()))
        msg.answer.assert_called_once()
        assert "0 до 15000" in msg.answer.call_args[0][0]

    def test_invalid_negative(self):
        msg = _make_message("-100")
        state = _make_state()
        asyncio.run(process_new_mmr(msg, state, user=_sample_user()))
        msg.answer.assert_called_once()
        assert "0 до 15000" in msg.answer.call_args[0][0]

    def test_invalid_too_high(self):
        msg = _make_message("20000")
        state = _make_state()
        asyncio.run(process_new_mmr(msg, state, user=_sample_user()))
        msg.answer.assert_called_once()
        assert "0 до 15000" in msg.answer.call_args[0][0]

    @patch("bot.handlers.settings.UserRepository")
    def test_valid_mmr(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update_mmr = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        msg = _make_message("4500")
        state = _make_state()
        user = _sample_user()
        asyncio.run(process_new_mmr(msg, state, user=user))

        mock_repo.update_mmr.assert_called_once_with(123456789, 4500)
        assert user["current_mmr"] == 4500
        state.clear.assert_called_once()
        # Показывает меню настроек
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Настройки" in text

    @patch("bot.handlers.settings.UserRepository")
    def test_valid_zero_mmr(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update_mmr = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        msg = _make_message("0")
        state = _make_state()
        user = _sample_user()
        asyncio.run(process_new_mmr(msg, state, user=user))

        mock_repo.update_mmr.assert_called_once_with(123456789, 0)

    @patch("bot.handlers.settings.UserRepository")
    def test_valid_max_mmr(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update_mmr = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        msg = _make_message("15000")
        state = _make_state()
        user = _sample_user()
        asyncio.run(process_new_mmr(msg, state, user=user))

        mock_repo.update_mmr.assert_called_once_with(123456789, 15000)

    @patch("bot.handlers.settings.UserRepository")
    def test_db_error(self, mock_repo_cls):
        mock_repo = MagicMock()
        mock_repo.update_mmr = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_repo_cls.return_value = mock_repo

        msg = _make_message("3000")
        state = _make_state()
        asyncio.run(process_new_mmr(msg, state, user=_sample_user()))

        msg.answer.assert_called_once()
        assert "Не удалось" in msg.answer.call_args[0][0]
        state.clear.assert_called_once()


# ========================================================================
# Тесты change_steam_menu
# ========================================================================


class TestChangeSteamMenu:
    """Тесты для кнопки смены Steam."""

    def test_not_registered(self):
        cb = _make_callback("settings:change_steam")
        state = _make_state()
        asyncio.run(change_steam_menu(cb, state, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    def test_shows_steam_prompt(self):
        cb = _make_callback("settings:change_steam")
        state = _make_state()
        asyncio.run(change_steam_menu(cb, state, user=_sample_user()))
        cb.message.edit_text.assert_called_once()
        text = cb.message.edit_text.call_args[0][0]
        assert "Steam" in text
        state.set_state.assert_called_once()


# ========================================================================
# Тесты process_new_steam
# ========================================================================


class TestProcessNewSteam:
    """Тесты для обработки ввода нового Steam ID."""

    def test_not_registered(self):
        msg = _make_message("76561198047104768")
        state = _make_state()
        asyncio.run(process_new_steam(msg, state, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]
        state.clear.assert_called_once()

    def test_empty_input(self):
        msg = _make_message("")
        state = _make_state()
        asyncio.run(process_new_steam(msg, state, user=_sample_user()))
        msg.answer.assert_called_once()
        assert "Steam ID" in msg.answer.call_args[0][0]

    @patch("bot.handlers.settings.SteamClient")
    @patch("bot.handlers.settings.UserRepository")
    def test_valid_steam_id(self, mock_repo_cls, mock_steam_cls):
        mock_steam = MagicMock()
        mock_steam.__aenter__ = AsyncMock(return_value=mock_steam)
        mock_steam.__aexit__ = AsyncMock(return_value=False)
        mock_steam.resolve_and_validate = AsyncMock(
            return_value=(76561198047104768, "NewNick")
        )
        mock_steam_cls.return_value = mock_steam

        mock_repo = MagicMock()
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        msg = _make_message("76561198047104768")
        state = _make_state()
        user = _sample_user()
        asyncio.run(process_new_steam(msg, state, user=user))

        mock_repo.update.assert_called_once_with(
            123456789,
            steam_id="76561198047104768",
            username="NewNick",
        )
        assert user["steam_id"] == "76561198047104768"
        assert user["username"] == "NewNick"
        state.clear.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "обновлён" in text.lower()
        assert "NewNick" in text

    @patch("bot.handlers.settings.SteamClient")
    def test_closed_profile(self, mock_steam_cls):
        from core.exceptions import SteamProfileClosed

        mock_steam = MagicMock()
        mock_steam.__aenter__ = AsyncMock(return_value=mock_steam)
        mock_steam.__aexit__ = AsyncMock(return_value=False)
        mock_steam.resolve_and_validate = AsyncMock(
            side_effect=SteamProfileClosed("closed")
        )
        mock_steam_cls.return_value = mock_steam

        msg = _make_message("76561198047104768")
        state = _make_state()
        asyncio.run(process_new_steam(msg, state, user=_sample_user()))

        msg.answer.assert_called_once()
        assert "закрыт" in msg.answer.call_args[0][0].lower()

    @patch("bot.handlers.settings.SteamClient")
    def test_invalid_steam_id(self, mock_steam_cls):
        mock_steam = MagicMock()
        mock_steam.__aenter__ = AsyncMock(return_value=mock_steam)
        mock_steam.__aexit__ = AsyncMock(return_value=False)
        mock_steam.resolve_and_validate = AsyncMock(
            side_effect=ValueError("Invalid Steam ID")
        )
        mock_steam_cls.return_value = mock_steam

        msg = _make_message("invalid_id")
        state = _make_state()
        asyncio.run(process_new_steam(msg, state, user=_sample_user()))

        msg.answer.assert_called_once()
        assert "Не удалось распознать" in msg.answer.call_args[0][0]

    @patch("bot.handlers.settings.SteamClient")
    def test_api_error(self, mock_steam_cls):
        mock_steam = MagicMock()
        mock_steam.__aenter__ = AsyncMock(return_value=mock_steam)
        mock_steam.__aexit__ = AsyncMock(return_value=False)
        mock_steam.resolve_and_validate = AsyncMock(
            side_effect=RuntimeError("API error")
        )
        mock_steam_cls.return_value = mock_steam

        msg = _make_message("76561198047104768")
        state = _make_state()
        asyncio.run(process_new_steam(msg, state, user=_sample_user()))

        msg.answer.assert_called_once()
        assert "ошибка" in msg.answer.call_args[0][0].lower()
        state.clear.assert_called_once()


# ========================================================================
# Тесты: роутер settings
# ========================================================================


class TestSettingsRouter:
    """Тесты для роутера settings."""

    def test_router_exists(self):
        from bot.handlers.settings import router
        assert router is not None
        assert router.name == "settings"

    def test_states_defined(self):
        assert hasattr(SettingsStates, "waiting_new_mmr")
        assert hasattr(SettingsStates, "waiting_new_steam")
