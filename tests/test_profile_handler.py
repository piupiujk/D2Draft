"""Тесты для bot/handlers/profile.py и core/formatting.py — format_profile."""

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

from bot.handlers.profile import (  # noqa: E402
    _build_profile_response,
    _show_profile,
    btn_profile,
    cmd_profile,
    process_update_mmr,
)
from core.enums import RankBracket, Role  # noqa: E402
from core.formatting import format_profile  # noqa: E402
from services.profile import MmrPoint, TopHero, UserProfile  # noqa: E402

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


def _sample_user() -> dict:
    """Тестовый зарегистрированный пользователь."""
    return {
        "id": 1,
        "telegram_id": 123456789,
        "steam_id": "76561198047104768",
        "username": "TestPlayer",
        "current_mmr": 3500,
        "main_role": 1,
    }


def _sample_profile() -> UserProfile:
    """Тестовый профиль пользователя."""
    return UserProfile(
        current_mmr=3500,
        rank_bracket=RankBracket.LEGEND,
        main_role=Role.CARRY,
        overall_winrate=52.3,
        top_heroes=[
            TopHero(hero_id=1, name_ru="Анти-Маг", name_en="Anti-Mage", games=150, winrate=0.56),
            TopHero(hero_id=2, name_ru="Акс", name_en="Axe", games=120, winrate=0.48),
            TopHero(
                hero_id=11, name_ru="Тень Демона",
                name_en="Shadow Fiend", games=100, winrate=0.51,
            ),
        ],
        winrate_7d=60.0,
        winrate_30d=53.5,
        win_streak=3,
        loss_streak=0,
        mmr_history=[
            MmrPoint(mmr=3500, recorded_at="2026-03-01"),
            MmrPoint(mmr=3450, recorded_at="2026-02-15"),
            MmrPoint(mmr=3400, recorded_at="2026-02-01"),
        ],
        total_matches=1200,
        personaname="TestPlayer",
    )


def _sample_minimal_profile() -> UserProfile:
    """Минимальный профиль без Steam."""
    return UserProfile(
        current_mmr=None,
        rank_bracket=None,
        main_role=None,
        overall_winrate=None,
        personaname="NewPlayer",
    )


# ========================================================================
# Тесты format_profile
# ========================================================================


