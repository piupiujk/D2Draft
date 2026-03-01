"""Тесты для bot/handlers/meta.py и core/formatting.py."""

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

from bot.handlers.meta import (  # noqa: E402
    _parse_meta_role_callback,
    _parse_role_from_text,
    _show_meta_heroes,
    btn_meta,
    cmd_meta,
    process_meta_role,
)
from core.enums import Role  # noqa: E402
from core.formatting import format_meta_heroes  # noqa: E402
from services.meta import MetaHero  # noqa: E402

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
        "telegram_id": 123456789,
        "steam_id": "76561198047104768",
        "username": "TestPlayer",
        "current_mmr": 3500,
        "main_role": 1,
    }


def _sample_heroes() -> list[MetaHero]:
    """Тестовый список мета-героев."""
    return [
        MetaHero(
            hero_id=1,
            name_ru="Анти-Маг",
            name_en="Anti-Mage",
            winrate=0.5432,
            pick_rate=0.0821,
            match_count=15000,
            personal_winrate=0.62,
            personal_games=50,
        ),
        MetaHero(
            hero_id=2,
            name_ru="Акс",
            name_en="Axe",
            winrate=0.5215,
            pick_rate=0.0654,
            match_count=12000,
            personal_winrate=None,
            personal_games=None,
        ),
    ]


# ===========================================================================
# Тесты: core/formatting.py — format_meta_heroes
# ===========================================================================


class TestFormatMetaHeroes:
    """Тесты функции format_meta_heroes."""

    def test_empty_list(self):
        """Пустой список — сообщение о нет данных."""
        result = format_meta_heroes([], "Керри")
        assert "Нет данных" in result
        assert "Керри" in result

    def test_heroes_with_personal(self):
        """Герои с личной статистикой."""
        heroes = _sample_heroes()
        result = format_meta_heroes(heroes, "Керри")

        assert "Мета-герои — Керри" in result
        assert "Анти-Маг" in result
        assert "Anti-Mage" in result
        assert "54.3%" in result  # винрейт
        assert "8.2%" in result   # пикрейт
        assert "62.0%" in result  # личный винрейт
        assert "50 игр" in result

    def test_hero_without_personal(self):
        """Герой без личной статистики — нет строки 'Личный'."""
        heroes = [_sample_heroes()[1]]  # Акс без personal
        result = format_meta_heroes(heroes, "Оффлейнер")

        assert "Акс" in result
        assert "Личный" not in result

    def test_html_tags_present(self):
        """Результат содержит HTML-теги для parse_mode."""
        heroes = _sample_heroes()
        result = format_meta_heroes(heroes, "Керри")
        assert "<b>" in result

    def test_length_under_limit(self):
        """Длина результата не превышает 4096 символов."""
        heroes = _sample_heroes()
        result = format_meta_heroes(heroes, "Керри")
        assert len(result) <= 4096

    def test_numbering(self):
        """Герои пронумерованы."""
        heroes = _sample_heroes()
        result = format_meta_heroes(heroes, "Мидер")
        assert "1." in result
        assert "2." in result


# ===========================================================================
# Тесты: _parse_role_from_text
# ===========================================================================


class TestParseRoleFromText:
    """Тесты парсинга роли из текста."""

    def test_carry(self):
        assert _parse_role_from_text("carry") == Role.CARRY

    def test_carry_russian(self):
        assert _parse_role_from_text("керри") == Role.CARRY

    def test_mid(self):
        assert _parse_role_from_text("mid") == Role.MID

    def test_mid_number(self):
        assert _parse_role_from_text("2") == Role.MID

    def test_offlane_russian(self):
        assert _parse_role_from_text("оффлейн") == Role.OFFLANE

    def test_unknown(self):
        assert _parse_role_from_text("xyz") is None

    def test_case_insensitive(self):
        assert _parse_role_from_text("CARRY") == Role.CARRY

    def test_whitespace_stripped(self):
        assert _parse_role_from_text("  mid  ") == Role.MID


# ===========================================================================
# Тесты: _parse_meta_role_callback
# ===========================================================================


class TestParseMetaRoleCallback:
    """Тесты парсинга callback_data для мета-роли."""

    def test_valid(self):
        assert _parse_meta_role_callback("meta_role:1") == Role.CARRY

    def test_all_roles(self):
        for role in Role:
            assert _parse_meta_role_callback(f"meta_role:{role.value}") == role

    def test_invalid_prefix(self):
        assert _parse_meta_role_callback("role:1") is None

    def test_invalid_value(self):
        assert _parse_meta_role_callback("meta_role:99") is None


