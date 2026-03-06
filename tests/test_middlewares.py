"""Тесты для bot/middlewares/ — auth, subscription, throttle."""

import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

# --- Мокаем зависимости aiogram ---

if "aiogram" not in sys.modules:
    _aiogram = ModuleType("aiogram")

    class _BaseMiddleware:
        pass

    _aiogram.BaseMiddleware = _BaseMiddleware  # type: ignore[attr-defined]
    sys.modules["aiogram"] = _aiogram

    _aiogram_types = ModuleType("aiogram.types")

    class _TelegramObject:
        pass

    class _Update(_TelegramObject):
        def __init__(self):
            self.message = None
            self.callback_query = None
            self.inline_query = None

    class _ContentType:
        PHOTO = "photo"
        TEXT = "text"

    _aiogram_types.TelegramObject = _TelegramObject  # type: ignore[attr-defined]
    _aiogram_types.Update = _Update  # type: ignore[attr-defined]
    _aiogram_types.ContentType = _ContentType  # type: ignore[attr-defined]
    sys.modules["aiogram.types"] = _aiogram_types

if "supabase" not in sys.modules:
    _mock_supabase = ModuleType("supabase")
    _mock_supabase.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    _mock_supabase.create_async_client = AsyncMock()  # type: ignore[attr-defined]
    sys.modules["supabase"] = _mock_supabase

if "bot.config" not in sys.modules:
    _mock_config = ModuleType("bot.config")
    _settings = MagicMock()
    _settings.SUPABASE_URL = "https://test.supabase.co"
    _settings.SUPABASE_KEY = "test-key"
    _mock_config.settings = _settings  # type: ignore[attr-defined]
    sys.modules["bot.config"] = _mock_config

from bot.middlewares.auth import AuthMiddleware, _extract_telegram_id  # noqa: E402
from bot.middlewares.subscription import SubscriptionMiddleware, _check_premium  # noqa: E402
from bot.middlewares.throttle import (  # noqa: E402
    ThrottleMiddleware,
    _llm_bucket,
    check_llm_limit,
)

# --- Хелперы для создания мок-событий ---


def _make_update_with_message(user_id: int):
    """Создать мок Update с Message и from_user."""
    update = MagicMock()
    update.__class__ = sys.modules["aiogram.types"].Update
    # isinstance проверка
    from aiogram.types import Update
    update.__class__ = Update

    user = MagicMock()
    user.id = user_id
    message = MagicMock()
    message.from_user = user
    update.message = message
    update.callback_query = None
    update.inline_query = None
    return update


def _make_update_with_callback(user_id: int):
    """Создать мок Update с CallbackQuery."""
    from aiogram.types import Update
    update = MagicMock()
    update.__class__ = Update

    user = MagicMock()
    user.id = user_id
    callback = MagicMock()
    callback.from_user = user
    update.message = None
    update.callback_query = callback
    update.inline_query = None
    return update


def _make_direct_event(user_id: int):
    """Создать мок прямого события (Message) без обёртки Update."""
    event = MagicMock()
    # Убеждаемся что это НЕ Update
    event.__class__ = MagicMock
    user = MagicMock()
    user.id = user_id
    event.from_user = user
    return event


def _make_event_no_user():
    """Создать мок события без from_user."""
    event = MagicMock()
    event.__class__ = MagicMock
    event.from_user = None
    return event


# ============================================================
# Тесты AuthMiddleware
# ============================================================


class TestExtractTelegramId:
    """Тесты извлечения telegram_id из событий."""

    def test_extract_from_update_message(self):
        update = _make_update_with_message(12345)
        assert _extract_telegram_id(update) == 12345

    def test_extract_from_update_callback(self):
        update = _make_update_with_callback(67890)
        assert _extract_telegram_id(update) == 67890

    def test_extract_from_direct_event(self):
        event = _make_direct_event(11111)
        assert _extract_telegram_id(event) == 11111

    def test_extract_returns_none_for_no_user(self):
        event = _make_event_no_user()
        assert _extract_telegram_id(event) is None


class TestAuthMiddleware:
    """Тесты AuthMiddleware — загрузка пользователя из БД."""

    def test_registered_user_loaded(self):
        """Зарегистрированный пользователь — data['user'] заполнен."""
        user_data = {"id": "uuid-1", "telegram_id": 12345, "username": "tester"}
        repo = MagicMock()
        repo.get_by_telegram_id = AsyncMock(return_value=user_data)

        middleware = AuthMiddleware(user_repo=repo)
        handler = AsyncMock(return_value="ok")
        event = _make_update_with_message(12345)
        data: dict = {}

        result = asyncio.run(middleware(handler, event, data))

        assert data["user"] == user_data
        repo.get_by_telegram_id.assert_awaited_once_with(12345)
        handler.assert_awaited_once()
        assert result == "ok"

    def test_unregistered_user_none(self):
        """Незарегистрированный пользователь — data['user'] = None."""
        repo = MagicMock()
        repo.get_by_telegram_id = AsyncMock(return_value=None)

        middleware = AuthMiddleware(user_repo=repo)
        handler = AsyncMock(return_value="ok")
        event = _make_update_with_message(99999)
        data: dict = {}

        asyncio.run(middleware(handler, event, data))

        assert data["user"] is None

    def test_no_user_in_event(self):
        """Событие без from_user — data['user'] = None, хендлер вызван."""
        repo = MagicMock()
        repo.get_by_telegram_id = AsyncMock()

        middleware = AuthMiddleware(user_repo=repo)
        handler = AsyncMock(return_value="ok")
        event = _make_event_no_user()
        data: dict = {}

        asyncio.run(middleware(handler, event, data))

        assert data["user"] is None
        repo.get_by_telegram_id.assert_not_awaited()
        handler.assert_awaited_once()

    def test_default_repo_created(self):
        """Без явного repo — создаётся UserRepository по умолчанию."""
        middleware = AuthMiddleware()
        assert middleware._user_repo is not None


