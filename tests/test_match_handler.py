"""Тесты для bot/handlers/match.py и core/formatting.py — format_match_analysis."""

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

from bot.handlers.match import (  # noqa: E402
    _get_user_role,
    _show_last_match,
    btn_match,
    cmd_lastmatch,
    process_ai_advice,
)
from core.enums import MatchOutcome, Role  # noqa: E402
from core.formatting import format_match_analysis  # noqa: E402
from services.match_analysis import MatchAnalysis, RoleMetric  # noqa: E402

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
    cb.message.edit_reply_markup = AsyncMock()
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


def _sample_analysis() -> MatchAnalysis:
    """Тестовый анализ матча."""
    return MatchAnalysis(
        match_id=7654321000,
        hero_id=1,
        hero_name_ru="Анти-Маг",
        hero_name_en="Anti-Mage",
        role=Role.CARRY,
        role_detected=True,
        duration_sec=2100,  # 35 мин
        result=MatchOutcome.WIN,
        kills=12,
        deaths=3,
        assists=8,
        metrics=[
            RoleMetric(name="gold_per_min", label_ru="GPM", value=650, median=550),
            RoleMetric(name="xp_per_min", label_ru="XPM", value=700, median=600),
            RoleMetric(name="last_hits", label_ru="Ластхиты", value=320, median=291.7),
            RoleMetric(name="hero_damage", label_ru="Урон героям", value=28000, median=23333),
            RoleMetric(name="tower_damage", label_ru="Урон строениям", value=7500, median=5833),
        ],
    )


def _sample_loss_analysis() -> MatchAnalysis:
    """Тестовый анализ проигранного матча саппорта."""
    return MatchAnalysis(
        match_id=7654321001,
        hero_id=5,
        hero_name_ru="Кристал Мэйден",
        hero_name_en="Crystal Maiden",
        role=Role.HARD_SUPPORT,
        role_detected=True,
        duration_sec=1800,
        result=MatchOutcome.LOSS,
        kills=2,
        deaths=10,
        assists=20,
        metrics=[
            RoleMetric(name="obs_placed", label_ru="Обсервер варды", value=15, median=12),
            RoleMetric(name="sen_placed", label_ru="Сентри варды", value=8, median=10),
            RoleMetric(name="hero_healing", label_ru="Лечение", value=2000, median=5000),
            RoleMetric(name="assists", label_ru="Ассисты", value=20, median=18),
            RoleMetric(name="stuns", label_ru="Оглушение (сек)", value=50, median=35),
        ],
    )


# ========================================================================
# Тесты format_match_analysis
# ========================================================================


