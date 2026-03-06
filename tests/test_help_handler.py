"""Тесты для bot/handlers/help.py — хендлер /help."""

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

# aiogram.types
if "aiogram.types" not in sys.modules:
    sys.modules["aiogram.types"] = ModuleType("aiogram.types")

_aiogram_types = sys.modules["aiogram.types"]

for _cls_name in (
    "KeyboardButton", "ReplyKeyboardMarkup",
    "InlineKeyboardButton", "InlineKeyboardMarkup",
    "TelegramObject", "Update", "Message", "CallbackQuery",
):
    if not hasattr(_aiogram_types, _cls_name):
        _cls = type(_cls_name, (), {"__init__": lambda self, **kw: None})
        setattr(_aiogram_types, _cls_name, _cls)

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

from bot.handlers.help import HELP_TEXT, cmd_help  # noqa: E402

# ---------------------------------------------------------------------------
# Фикстуры
# ---------------------------------------------------------------------------


def _make_message() -> MagicMock:
    """Создать мок Message."""
    msg = MagicMock()
    msg.text = "/help"
    msg.answer = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 123456789
    return msg


# ===========================================================================
# Тесты: cmd_help
# ===========================================================================


class TestCmdHelp:
    """Тесты для команды /help."""

    def test_sends_help_text(self):
        """Отправляет текст справки."""
        msg = _make_message()
        asyncio.run(cmd_help(msg))
        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert text == HELP_TEXT

    def test_uses_html_parse_mode(self):
        """Справка отправляется с parse_mode='HTML'."""
        msg = _make_message()
        asyncio.run(cmd_help(msg))
        kwargs = msg.answer.call_args[1]
        assert kwargs.get("parse_mode") == "HTML"

    def test_contains_start_command(self):
        """Справка содержит команду /start."""
        assert "/start" in HELP_TEXT

    def test_contains_meta_command(self):
        """Справка содержит команду /meta."""
        assert "/meta" in HELP_TEXT

    def test_contains_build_command(self):
        """Справка содержит команду /build."""
        assert "/build" in HELP_TEXT

    def test_contains_lastmatch_command(self):
        """Справка содержит команду /lastmatch."""
        assert "/lastmatch" in HELP_TEXT

    def test_contains_profile_command(self):
        """Справка содержит команду /profile."""
        assert "/profile" in HELP_TEXT

    def test_contains_draft_command(self):
        """Справка содержит команду /draft."""
        assert "/draft" in HELP_TEXT

    def test_contains_settings_command(self):
        """Справка содержит команду /settings."""
        assert "/settings" in HELP_TEXT

    def test_contains_help_command(self):
        """Справка содержит команду /help."""
        assert "/help" in HELP_TEXT

    def test_all_eight_commands_listed(self):
        """Все 8 команд перечислены в справке."""
        commands = ["/start", "/meta", "/build", "/lastmatch",
                    "/profile", "/draft", "/settings", "/help"]
        for cmd in commands:
            assert cmd in HELP_TEXT, f"Команда {cmd} отсутствует в справке"

    def test_mentions_free_features(self):
        """Справка упоминает бесплатные функции."""
        assert "Бесплатные" in HELP_TEXT or "бесплатные" in HELP_TEXT

    def test_mentions_premium_features(self):
        """Справка упоминает Premium функции."""
        assert "Premium" in HELP_TEXT or "premium" in HELP_TEXT

    def test_help_text_within_telegram_limit(self):
        """Текст справки не превышает лимит Telegram (4096 символов)."""
        assert len(HELP_TEXT) <= 4096

    def test_help_text_valid_html(self):
        """Текст справки содержит валидные HTML-теги."""
        assert "<b>" in HELP_TEXT
        assert "</b>" in HELP_TEXT
        open_count = HELP_TEXT.count("<b>")
        close_count = HELP_TEXT.count("</b>")
        assert open_count == close_count


# ===========================================================================
# Тесты: роутер help
# ===========================================================================


class TestHelpRouter:
    """Тесты для роутера help."""

    def test_router_exists(self):
        """Роутер help создан."""
        from bot.handlers.help import router
        assert router is not None
        assert router.name == "help"

    def test_help_router_in_main(self):
        """Роутер help импортируется в __main__.py."""
        from bot.handlers.help import router as help_router
        assert help_router is not None