# ============================================================
# Тесты SubscriptionMiddleware
# ============================================================


class TestCheckPremium:
    """Тесты функции _check_premium."""

    def test_none_user(self):
        assert _check_premium(None) is False

    def test_not_premium(self):
        user = {"is_premium": False}
        assert _check_premium(user) is False

    def test_premium_no_expiry(self):
        """Premium без expires_at — считаем активным."""
        user = {"is_premium": True, "premium_expires_at": None}
        assert _check_premium(user) is True

    def test_premium_future_expiry(self):
        """Premium с будущей датой истечения — активен."""
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        user = {"is_premium": True, "premium_expires_at": future}
        assert _check_premium(user) is True

    def test_premium_past_expiry(self):
        """Premium с прошедшей датой — НЕ активен."""
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        user = {"is_premium": True, "premium_expires_at": past}
        assert _check_premium(user) is False

    def test_premium_datetime_object(self):
        """expires_at как объект datetime."""
        future = datetime.now(timezone.utc) + timedelta(days=10)
        user = {"is_premium": True, "premium_expires_at": future}
        assert _check_premium(user) is True

    def test_premium_invalid_expiry_string(self):
        """Невалидная строка expires_at — считаем НЕ premium."""
        user = {"is_premium": True, "premium_expires_at": "not-a-date"}
        assert _check_premium(user) is False

    def test_missing_is_premium_key(self):
        """Нет ключа is_premium — считаем НЕ premium."""
        user = {"username": "test"}
        assert _check_premium(user) is False


