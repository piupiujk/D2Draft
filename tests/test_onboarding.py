"""Тесты для bot/handlers/start.py — онбординг нового пользователя."""

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

    _filters.CommandStart = _CommandStart  # type: ignore[attr-defined]
    sys.modules["aiogram.filters"] = _filters

# aiogram.Router и F
_aiogram_mod = sys.modules["aiogram"]

if not hasattr(_aiogram_mod, "Router"):
    class _PassthroughDecorator:
        """Декоратор-заглушка, который возвращает функцию без изменений."""
        def __call__(self, *args, **kwargs):
            # router.message(SomeFilter) -> вызывается с фильтром, возвращает декоратор
            def decorator(fn):
                return fn
            # Если передана функция напрямую — вернуть её
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

from bot.handlers.start import (  # noqa: E402
    cancel_nickname,
    cmd_start,
    confirm_nickname,
    process_mmr,
    process_role,
    process_steam_id,
)
from bot.states.onboarding import OnboardingStates  # noqa: E402
from core.exceptions import SteamProfileClosed  # noqa: E402
from repositories.user import DuplicateUserError  # noqa: E402

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


def _make_state(data: dict | None = None) -> MagicMock:
    """Создать мок FSMContext."""
    state = MagicMock()
    _data = data or {}
    state.get_data = AsyncMock(return_value=_data)
    state.set_state = AsyncMock()
    state.update_data = AsyncMock()
    state.clear = AsyncMock()
    return state


# ---------------------------------------------------------------------------
# Тесты: /start
# ---------------------------------------------------------------------------

class TestCmdStart:
    """Тесты команды /start."""

    def test_existing_user_shows_main_menu(self):
        """Зарегистрированный пользователь — главное меню."""
        msg = _make_message("/start")
        state = _make_state()
        user = {"telegram_id": 123, "username": "TestPlayer"}

        asyncio.run(cmd_start(msg, state, user=user))

        msg.answer.assert_called_once()
        call_kwargs = msg.answer.call_args
        assert "TestPlayer" in call_kwargs[0][0]
        assert call_kwargs[1].get("reply_markup") is not None
        # FSM не должен меняться
        state.set_state.assert_not_called()

    def test_existing_user_no_username(self):
        """Зарегистрированный пользователь без username — показывает 'игрок'."""
        msg = _make_message("/start")
        state = _make_state()
        user = {"telegram_id": 123, "username": None}

        asyncio.run(cmd_start(msg, state, user=user))

        call_text = msg.answer.call_args[0][0]
        assert "игрок" in call_text

    def test_new_user_starts_onboarding(self):
        """Новый пользователь — запуск онбординга."""
        msg = _make_message("/start")
        state = _make_state()

        asyncio.run(cmd_start(msg, state, user=None))

        msg.answer.assert_called_once()
        call_text = msg.answer.call_args[0][0]
        assert "Steam" in call_text
        state.clear.assert_called_once()
        state.set_state.assert_called_once_with(OnboardingStates.waiting_steam_id)


# ---------------------------------------------------------------------------
# Тесты: ввод Steam ID
# ---------------------------------------------------------------------------