# ===========================================================================
# Тесты: cmd_meta
# ===========================================================================


class TestCmdMeta:
    """Тесты команды /meta."""

    def test_unregistered_user(self):
        """Незарегистрированный пользователь — предложение /start."""
        msg = _make_message("/meta")
        asyncio.run(cmd_meta(msg, user=None))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "/start" in text

    def test_no_role_arg_shows_keyboard(self):
        """Без аргумента — клавиатура выбора роли."""
        msg = _make_message("/meta")
        user = _sample_user()

        asyncio.run(cmd_meta(msg, user=user))

        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
        assert call_kwargs[1].get("reply_markup") is not None
        text = call_kwargs[0][0]
        assert "роль" in text.lower()

    def test_with_role_arg_shows_heroes(self):
        """С аргументом роли — сразу список героев."""
        msg = _make_message("/meta mid")
        user = _sample_user()

        with patch(
            "bot.handlers.meta._show_meta_heroes", new_callable=AsyncMock
        ) as mock_show:
            asyncio.run(cmd_meta(msg, user=user))

            mock_show.assert_called_once()
            call_args = mock_show.call_args
            assert call_args[0][0] is msg
            assert call_args[0][1] is user
            assert call_args[0][2] == Role.MID

    def test_with_invalid_role_arg_shows_keyboard(self):
        """Невалидный аргумент роли — клавиатура выбора роли."""
        msg = _make_message("/meta бред")
        user = _sample_user()

        asyncio.run(cmd_meta(msg, user=user))

        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
        assert call_kwargs[1].get("reply_markup") is not None

    def test_with_russian_role_arg(self):
        """Аргумент роли на русском — работает."""
        msg = _make_message("/meta керри")
        user = _sample_user()

        with patch(
            "bot.handlers.meta._show_meta_heroes", new_callable=AsyncMock
        ) as mock_show:
            asyncio.run(cmd_meta(msg, user=user))
            mock_show.assert_called_once()
            assert mock_show.call_args[0][2] == Role.CARRY


# ===========================================================================
# Тесты: btn_meta (кнопка «Герои меты»)
# ===========================================================================


class TestBtnMeta:
    """Тесты кнопки 'Герои меты'."""

    def test_unregistered_user(self):
        """Незарегистрированный пользователь — предложение /start."""
        msg = _make_message("Герои меты")
        asyncio.run(btn_meta(msg, user=None))

        text = msg.answer.call_args[0][0]
        assert "/start" in text

    def test_shows_role_keyboard(self):
        """Зарегистрированный пользователь — клавиатура выбора роли."""
        msg = _make_message("Герои меты")
        user = _sample_user()

        asyncio.run(btn_meta(msg, user=user))

        call_kwargs = msg.answer.call_args
        assert call_kwargs[1].get("reply_markup") is not None


# ===========================================================================
# Тесты: process_meta_role (callback выбора роли)
# ===========================================================================


class TestProcessMetaRole:
    """Тесты обработки callback выбора роли."""

    def test_unregistered_user(self):
        """Незарегистрированный пользователь — алерт."""
        cb = _make_callback("meta_role:1")
        asyncio.run(process_meta_role(cb, user=None))

        cb.answer.assert_called_once()
        call_kwargs = cb.answer.call_args
        assert call_kwargs[1].get("show_alert") is True

    def test_invalid_role(self):
        """Невалидная роль — сообщение."""
        cb = _make_callback("meta_role:99")
        user = _sample_user()

        asyncio.run(process_meta_role(cb, user=user))

        cb.answer.assert_called_once()
        text = cb.answer.call_args[0][0]
        assert "Некорректный" in text

    def test_valid_role_calls_show(self):
        """Валидная роль — вызов _show_meta_heroes."""
        cb = _make_callback("meta_role:1")
        user = _sample_user()

        with patch(
            "bot.handlers.meta._show_meta_heroes", new_callable=AsyncMock
        ) as mock_show:
            asyncio.run(process_meta_role(cb, user=user))

            cb.answer.assert_called()
            cb.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
            mock_show.assert_called_once()
            assert mock_show.call_args[0][2] == Role.CARRY