class TestSubscriptionMiddleware:
    """Тесты SubscriptionMiddleware."""

    def test_premium_user_gets_is_premium_true(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        user = {"is_premium": True, "premium_expires_at": future}

        middleware = SubscriptionMiddleware()
        handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data: dict = {"user": user}

        asyncio.run(middleware(handler, event, data))

        assert data["is_premium"] is True
        handler.assert_awaited_once()

    def test_free_user_gets_is_premium_false(self):
        user = {"is_premium": False}

        middleware = SubscriptionMiddleware()
        handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data: dict = {"user": user}

        asyncio.run(middleware(handler, event, data))

        assert data["is_premium"] is False

    def test_no_user_gets_is_premium_false(self):
        middleware = SubscriptionMiddleware()
        handler = AsyncMock(return_value="ok")
        event = MagicMock()
        data: dict = {"user": None}

        asyncio.run(middleware(handler, event, data))

        assert data["is_premium"] is False


# ============================================================
# Тесты ThrottleMiddleware
# ============================================================


class TestThrottleMiddleware:
    """Тесты ThrottleMiddleware — rate limiting."""

    def test_under_limit_passes(self):
        """Запросы в пределах лимита — хендлер вызывается."""
        middleware = ThrottleMiddleware(rate_limit=5, window_sec=60)
        handler = AsyncMock(return_value="ok")
        event = _make_update_with_message(12345)
        data: dict = {}

        for _ in range(5):
            result = asyncio.run(middleware(handler, event, data))
            assert result == "ok"

        assert handler.await_count == 5

    def test_over_limit_blocks(self):
        """Превышение лимита — хендлер НЕ вызывается."""
        middleware = ThrottleMiddleware(rate_limit=3, window_sec=60)
        handler = AsyncMock(return_value="ok")
        event = _make_update_with_message(12345)
        # Мокаем event.message.answer чтобы не падал
        event.message.answer = AsyncMock()
        data: dict = {}

        for _ in range(3):
            asyncio.run(middleware(handler, event, data))

        # 4-й запрос — блокировка
        result = asyncio.run(middleware(handler, event, data))
        assert result is None
        assert handler.await_count == 3  # только 3 вызова, 4-й заблокирован

    def test_different_users_independent(self):
        """Лимиты для разных пользователей независимы."""
        middleware = ThrottleMiddleware(rate_limit=2, window_sec=60)
        handler = AsyncMock(return_value="ok")

        event_a = _make_update_with_message(111)
        event_b = _make_update_with_message(222)

        asyncio.run(middleware(handler, event_a, {}))
        asyncio.run(middleware(handler, event_a, {}))
        asyncio.run(middleware(handler, event_b, {}))
        asyncio.run(middleware(handler, event_b, {}))

        assert handler.await_count == 4

    def test_window_expires_resets(self):
        """После истечения окна — лимит сбрасывается."""
        middleware = ThrottleMiddleware(rate_limit=2, window_sec=1)
        handler = AsyncMock(return_value="ok")
        event = _make_update_with_message(12345)
        event.message.answer = AsyncMock()

        # Исчерпываем лимит
        asyncio.run(middleware(handler, event, {}))
        asyncio.run(middleware(handler, event, {}))

        # Превышение
        result = asyncio.run(middleware(handler, event, {}))
        assert result is None
        assert handler.await_count == 2

        # Сдвигаем время — мокаем monotonic
        with patch("bot.middlewares.throttle.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2
            result = asyncio.run(middleware(handler, event, {}))
            assert result == "ok"

    def test_no_user_passes_through(self):
        """Событие без from_user — пропускаем без throttling."""
        middleware = ThrottleMiddleware(rate_limit=1, window_sec=60)
        handler = AsyncMock(return_value="ok")
        event = _make_event_no_user()

        result = asyncio.run(middleware(handler, event, {}))
        assert result == "ok"
        handler.assert_awaited_once()

    def test_throttle_sends_warning_message(self):
        """При блокировке — отправляется предупреждение через message.answer."""
        middleware = ThrottleMiddleware(rate_limit=1, window_sec=60)
        handler = AsyncMock(return_value="ok")
        event = _make_update_with_message(12345)
        event.message.answer = AsyncMock()

        asyncio.run(middleware(handler, event, {}))
        asyncio.run(middleware(handler, event, {}))

        event.message.answer.assert_awaited_once()

    def test_image_limit_separate(self):
        """Отдельный лимит для изображений (5/мин по умолчанию)."""
        from aiogram.types import ContentType

        middleware = ThrottleMiddleware(message_limit=30, image_limit=2, image_window=60)
        handler = AsyncMock(return_value="ok")

        # Создаём событие с фото
        event = _make_update_with_message(12345)
        event.message.content_type = ContentType.PHOTO
        event.message.answer = AsyncMock()

        # 2 фото — проходят
        asyncio.run(middleware(handler, event, {}))
        asyncio.run(middleware(handler, event, {}))
        assert handler.await_count == 2

        # 3-е фото — блокировка
        result = asyncio.run(middleware(handler, event, {}))
        assert result is None
        assert handler.await_count == 2

    def test_image_and_text_limits_independent(self):
        """Лимиты для текста и изображений независимы."""
        from aiogram.types import ContentType

        middleware = ThrottleMiddleware(message_limit=2, image_limit=2)
        handler = AsyncMock(return_value="ok")

        # Текстовые сообщения
        text_event = _make_update_with_message(12345)
        text_event.message.content_type = ContentType.TEXT

        # Фото
        photo_event = _make_update_with_message(12345)
        photo_event.message.content_type = ContentType.PHOTO
        photo_event.message.answer = AsyncMock()

        # 2 текста — ок
        asyncio.run(middleware(handler, text_event, {}))
        asyncio.run(middleware(handler, text_event, {}))
        assert handler.await_count == 2

        # 2 фото — ок (независимый лимит)
        asyncio.run(middleware(handler, photo_event, {}))
        asyncio.run(middleware(handler, photo_event, {}))
        assert handler.await_count == 4

    def test_image_throttle_warning_text(self):
        """При превышении лимита изображений — сообщение об изображениях."""
        from aiogram.types import ContentType

        middleware = ThrottleMiddleware(image_limit=1, image_window=60)
        handler = AsyncMock(return_value="ok")

        event = _make_update_with_message(12345)
        event.message.content_type = ContentType.PHOTO
        event.message.answer = AsyncMock()

        asyncio.run(middleware(handler, event, {}))
        asyncio.run(middleware(handler, event, {}))

        event.message.answer.assert_awaited_once()
        call_text = event.message.answer.call_args[0][0]
        assert "изображений" in call_text


class TestLlmRateLimit:
    """Тесты check_llm_limit — лимит LLM-запросов."""

    def setup_method(self):
        """Очистить глобальный LLM bucket перед каждым тестом."""
        _llm_bucket._requests.clear()

    def test_llm_limit_allows_under_limit(self):
        """Запросы в пределах лимита — разрешены."""
        for _ in range(10):
            assert check_llm_limit(12345) is True

    def test_llm_limit_blocks_over_limit(self):
        """Превышение лимита — блокировка."""
        for _ in range(10):
            check_llm_limit(12345)

        assert check_llm_limit(12345) is False

    def test_llm_limit_per_user(self):
        """Лимиты LLM независимы для разных пользователей."""
        for _ in range(10):
            check_llm_limit(111)

        # Пользователь 111 заблокирован
        assert check_llm_limit(111) is False
        # Пользователь 222 — нет
        assert check_llm_limit(222) is True

    def test_llm_limit_resets_after_window(self):
        """После истечения окна лимит сбрасывается."""
        for _ in range(10):
            check_llm_limit(12345)

        assert check_llm_limit(12345) is False

        # Сдвигаем время на 1 час вперёд
        with patch("bot.middlewares.throttle.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 3601
            assert check_llm_limit(12345) is True