class TestProcessSteamId:
    """Тесты обработки ввода Steam ID."""

    def test_valid_steam_id(self):
        """Валидный Steam ID — подтверждение никнейма."""
        msg = _make_message("76561198047104768")
        state = _make_state()

        with patch(
            "bot.handlers.start.SteamClient"
        ) as mock_client:
            instance = mock_client.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.resolve_and_validate = AsyncMock(
                return_value=(76561198047104768, "TestNick")
            )

            asyncio.run(process_steam_id(msg, state))

        state.update_data.assert_called_once()
        call_kwargs = state.update_data.call_args[1]
        assert call_kwargs["steam_id_64"] == 76561198047104768
        assert call_kwargs["persona_name"] == "TestNick"
        state.set_state.assert_called_once_with(OnboardingStates.confirming_nickname)

        # Сообщение содержит никнейм
        answer_text = msg.answer.call_args[0][0]
        assert "TestNick" in answer_text

    def test_closed_profile(self):
        """Закрытый профиль — информативное сообщение."""
        msg = _make_message("76561198047104768")
        state = _make_state()

        with patch(
            "bot.handlers.start.SteamClient"
        ) as mock_client:
            instance = mock_client.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.resolve_and_validate = AsyncMock(
                side_effect=SteamProfileClosed("76561198047104768")
            )

            asyncio.run(process_steam_id(msg, state))

        answer_text = msg.answer.call_args[0][0]
        assert "закрыт" in answer_text.lower()
        state.set_state.assert_not_called()

    def test_invalid_steam_id(self):
        """Невалидный Steam ID — сообщение об ошибке."""
        msg = _make_message("not_a_steam_id_!!!")
        state = _make_state()

        with patch(
            "bot.handlers.start.SteamClient"
        ) as mock_client:
            instance = mock_client.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.resolve_and_validate = AsyncMock(
                side_effect=ValueError("Некорректный формат")
            )

            asyncio.run(process_steam_id(msg, state))

        answer_text = msg.answer.call_args[0][0]
        assert (
            "Не удалось" in answer_text
            or "ошибка" in answer_text.lower()
        )
        state.set_state.assert_not_called()

    def test_empty_text(self):
        """Пустой текст — просьба отправить текстом."""
        msg = _make_message("")
        state = _make_state()

        asyncio.run(process_steam_id(msg, state))

        answer_text = msg.answer.call_args[0][0]
        assert "текст" in answer_text.lower()

    def test_api_error_generic(self):
        """Неожиданная ошибка API — общее сообщение."""
        msg = _make_message("76561198047104768")
        state = _make_state()

        with patch(
            "bot.handlers.start.SteamClient"
        ) as mock_client:
            instance = mock_client.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.resolve_and_validate = AsyncMock(
                side_effect=RuntimeError("Connection timeout")
            )

            asyncio.run(process_steam_id(msg, state))

        answer_text = msg.answer.call_args[0][0]
        assert "ошибка" in answer_text.lower()


# ---------------------------------------------------------------------------
# Тесты: подтверждение никнейма
# ---------------------------------------------------------------------------

class TestConfirmNickname:
    """Тесты подтверждения/отклонения никнейма."""

    def test_confirm_asks_mmr(self):
        """Подтверждение — запрос MMR."""
        cb = _make_callback("common:confirm")
        state = _make_state()

        asyncio.run(confirm_nickname(cb, state))

        cb.answer.assert_called_once()
        cb.message.edit_reply_markup.assert_called_once_with(reply_markup=None)
        cb.message.answer.assert_called_once()
        answer_text = cb.message.answer.call_args[0][0]
        assert "MMR" in answer_text
        state.set_state.assert_called_once_with(OnboardingStates.waiting_mmr)

    def test_cancel_returns_to_steam_id(self):
        """Отмена — возврат к вводу Steam ID."""
        cb = _make_callback("common:cancel")
        state = _make_state()

        asyncio.run(cancel_nickname(cb, state))

        cb.answer.assert_called_once()
        state.set_state.assert_called_once_with(OnboardingStates.waiting_steam_id)


# ---------------------------------------------------------------------------
# Тесты: ввод MMR
# ---------------------------------------------------------------------------

class TestProcessMmr:
    """Тесты обработки ввода MMR."""

    def test_valid_mmr(self):
        """Валидный MMR — выбор роли."""
        msg = _make_message("5000")
        state = _make_state()

        asyncio.run(process_mmr(msg, state))

        state.update_data.assert_called_once_with(mmr=5000)
        state.set_state.assert_called_once_with(OnboardingStates.waiting_role)
        # Сообщение содержит кнопки ролей
        assert msg.answer.call_args[1].get("reply_markup") is not None

    def test_mmr_zero(self):
        """MMR = 0 — допустимо."""
        msg = _make_message("0")
        state = _make_state()

        asyncio.run(process_mmr(msg, state))

        state.update_data.assert_called_once_with(mmr=0)
        state.set_state.assert_called_once_with(OnboardingStates.waiting_role)

    def test_mmr_15000(self):
        """MMR = 15000 — допустимо."""
        msg = _make_message("15000")
        state = _make_state()

        asyncio.run(process_mmr(msg, state))

        state.update_data.assert_called_once_with(mmr=15000)

    def test_mmr_negative(self):
        """Отрицательный MMR — ошибка."""
        msg = _make_message("-100")
        state = _make_state()

        asyncio.run(process_mmr(msg, state))

        answer_text = msg.answer.call_args[0][0]
        assert "0" in answer_text and "15000" in answer_text
        state.set_state.assert_not_called()

    def test_mmr_too_high(self):
        """MMR > 15000 — ошибка."""
        msg = _make_message("20000")
        state = _make_state()

        asyncio.run(process_mmr(msg, state))

        state.set_state.assert_not_called()

    def test_mmr_not_a_number(self):
        """Нечисловой ввод — ошибка."""
        msg = _make_message("высокий")
        state = _make_state()

        asyncio.run(process_mmr(msg, state))

        state.set_state.assert_not_called()


