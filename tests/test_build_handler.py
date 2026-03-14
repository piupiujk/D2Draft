"""Тесты для bot/handlers/build.py и core/formatting.py — format_build."""

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

from bot.handlers.build import (  # noqa: E402
    _resolve_and_show_build,
    _show_build,
    btn_build,
    cmd_build,
    process_hero_callback,
    process_hero_name,
)
from core.formatting import format_build  # noqa: E402, I001
from services.build import (  # noqa: E402
    BuildItem,
    HeroBuild,
    SkillSlot,
    TalentChoice,
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


def _make_state() -> MagicMock:
    """Создать мок FSMContext."""
    state = MagicMock()
    state.set_state = AsyncMock()
    state.clear = AsyncMock()
    state.get_data = AsyncMock(return_value={})
    state.update_data = AsyncMock()
    return state


def _sample_user() -> dict:
    """Тестовый зарегистрированный пользователь."""
    return {
        "telegram_id": 123456789,
        "steam_id": "76561198047104768",
        "username": "TestPlayer",
        "current_mmr": 3500,
        "main_role": 1,
    }


def _sample_build() -> HeroBuild:
    """Тестовый билд героя."""
    return HeroBuild(
        hero_id=1,
        name_en="Anti-Mage",
        name_ru="Анти-Маг",
        starting_items=[
            BuildItem(item_id=44, name_en="Tango", name_ru="Танго", winrate=0.52, match_count=5000),
            BuildItem(
                item_id=181,
                name_en="Quelling Blade",
                name_ru="Секач",
                winrate=0.53,
                match_count=5000,
            ),
        ],
        core_items=[
            BuildItem(
                item_id=1,
                name_en="Battle Fury",
                name_ru="Батлфьюри",
                winrate=0.58,
                match_count=4000,
                time=15,
            ),
            BuildItem(
                item_id=2,
                name_en="Manta Style",
                name_ru="Манта",
                winrate=0.61,
                match_count=3500,
                time=25,
            ),
        ],
        situational_items=[
            BuildItem(
                item_id=3, name_en="Black King Bar", name_ru="БКБ", winrate=0.55, match_count=2000
            ),
            BuildItem(
                item_id=4,
                name_en="Abyssal Blade",
                name_ru="Абиссал",
                winrate=0.63,
                match_count=1500,
            ),
        ],
        skill_order=[
            SkillSlot(ability_id=100, slot=2),  # E
            SkillSlot(ability_id=101, slot=0),  # Q
            SkillSlot(ability_id=100, slot=2),  # E
            SkillSlot(ability_id=102, slot=1),  # W
        ],
        talents=[
            TalentChoice(ability_id=200, slot=0, winrate=0.54, match_count=3000),
            TalentChoice(ability_id=201, slot=1, winrate=0.57, match_count=2800),
        ],
        guide_winrate=0.5678,
    )


# ===========================================================================
# Тесты: core/formatting.py — format_build
# ===========================================================================


class TestFormatBuild:
    """Тесты функции format_build."""

    def test_header_with_hero_name(self):
        """Заголовок содержит имя героя на английском."""
        build = _sample_build()
        result = format_build(build)
        assert "Anti-Mage" in result

    def test_guide_winrate_shown(self):
        """Винрейт гайда отображается."""
        build = _sample_build()
        result = format_build(build)
        assert "56.8%" in result

    def test_starting_items_section(self):
        """Секция стартовых предметов."""
        build = _sample_build()
        result = format_build(build)
        assert "Стартовые предметы" in result
        assert "Tango" in result
        assert "Quelling Blade" in result

    def test_core_items_section(self):
        """Секция основных предметов с нумерацией."""
        build = _sample_build()
        result = format_build(build)
        assert "Основные предметы" in result
        assert "Battle Fury" in result
        assert "Manta Style" in result
        assert "1." in result
        assert "2." in result

    def test_core_items_with_winrate(self):
        """Винрейт основных предметов."""
        build = _sample_build()
        result = format_build(build)
        assert "58% WR" in result  # Battle Fury
        assert "61% WR" in result  # Manta Style

    def test_situational_items_section(self):
        """Секция ситуативных предметов."""
        build = _sample_build()
        result = format_build(build)
        assert "Ситуативные предметы" in result
        assert "Black King Bar" in result
        assert "Abyssal Blade" in result

    def test_skill_order_section(self):
        """Секция прокачки скиллов."""
        build = _sample_build()
        result = format_build(build)
        assert "Прокачка скиллов" in result
        assert "E" in result
        assert "Q" in result
        assert "W" in result

    def test_talents_section(self):
        """Секция талантов."""
        build = _sample_build()
        result = format_build(build)
        assert "Таланты" in result
        assert "54%" in result
        assert "57%" in result

    def test_html_tags_present(self):
        """Результат содержит HTML-теги."""
        build = _sample_build()
        result = format_build(build)
        assert "<b>" in result

    def test_length_under_limit(self):
        """Длина не превышает 4096 символов."""
        build = _sample_build()
        result = format_build(build)
        assert len(result) <= 4096

    def test_empty_build(self):
        """Пустой билд — только заголовок."""
        build = HeroBuild(hero_id=1, name_en="Anti-Mage", name_ru="Анти-Маг")
        result = format_build(build)
        assert "Anti-Mage" in result
        # Нет секций предметов
        assert "Стартовые" not in result
        assert "Основные" not in result

    def test_zero_guide_winrate_not_shown(self):
        """Нулевой винрейт гайда не отображается."""
        build = HeroBuild(hero_id=1, name_en="Anti-Mage", name_ru="Анти-Маг", guide_winrate=0.0)
        result = format_build(build)
        assert "Гайд:" not in result


# ===========================================================================
# Тесты: cmd_build
# ===========================================================================


class TestCmdBuild:
    """Тесты команды /build."""

    def test_unregistered_user(self):
        """Незарегистрированный пользователь — предложение /start."""
        msg = _make_message("/build")
        state = _make_state()
        asyncio.run(cmd_build(msg, state, user=None))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "/start" in text

    def test_no_hero_arg_asks_for_input(self):
        """Без аргумента — запрос ввода героя и установка FSM."""
        msg = _make_message("/build")
        state = _make_state()
        user = _sample_user()

        asyncio.run(cmd_build(msg, state, user=user))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "имя героя" in text.lower()
        state.set_state.assert_called_once()

    def test_with_hero_arg_shows_build(self):
        """С аргументом героя — сразу показ билда."""
        msg = _make_message("/build Anti-Mage")
        state = _make_state()
        user = _sample_user()

        with patch(
            "bot.handlers.build._resolve_and_show_build",
            new_callable=AsyncMock,
        ) as mock_resolve:
            asyncio.run(cmd_build(msg, state, user=user))

            mock_resolve.assert_called_once()
            call_args = mock_resolve.call_args[0]
            assert call_args[0] is msg
            assert call_args[1] is state
            assert call_args[2] is user
            assert call_args[3] == "Anti-Mage"

    def test_with_russian_hero_arg(self):
        """С аргументом героя на русском."""
        msg = _make_message("/build Антимаг")
        state = _make_state()
        user = _sample_user()

        with patch(
            "bot.handlers.build._resolve_and_show_build",
            new_callable=AsyncMock,
        ) as mock_resolve:
            asyncio.run(cmd_build(msg, state, user=user))

            mock_resolve.assert_called_once()
            assert mock_resolve.call_args[0][3] == "Антимаг"


# ===========================================================================
# Тесты: btn_build (кнопка «Билд героя»)
# ===========================================================================


class TestBtnBuild:
    """Тесты кнопки 'Билд героя'."""

    def test_unregistered_user(self):
        """Незарегистрированный пользователь — предложение /start."""
        msg = _make_message("Билд героя")
        state = _make_state()
        asyncio.run(btn_build(msg, state, user=None))

        text = msg.answer.call_args[0][0]
        assert "/start" in text

    def test_shows_hero_input_prompt(self):
        """Зарегистрированный пользователь — запрос ввода героя."""
        msg = _make_message("Билд героя")
        state = _make_state()
        user = _sample_user()

        asyncio.run(btn_build(msg, state, user=user))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "имя героя" in text.lower()
        state.set_state.assert_called_once()


# ===========================================================================
# Тесты: process_hero_name (FSM ввод героя)
# ===========================================================================


class TestProcessHeroName:
    """Тесты обработки текстового ввода имени героя."""

    def test_unregistered_user(self):
        """Незарегистрированный — предложение /start, сброс FSM."""
        msg = _make_message("Anti-Mage")
        state = _make_state()
        asyncio.run(process_hero_name(msg, state, user=None))

        text = msg.answer.call_args[0][0]
        assert "/start" in text
        state.clear.assert_called_once()

    def test_empty_text(self):
        """Пустой текст — просьба ввести имя."""
        msg = _make_message("")
        state = _make_state()
        user = _sample_user()

        asyncio.run(process_hero_name(msg, state, user=user))

        text = msg.answer.call_args[0][0]
        assert "имя героя" in text.lower()

    def test_valid_hero_calls_resolve(self):
        """Валидное имя героя — вызов _resolve_and_show_build."""
        msg = _make_message("am")
        state = _make_state()
        user = _sample_user()

        with patch(
            "bot.handlers.build._resolve_and_show_build",
            new_callable=AsyncMock,
        ) as mock_resolve:
            asyncio.run(process_hero_name(msg, state, user=user))

            mock_resolve.assert_called_once()
            assert mock_resolve.call_args[0][3] == "am"


# ===========================================================================
# Тесты: process_hero_callback (inline-кнопка героя)
# ===========================================================================


class TestProcessHeroCallback:
    """Тесты обработки callback_data выбора героя."""

    def test_unregistered_user(self):
        """Незарегистрированный — алерт."""
        cb = _make_callback("hero:1")
        asyncio.run(process_hero_callback(cb, user=None))

        cb.answer.assert_called_once()
        assert cb.answer.call_args[1].get("show_alert") is True

    def test_invalid_hero_id(self):
        """Невалидный callback — сообщение."""
        cb = _make_callback("hero:abc")
        user = _sample_user()

        asyncio.run(process_hero_callback(cb, user=user))

        cb.answer.assert_called_once()
        text = cb.answer.call_args[0][0]
        assert "Некорректный" in text

    def test_valid_hero_shows_build(self):
        """Валидный hero_id — показ билда."""
        cb = _make_callback("hero:1")
        user = _sample_user()

        with patch(
            "bot.handlers.build._show_build",
            new_callable=AsyncMock,
        ) as mock_show:
            asyncio.run(process_hero_callback(cb, user=user))

            cb.answer.assert_called()
            mock_show.assert_called_once()
            call_args = mock_show.call_args[0]
            assert call_args[0] is cb.message
            assert call_args[1] is user
            assert call_args[2] == 1  # hero_id

    def test_unknown_hero_id(self):
        """Неизвестный hero_id — сообщение об ошибке."""
        cb = _make_callback("hero:99999")
        user = _sample_user()

        asyncio.run(process_hero_callback(cb, user=user))

        cb.answer.assert_called()
        cb.message.answer.assert_called_once()
        text = cb.message.answer.call_args[0][0]
        assert "не найден" in text.lower()


# ===========================================================================
# Тесты: _resolve_and_show_build
# ===========================================================================


class TestResolveAndShowBuild:
    """Тесты поиска героя и отображения билда."""

    def test_valid_hero_name(self):
        """Валидное имя — вызов _show_build и сброс FSM."""
        msg = _make_message()
        state = _make_state()
        user = _sample_user()

        with patch(
            "bot.handlers.build._show_build",
            new_callable=AsyncMock,
        ) as mock_show:
            asyncio.run(_resolve_and_show_build(msg, state, user, "Anti-Mage"))

            state.clear.assert_called_once()
            mock_show.assert_called_once()
            call_args = mock_show.call_args[0]
            assert call_args[2] == 1  # hero_id Anti-Mage
            assert call_args[3] == "Анти-Маг"  # name_ru

    def test_valid_alias(self):
        """Алиас героя — находит правильно."""
        msg = _make_message()
        state = _make_state()
        user = _sample_user()

        with patch(
            "bot.handlers.build._show_build",
            new_callable=AsyncMock,
        ) as mock_show:
            asyncio.run(_resolve_and_show_build(msg, state, user, "am"))

            mock_show.assert_called_once()
            assert mock_show.call_args[0][2] == 1  # Anti-Mage

    def test_russian_name(self):
        """Русское имя героя — находит правильно."""
        msg = _make_message()
        state = _make_state()
        user = _sample_user()

        with patch(
            "bot.handlers.build._show_build",
            new_callable=AsyncMock,
        ) as mock_show:
            asyncio.run(_resolve_and_show_build(msg, state, user, "Антимаг"))

            mock_show.assert_called_once()
            assert mock_show.call_args[0][2] == 1  # Anti-Mage

    def test_unknown_hero(self):
        """Неизвестный герой — сообщение 'не найден'."""
        msg = _make_message()
        state = _make_state()
        user = _sample_user()

        asyncio.run(_resolve_and_show_build(msg, state, user, "НесуществующийГерой"))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "не найден" in text.lower()
        assert "НесуществующийГерой" in text


# ===========================================================================
# Тесты: _show_build
# ===========================================================================


class TestShowBuild:
    """Тесты получения и вывода билда."""

    def test_shows_build_successfully(self):
        """Успешный вывод билда."""
        msg = _make_message()
        user = _sample_user()
        build = _sample_build()

        with (
            patch("bot.handlers.build.StratzClient") as mock_stratz_cls,
            patch(
                "bot.handlers.build.get_hero_build",
                new_callable=AsyncMock,
            ) as mock_get_build,
        ):
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(return_value=stratz_inst)
            stratz_inst.__aexit__ = AsyncMock(return_value=False)
            mock_stratz_cls.return_value = stratz_inst

            mock_get_build.return_value = build

            asyncio.run(_show_build(msg, user, 1, "Анти-Маг"))

        msg.answer.assert_called_once()
        call_args = msg.answer.call_args
        text = call_args[0][0]
        assert "Anti-Mage" in text
        assert call_args[1].get("parse_mode") == "HTML"

    def test_uses_user_mmr_for_bracket(self):
        """Использует MMR пользователя для определения брекета."""
        msg = _make_message()
        user = _sample_user()
        user["current_mmr"] = 5500  # Divine
        build = _sample_build()

        with (
            patch("bot.handlers.build.StratzClient") as mock_stratz_cls,
            patch(
                "bot.handlers.build.get_hero_build",
                new_callable=AsyncMock,
            ) as mock_get_build,
        ):
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(return_value=stratz_inst)
            stratz_inst.__aexit__ = AsyncMock(return_value=False)
            mock_stratz_cls.return_value = stratz_inst

            mock_get_build.return_value = build

            asyncio.run(_show_build(msg, user, 1, "Анти-Маг"))

            # Проверяем что get_hero_build вызван с role из user
            call_kwargs = mock_get_build.call_args[1]
            assert call_kwargs["hero_id"] == 1
            assert call_kwargs["role"] == 1  # main_role

    def test_api_error_shows_message(self):
        """Ошибка API — информативное сообщение."""
        msg = _make_message()
        user = _sample_user()

        with patch("bot.handlers.build.StratzClient") as mock_stratz_cls:
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(side_effect=RuntimeError("API down"))
            mock_stratz_cls.return_value = stratz_inst

            asyncio.run(_show_build(msg, user, 1, "Анти-Маг"))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "ошибка" in text.lower() or "недоступен" in text.lower()

    def test_no_mmr_uses_zero(self):
        """Без MMR — используется 0 (Herald)."""
        msg = _make_message()
        user = _sample_user()
        user["current_mmr"] = None
        build = _sample_build()

        with (
            patch("bot.handlers.build.StratzClient") as mock_stratz_cls,
            patch(
                "bot.handlers.build.get_hero_build",
                new_callable=AsyncMock,
            ) as mock_get_build,
        ):
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(return_value=stratz_inst)
            stratz_inst.__aexit__ = AsyncMock(return_value=False)
            mock_stratz_cls.return_value = stratz_inst

            mock_get_build.return_value = build

            asyncio.run(_show_build(msg, user, 1, "Анти-Маг"))

        msg.answer.assert_called_once()