class TestFormatProfile:
    """Тесты форматирования профиля."""

    def test_contains_personaname(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "TestPlayer" in text

    def test_contains_mmr(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "3500" in text

    def test_contains_rank_medal(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "Легенда" in text

    def test_contains_role(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "Керри" in text

    def test_contains_overall_winrate(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "52.3%" in text

    def test_contains_total_matches(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "1200" in text

    def test_contains_winrate_7d(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "60.0%" in text

    def test_contains_winrate_30d(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "53.5%" in text

    def test_contains_win_streak(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "3" in text
        assert "Серия побед" in text

    def test_loss_streak_displayed(self):
        p = _sample_profile()
        p.win_streak = 0
        p.loss_streak = 5
        text = format_profile(p)
        assert "Серия поражений" in text
        assert "5" in text

    def test_no_streak_when_one(self):
        p = _sample_profile()
        p.win_streak = 1
        p.loss_streak = 0
        text = format_profile(p)
        assert "Серия побед" not in text

    def test_contains_top_heroes(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "Анти-Маг" in text
        assert "Акс" in text
        assert "150 игр" in text

    def test_contains_mmr_dynamics(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "Динамика MMR" in text
        assert "100" in text  # diff 3500 - 3400 = +100
        assert "↑" in text

    def test_negative_mmr_dynamics(self):
        p = _sample_profile()
        # Развернём: первый (свежий) меньше последнего (старого)
        p.mmr_history = [
            MmrPoint(mmr=3300, recorded_at="2026-03-01"),
            MmrPoint(mmr=3500, recorded_at="2026-02-01"),
        ]
        text = format_profile(p)
        assert "↓" in text
        assert "-200" in text

    def test_html_tags_present(self):
        p = _sample_profile()
        text = format_profile(p)
        assert "<b>" in text
        assert "</b>" in text

    def test_length_under_4096(self):
        p = _sample_profile()
        text = format_profile(p)
        assert len(text) <= 4096

    def test_minimal_profile(self):
        p = _sample_minimal_profile()
        text = format_profile(p)
        assert "NewPlayer" in text
        assert "MMR" not in text or "None" not in text

    def test_no_personaname_fallback(self):
        p = _sample_minimal_profile()
        p.personaname = None
        text = format_profile(p)
        assert "Игрок" in text

    def test_hero_winrate_formatted(self):
        p = _sample_profile()
        text = format_profile(p)
        # winrate 0.56 → 56.0%
        assert "56.0%" in text


# ========================================================================
# Тесты cmd_profile
# ========================================================================


class TestCmdProfile:
    """Тесты для команды /profile."""

    def test_not_registered(self):
        msg = _make_message("/profile")
        asyncio.run(cmd_profile(msg, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]

    @patch("bot.handlers.profile._show_profile", new_callable=AsyncMock)
    def test_registered_calls_show(self, mock_show):
        msg = _make_message("/profile")
        user = _sample_user()
        asyncio.run(cmd_profile(msg, user=user))
        mock_show.assert_called_once_with(msg, user)


# ========================================================================
# Тесты btn_profile
# ========================================================================


class TestBtnProfile:
    """Тесты для кнопки 'Мой профиль'."""

    def test_not_registered(self):
        msg = _make_message("Мой профиль")
        asyncio.run(btn_profile(msg, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]

    @patch("bot.handlers.profile._show_profile", new_callable=AsyncMock)
    def test_registered_calls_show(self, mock_show):
        msg = _make_message("Мой профиль")
        user = _sample_user()
        asyncio.run(btn_profile(msg, user=user))
        mock_show.assert_called_once_with(msg, user)


# ========================================================================
# Тесты process_update_mmr
# ========================================================================


class TestProcessUpdateMmr:
    """Тесты для callback обновления MMR."""

    def test_not_registered(self):
        cb = _make_callback("update_mmr")
        asyncio.run(process_update_mmr(cb, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    def test_no_steam_id(self):
        cb = _make_callback("update_mmr")
        user = {"id": 1, "telegram_id": 123, "steam_id": None}
        asyncio.run(process_update_mmr(cb, user=user))
        cb.answer.assert_called_once()
        assert "Steam" in cb.answer.call_args[0][0]

    @patch("bot.handlers.profile._show_profile_edit", new_callable=AsyncMock)
    @patch("bot.handlers.profile.UserRepository")
    @patch("bot.handlers.profile.OpenDotaClient")
    def test_updates_mmr_successfully(self, mock_od_cls, mock_repo_cls, mock_edit):
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_player = MagicMock()
        mock_player.mmr_estimate = 4000
        mock_od.get_player = AsyncMock(return_value=mock_player)
        mock_od_cls.return_value = mock_od

        mock_repo = MagicMock()
        mock_repo.update_mmr = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        cb = _make_callback("update_mmr")
        user = _sample_user()
        asyncio.run(process_update_mmr(cb, user=user))

        cb.answer.assert_called_once()
        assert "обновлён" in cb.answer.call_args[0][0].lower()
        mock_repo.update_mmr.assert_called_once_with(123456789, 4000)
        assert user["current_mmr"] == 4000

    @patch("bot.handlers.profile.OpenDotaClient")
    def test_api_error(self, mock_od_cls):
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od.get_player = AsyncMock(side_effect=RuntimeError("API error"))
        mock_od_cls.return_value = mock_od

        cb = _make_callback("update_mmr")
        user = _sample_user()
        asyncio.run(process_update_mmr(cb, user=user))

        cb.answer.assert_called_once()
        assert "Не удалось" in cb.answer.call_args[0][0]

    @patch("bot.handlers.profile.OpenDotaClient")
    def test_no_mmr_estimate(self, mock_od_cls):
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_player = MagicMock()
        mock_player.mmr_estimate = None
        mock_od.get_player = AsyncMock(return_value=mock_player)
        mock_od_cls.return_value = mock_od

        cb = _make_callback("update_mmr")
        user = _sample_user()
        asyncio.run(process_update_mmr(cb, user=user))

        cb.answer.assert_called_once()
        assert "не удалось определить" in cb.answer.call_args[0][0].lower()


# ========================================================================
# Тесты _show_profile
# ========================================================================


class TestShowProfile:
    """Тесты для _show_profile."""

    @patch("bot.handlers.profile._build_profile_response", new_callable=AsyncMock)
    def test_shows_loading_then_profile(self, mock_build):
        mock_build.return_value = ("<b>Профиль</b>", MagicMock())

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = _sample_user()

        asyncio.run(_show_profile(msg, user))

        # Проверяем сообщение загрузки
        first_call_text = msg.answer.call_args[0][0]
        assert "Загружаю" in first_call_text

        # Проверяем что профиль показан
        loading.edit_text.assert_called_once()


# ========================================================================
# Тесты _build_profile_response
# ========================================================================


class TestBuildProfileResponse:
    """Тесты для _build_profile_response."""

    @patch("bot.handlers.profile.get_user_profile", new_callable=AsyncMock)
    @patch("bot.handlers.profile.OpenDotaClient")
    @patch("bot.handlers.profile.MmrHistoryRepository")
    def test_returns_text_and_keyboard(self, mock_repo_cls, mock_od_cls, mock_get_profile):
        mock_get_profile.return_value = _sample_profile()
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        text, keyboard = asyncio.run(_build_profile_response(_sample_user()))

        assert "TestPlayer" in text
        assert len(keyboard.inline_keyboard) == 1
        assert "MMR" in keyboard.inline_keyboard[0][0].text

    @patch("bot.handlers.profile.get_user_profile", new_callable=AsyncMock)
    @patch("bot.handlers.profile.OpenDotaClient")
    @patch("bot.handlers.profile.MmrHistoryRepository")
    def test_api_error_fallback(self, mock_repo_cls, mock_od_cls, mock_get_profile):
        mock_get_profile.side_effect = RuntimeError("API error")
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        text, keyboard = asyncio.run(_build_profile_response(_sample_user()))

        assert "Не удалось" in text
        # Клавиатура всегда присутствует (для повторной попытки)
        assert keyboard is not None

    @patch("bot.handlers.profile.get_user_profile", new_callable=AsyncMock)
    @patch("bot.handlers.profile.OpenDotaClient")
    @patch("bot.handlers.profile.MmrHistoryRepository")
    def test_profile_contains_heroes(self, mock_repo_cls, mock_od_cls, mock_get_profile):
        mock_get_profile.return_value = _sample_profile()
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        text, _ = asyncio.run(_build_profile_response(_sample_user()))

        assert "Анти-Маг" in text
        assert "Акс" in text

    @patch("bot.handlers.profile.get_user_profile", new_callable=AsyncMock)
    @patch("bot.handlers.profile.OpenDotaClient")
    @patch("bot.handlers.profile.MmrHistoryRepository")
    def test_html_parse_mode(self, mock_repo_cls, mock_od_cls, mock_get_profile):
        mock_get_profile.return_value = _sample_profile()
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        text, _ = asyncio.run(_build_profile_response(_sample_user()))

        assert "<b>" in text