class TestFormatMatchAnalysis:
    """Тесты форматирования анализа матча."""

    def test_contains_match_id(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert str(a.match_id) in text

    def test_contains_hero_names(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "Анти-Маг" in text
        assert "Anti-Mage" in text

    def test_win_result_displayed(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "Победа" in text
        assert "✅" in text

    def test_loss_result_displayed(self):
        a = _sample_loss_analysis()
        text = format_match_analysis(a)
        assert "Поражение" in text
        assert "❌" in text

    def test_duration_formatted(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "35:00" in text

    def test_kda_displayed(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "12/3/8" in text

    def test_role_displayed(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "Керри" in text

    def test_metrics_displayed(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "GPM" in text
        assert "XPM" in text
        assert "650" in text

    def test_median_comparison(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "медиана" in text

    def test_positive_diff_green(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        # GPM 650 > median 550 → зелёный
        assert "🟢" in text

    def test_negative_diff_red(self):
        a = _sample_loss_analysis()
        text = format_match_analysis(a)
        # hero_healing 2000 < median 5000 → красный
        assert "🔴" in text

    def test_html_tags_present(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert "<b>" in text
        assert "</b>" in text

    def test_length_under_4096(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        assert len(text) <= 4096

    def test_empty_metrics(self):
        a = _sample_analysis()
        a.metrics = []
        text = format_match_analysis(a)
        assert "Метрики" not in text
        assert str(a.match_id) in text

    def test_large_values_formatted(self):
        a = _sample_analysis()
        text = format_match_analysis(a)
        # hero_damage=28000 должен быть отформатирован с пробелом
        assert "28 000" in text

    def test_support_metrics(self):
        a = _sample_loss_analysis()
        text = format_match_analysis(a)
        assert "Обсервер варды" in text
        assert "Лечение" in text


# ========================================================================
# Тесты _get_user_role
# ========================================================================


class TestGetUserRole:
    """Тесты для _get_user_role."""

    def test_valid_role(self):
        assert _get_user_role({"main_role": 1}) == Role.CARRY

    def test_valid_role_5(self):
        assert _get_user_role({"main_role": 5}) == Role.HARD_SUPPORT

    def test_none_role(self):
        assert _get_user_role({"main_role": None}) is None

    def test_missing_role(self):
        assert _get_user_role({}) is None

    def test_invalid_role(self):
        assert _get_user_role({"main_role": "abc"}) is None


# ========================================================================
# Тесты cmd_lastmatch
# ========================================================================


class TestCmdLastmatch:
    """Тесты для команды /lastmatch."""

    def test_not_registered(self):
        msg = _make_message("/lastmatch")
        asyncio.run(cmd_lastmatch(msg, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]

    @patch("bot.handlers.match._show_last_match", new_callable=AsyncMock)
    def test_registered_calls_show(self, mock_show):
        msg = _make_message("/lastmatch")
        user = _sample_user()
        asyncio.run(cmd_lastmatch(msg, user=user, is_premium=False))
        mock_show.assert_called_once_with(msg, user, False)

    @patch("bot.handlers.match._show_last_match", new_callable=AsyncMock)
    def test_premium_passed(self, mock_show):
        msg = _make_message("/lastmatch")
        user = _sample_user()
        asyncio.run(cmd_lastmatch(msg, user=user, is_premium=True))
        mock_show.assert_called_once_with(msg, user, True)


# ========================================================================
# Тесты btn_match
# ========================================================================


class TestBtnMatch:
    """Тесты для кнопки 'Разбор матча'."""

    def test_not_registered(self):
        msg = _make_message("Разбор матча")
        asyncio.run(btn_match(msg, user=None))
        msg.answer.assert_called_once()
        assert "зарегистрироваться" in msg.answer.call_args[0][0]

    @patch("bot.handlers.match._show_last_match", new_callable=AsyncMock)
    def test_registered_calls_show(self, mock_show):
        msg = _make_message("Разбор матча")
        user = _sample_user()
        asyncio.run(btn_match(msg, user=user, is_premium=False))
        mock_show.assert_called_once_with(msg, user, False)


# ========================================================================
# Тесты process_ai_advice
# ========================================================================


class TestProcessAiAdvice:
    """Тесты для callback AI-совета."""

    def test_not_registered(self):
        cb = _make_callback("ai_advice:123")
        asyncio.run(process_ai_advice(cb, user=None))
        cb.answer.assert_called_once()
        assert "зарегистрироваться" in cb.answer.call_args[0][0]

    def test_not_premium(self):
        cb = _make_callback("ai_advice:123")
        user = _sample_user()
        asyncio.run(process_ai_advice(cb, user=user, is_premium=False))
        cb.answer.assert_called_once()
        assert "Premium" in cb.answer.call_args[0][0]

    def test_premium_stub(self):
        cb = _make_callback("ai_advice:123")
        user = _sample_user()
        asyncio.run(process_ai_advice(cb, user=user, is_premium=True))
        cb.answer.assert_called_once()
        assert "разработке" in cb.answer.call_args[0][0]


# ========================================================================
# Тесты _show_last_match
# ========================================================================


class TestShowLastMatch:
    """Тесты для _show_last_match."""

    def test_no_steam_id(self):
        msg = _make_message()
        user = {"id": 1, "telegram_id": 123, "steam_id": None, "main_role": 1}
        asyncio.run(_show_last_match(msg, user, False))
        msg.answer.assert_called_once()
        assert "Steam" in msg.answer.call_args[0][0]

    def test_invalid_steam_id(self):
        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = {"id": 1, "telegram_id": 123, "steam_id": "not_a_number", "main_role": 1}
        asyncio.run(_show_last_match(msg, user, False))
        loading.edit_text.assert_called_once()
        assert "Не удалось" in loading.edit_text.call_args[0][0]

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_shows_analysis(self, mock_repo_cls, mock_od_cls, mock_analyze):
        analysis = _sample_analysis()
        mock_analyze.return_value = analysis
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = _sample_user()

        asyncio.run(_show_last_match(msg, user, False))

        loading.edit_text.assert_called_once()
        call_kwargs = loading.edit_text.call_args
        text = call_kwargs[0][0]
        assert "Анти-Маг" in text
        assert "Premium" in text  # текст о подписке для free

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_premium_gets_button(self, mock_repo_cls, mock_od_cls, mock_analyze):
        analysis = _sample_analysis()
        mock_analyze.return_value = analysis
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = _sample_user()

        asyncio.run(_show_last_match(msg, user, True))

        call_kwargs = loading.edit_text.call_args
        text = call_kwargs[0][0]
        assert "Premium" not in text  # нет текста о подписке
        # Проверяем что передана клавиатура
        reply_markup = call_kwargs[1].get("reply_markup")
        assert reply_markup is not None
        assert len(reply_markup.inline_keyboard) == 1
        btn = reply_markup.inline_keyboard[0][0]
        assert "AI" in btn.text

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_no_matches_error(self, mock_repo_cls, mock_od_cls, mock_analyze):
        mock_analyze.side_effect = ValueError("У игрока нет недавних матчей")
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = _sample_user()

        asyncio.run(_show_last_match(msg, user, False))

        loading.edit_text.assert_called_once()
        text = loading.edit_text.call_args[0][0]
        assert "недавних матчей" in text.lower() or "Сыграй" in text

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_api_error(self, mock_repo_cls, mock_od_cls, mock_analyze):
        mock_analyze.side_effect = RuntimeError("API timeout")
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = _sample_user()

        asyncio.run(_show_last_match(msg, user, False))

        loading.edit_text.assert_called_once()
        assert "Не удалось" in loading.edit_text.call_args[0][0]

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_loading_message_shown(self, mock_repo_cls, mock_od_cls, mock_analyze):
        analysis = _sample_analysis()
        mock_analyze.return_value = analysis
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        user = _sample_user()

        asyncio.run(_show_last_match(msg, user, False))

        # msg.answer вызван с текстом загрузки
        first_call_text = msg.answer.call_args[0][0]
        assert "Анализирую" in first_call_text

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_user_without_db_id(self, mock_repo_cls, mock_od_cls, mock_analyze):
        analysis = _sample_analysis()
        mock_analyze.return_value = analysis
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)
        # Пользователь без id в БД
        user = {"telegram_id": 123, "steam_id": "76561198047104768", "main_role": 1}

        asyncio.run(_show_last_match(msg, user, False))

        # analyze_last_match вызван с match_repo=None
        call_kwargs = mock_analyze.call_args[1]
        assert call_kwargs["match_repo"] is None

    @patch("bot.handlers.match.analyze_last_match", new_callable=AsyncMock)
    @patch("bot.handlers.match.OpenDotaClient")
    @patch("bot.handlers.match.MatchAnalysisRepository")
    def test_metrics_match_role(self, mock_repo_cls, mock_od_cls, mock_analyze):
        """Проверяем что метрики соответствуют роли в отображении."""
        analysis = _sample_analysis()  # CARRY
        mock_analyze.return_value = analysis
        mock_od = MagicMock()
        mock_od.__aenter__ = AsyncMock(return_value=mock_od)
        mock_od.__aexit__ = AsyncMock(return_value=False)
        mock_od_cls.return_value = mock_od

        msg = _make_message()
        loading = MagicMock()
        loading.edit_text = AsyncMock()
        msg.answer = AsyncMock(return_value=loading)

        asyncio.run(_show_last_match(msg, _sample_user(), False))

        text = loading.edit_text.call_args[0][0]
        assert "GPM" in text
        # carry не должен показывать варды
        assert "Обсервер варды" not in text