# ===========================================================================
# Тесты: _show_meta_heroes
# ===========================================================================


class TestShowMetaHeroes:
    """Тесты вывода мета-героев."""

    def test_shows_heroes(self):
        """Успешный вывод мета-героев."""
        msg = _make_message()
        user = _sample_user()
        heroes = _sample_heroes()

        with patch(
            "bot.handlers.meta.StratzClient"
        ) as mock_stratz_cls, patch(
            "bot.handlers.meta.OpenDotaClient"
        ) as mock_opendota_cls, patch(
            "bot.handlers.meta.get_meta_heroes", new_callable=AsyncMock
        ) as mock_get:
            # Мокаем StratzClient context manager
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(return_value=stratz_inst)
            stratz_inst.__aexit__ = AsyncMock(return_value=False)
            mock_stratz_cls.return_value = stratz_inst

            # Мокаем OpenDotaClient context manager
            opendota_inst = MagicMock()
            opendota_inst.__aenter__ = AsyncMock(return_value=opendota_inst)
            opendota_inst.__aexit__ = AsyncMock(return_value=False)
            mock_opendota_cls.return_value = opendota_inst

            mock_get.return_value = heroes

            asyncio.run(_show_meta_heroes(msg, user, Role.CARRY))

        msg.answer.assert_called_once()
        call_args = msg.answer.call_args
        text = call_args[0][0]
        assert "Анти-Маг" in text
        assert "Акс" in text
        assert call_args[1].get("parse_mode") == "HTML"
        # Должна быть inline-клавиатура с героями
        assert call_args[1].get("reply_markup") is not None

    def test_api_error_shows_message(self):
        """Ошибка API — информативное сообщение."""
        msg = _make_message()
        user = _sample_user()

        with patch(
            "bot.handlers.meta.StratzClient"
        ) as mock_stratz_cls:
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(side_effect=RuntimeError("API down"))
            mock_stratz_cls.return_value = stratz_inst

            asyncio.run(_show_meta_heroes(msg, user, Role.CARRY))

        msg.answer.assert_called_once()
        text = msg.answer.call_args[0][0]
        assert "Не удалось" in text

    def test_no_steam_id_skips_opendota(self):
        """Без steam_id — OpenDota не вызывается."""
        msg = _make_message()
        user = _sample_user()
        user["steam_id"] = None
        heroes = _sample_heroes()

        with patch(
            "bot.handlers.meta.StratzClient"
        ) as mock_stratz_cls, patch(
            "bot.handlers.meta.OpenDotaClient"
        ) as mock_opendota_cls, patch(
            "bot.handlers.meta.get_meta_heroes", new_callable=AsyncMock
        ) as mock_get:
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(return_value=stratz_inst)
            stratz_inst.__aexit__ = AsyncMock(return_value=False)
            mock_stratz_cls.return_value = stratz_inst

            mock_get.return_value = heroes

            asyncio.run(_show_meta_heroes(msg, user, Role.MID))

        # OpenDotaClient не создавался
        mock_opendota_cls.assert_not_called()

    def test_empty_heroes_no_keyboard(self):
        """Пустой список героев — нет inline-клавиатуры."""
        msg = _make_message()
        user = _sample_user()

        with patch(
            "bot.handlers.meta.StratzClient"
        ) as mock_stratz_cls, patch(
            "bot.handlers.meta.OpenDotaClient"
        ) as mock_opendota_cls, patch(
            "bot.handlers.meta.get_meta_heroes", new_callable=AsyncMock
        ) as mock_get:
            stratz_inst = MagicMock()
            stratz_inst.__aenter__ = AsyncMock(return_value=stratz_inst)
            stratz_inst.__aexit__ = AsyncMock(return_value=False)
            mock_stratz_cls.return_value = stratz_inst

            opendota_inst = MagicMock()
            opendota_inst.__aenter__ = AsyncMock(return_value=opendota_inst)
            opendota_inst.__aexit__ = AsyncMock(return_value=False)
            mock_opendota_cls.return_value = opendota_inst

            mock_get.return_value = []

            asyncio.run(_show_meta_heroes(msg, user, Role.CARRY))

        call_kwargs = msg.answer.call_args[1]
        assert call_kwargs.get("reply_markup") is None
        text = msg.answer.call_args[0][0]
        assert "Нет данных" in text
