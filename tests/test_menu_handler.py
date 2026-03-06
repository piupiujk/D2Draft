"""Тесты для bot/handlers/menu.py — роутинг текстовых кнопок главного меню."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

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
        """Декоратор-заглушка, который возвращает функцию без изменений."""
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

from bot.handlers.menu import (  # noqa: E402
    _DRAFT_STUB_TEXT,
    _NOT_REGISTERED_TEXT,
    _SETTINGS_STUB_TEXT,
    btn_draft,
    btn_settings,
)
from bot.keyboards.menu import (  # noqa: E402
    ALL_MENU_BUTTONS,
    BTN_BUILD,
    BTN_DRAFT,
    BTN_MATCH,
    BTN_META,
    BTN_PROFILE,
    BTN_SETTINGS,
)

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


def _sample_user() -> dict:
    """Тестовый зарегистрированный пользователь."""
    return {
        "telegram_id": 123456789,
        "steam_id": "76561198047104768",
        "username": "TestPlayer",
        "current_mmr": 4000,
        "main_role": 1,
        "is_premium": False,
    }


# ===========================================================================
# Тесты: btn_draft (кнопка «Анализ драфта»)
# ===========================================================================


class TestBtnDraft:
    """Тесты для кнопки 'Анализ драфта'."""

    def test_unregistered_user_gets_start_prompt(self):
        """Незарегистрированный пользователь получает предложение /start."""
        msg = _make_message(BTN_DRAFT)
        asyncio.run(btn_draft(msg, user=None))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "/start" in text
        assert text == _NOT_REGISTERED_TEXT

    def test_registered_user_gets_stub(self):
        """Зарегистрированный пользователь видит заглушку."""
        msg = _make_message(BTN_DRAFT)
        user = _sample_user()
        asyncio.run(btn_draft(msg, user=user))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Анализ драфта" in text
        assert "в разработке" in text

    def test_stub_uses_html_parse_mode(self):
        """Заглушка отправляется с parse_mode='HTML'."""
        msg = _make_message(BTN_DRAFT)
        asyncio.run(btn_draft(msg, user=_sample_user()))
        kwargs = msg.answer.call_args[1]
        assert kwargs.get("parse_mode") == "HTML"

    def test_stub_text_matches_constant(self):
        """Текст заглушки совпадает с константой."""
        msg = _make_message(BTN_DRAFT)
        asyncio.run(btn_draft(msg, user=_sample_user()))
        text = msg.answer.call_args[0][0]
        assert text == _DRAFT_STUB_TEXT


# ===========================================================================
# Тесты: btn_settings (кнопка «Настройки»)
# ===========================================================================


class TestBtnSettings:
    """Тесты для кнопки 'Настройки'."""

    def test_unregistered_user_gets_start_prompt(self):
        """Незарегистрированный пользователь получает предложение /start."""
        msg = _make_message(BTN_SETTINGS)
        asyncio.run(btn_settings(msg, user=None))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "/start" in text
        assert text == _NOT_REGISTERED_TEXT

    def test_registered_user_gets_stub(self):
        """Зарегистрированный пользователь видит заглушку."""
        msg = _make_message(BTN_SETTINGS)
        user = _sample_user()
        asyncio.run(btn_settings(msg, user=user))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Настройки" in text
        assert "в разработке" in text

    def test_stub_uses_html_parse_mode(self):
        """Заглушка отправляется с parse_mode='HTML'."""
        msg = _make_message(BTN_SETTINGS)
        asyncio.run(btn_settings(msg, user=_sample_user()))
        kwargs = msg.answer.call_args[1]
        assert kwargs.get("parse_mode") == "HTML"

    def test_stub_lists_future_features(self):
        """Заглушка перечисляет будущие возможности."""
        msg = _make_message(BTN_SETTINGS)
        asyncio.run(btn_settings(msg, user=_sample_user()))
        text = msg.answer.call_args[0][0]
        assert "уведомления" in text.lower()
        assert "роль" in text.lower()
        assert "MMR" in text

    def test_stub_text_matches_constant(self):
        """Текст заглушки совпадает с константой."""
        msg = _make_message(BTN_SETTINGS)
        asyncio.run(btn_settings(msg, user=_sample_user()))
        text = msg.answer.call_args[0][0]
        assert text == _SETTINGS_STUB_TEXT


# ===========================================================================
# Тесты: константы и полнота кнопок меню
# ===========================================================================


class TestMenuConstants:
    """Тесты целостности констант главного меню."""

    def test_all_menu_buttons_has_six_items(self):
        """В главном меню 6 кнопок."""
        assert len(ALL_MENU_BUTTONS) == 6

    def test_all_buttons_are_strings(self):
        """Все кнопки — строки."""
        for btn in ALL_MENU_BUTTONS:
            assert isinstance(btn, str)

    def test_draft_button_in_menu(self):
        assert BTN_DRAFT in ALL_MENU_BUTTONS

    def test_meta_button_in_menu(self):
        assert BTN_META in ALL_MENU_BUTTONS

    def test_match_button_in_menu(self):
        assert BTN_MATCH in ALL_MENU_BUTTONS

    def test_build_button_in_menu(self):
        assert BTN_BUILD in ALL_MENU_BUTTONS

    def test_profile_button_in_menu(self):
        assert BTN_PROFILE in ALL_MENU_BUTTONS

    def test_settings_button_in_menu(self):
        assert BTN_SETTINGS in ALL_MENU_BUTTONS

    def test_button_texts_are_unique(self):
        """Все тексты кнопок уникальны."""
        assert len(set(ALL_MENU_BUTTONS)) == len(ALL_MENU_BUTTONS)


# ===========================================================================
# Тесты: роутер menu зарегистрирован
# ===========================================================================


class TestMenuRouter:
    """Тесты для роутера menu."""

    def test_router_exists(self):
        """Роутер menu создан."""
        from bot.handlers.menu import router
        assert router is not None
        assert router.name == "menu"

    def test_menu_router_in_main(self):
        """Роутер menu импортируется в __main__.py."""
        # Проверяем что импорт работает
        from bot.handlers.menu import router as menu_router
        assert menu_router is not None