# ---------------------------------------------------------------------------
# Тесты: выбор роли и создание профиля
# ---------------------------------------------------------------------------

class TestProcessRole:
    """Тесты выбора роли и создания профиля."""

    def test_valid_role_creates_user(self):
        """Валидный выбор роли — профиль создан."""
        cb = _make_callback("role:1")
        state = _make_state(data={
            "steam_id": "76561198047104768",
            "persona_name": "TestNick",
            "mmr": 5000,
        })

        with patch(
            "bot.handlers.start.UserRepository"
        ) as mock_repo:
            repo_instance = mock_repo.return_value
            repo_instance.create = AsyncMock(return_value={
                "telegram_id": 123456789,
                "steam_id": "76561198047104768",
                "username": "TestNick",
                "current_mmr": 5000,
                "main_role": 1,
            })

            asyncio.run(process_role(cb, state))

        repo_instance.create.assert_called_once_with(
            telegram_id=123456789,
            steam_id="76561198047104768",
            username="TestNick",
            current_mmr=5000,
            main_role=1,
        )
        state.clear.assert_called_once()
        # Финальное сообщение содержит данные профиля
        answer_text = cb.message.answer.call_args[0][0]
        assert "TestNick" in answer_text
        assert "5000" in answer_text
        assert "Керри" in answer_text

    def test_duplicate_user_error(self):
        """Дублирование аккаунта — информативное сообщение."""
        cb = _make_callback("role:2")
        state = _make_state(data={
            "steam_id": "76561198047104768",
            "persona_name": "TestNick",
            "mmr": 3000,
        })

        with patch(
            "bot.handlers.start.UserRepository"
        ) as mock_repo:
            repo_instance = mock_repo.return_value
            repo_instance.create = AsyncMock(
                side_effect=DuplicateUserError("telegram_id", 123456789)
            )

            asyncio.run(process_role(cb, state))

        answer_text = cb.message.answer.call_args[0][0]
        assert "уже зарегистрирован" in answer_text
        state.clear.assert_called_once()

    def test_invalid_role_callback(self):
        """Невалидный callback роли."""
        cb = _make_callback("role:99")
        state = _make_state()

        asyncio.run(process_role(cb, state))

        cb.answer.assert_called_once()
        answer_text = cb.answer.call_args[0][0]
        assert "Некорректн" in answer_text

    def test_db_error_on_create(self):
        """Ошибка БД при создании — сообщение об ошибке."""
        cb = _make_callback("role:3")
        state = _make_state(data={
            "steam_id": "76561198047104768",
            "persona_name": "TestNick",
            "mmr": 4000,
        })

        with patch(
            "bot.handlers.start.UserRepository"
        ) as mock_repo:
            repo_instance = mock_repo.return_value
            repo_instance.create = AsyncMock(
                side_effect=RuntimeError("DB connection lost")
            )

            asyncio.run(process_role(cb, state))

        answer_text = cb.message.answer.call_args[0][0]
        assert "ошибка" in answer_text.lower()
        state.clear.assert_called_once()


# ---------------------------------------------------------------------------
# Тесты: FSM-состояния
# ---------------------------------------------------------------------------

class TestOnboardingStates:
    """Тесты FSM-состояний."""

    def test_states_exist(self):
        """Все состояния онбординга определены."""
        assert hasattr(OnboardingStates, "waiting_steam_id")
        assert hasattr(OnboardingStates, "confirming_nickname")
        assert hasattr(OnboardingStates, "waiting_mmr")
        assert hasattr(OnboardingStates, "waiting_role")
