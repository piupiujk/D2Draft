"""Middleware троттлинга — раздельный rate limit по telegram_id (in-memory dict с TTL).

Лимиты:
- Текстовые сообщения: 30 в минуту
- Изображения: 5 в минуту
- LLM-запросы (premium): 10 в час
"""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import ContentType, TelegramObject, Update

from core.logging import get_logger

logger = get_logger(__name__)

# Лимиты по умолчанию
DEFAULT_MESSAGE_LIMIT = 30  # текстовых сообщений в минуту
DEFAULT_MESSAGE_WINDOW = 60  # окно в секундах

DEFAULT_IMAGE_LIMIT = 5  # изображений в минуту
DEFAULT_IMAGE_WINDOW = 60

DEFAULT_LLM_LIMIT = 10  # LLM-запросов в час (premium)
DEFAULT_LLM_WINDOW = 3600


class _RateBucket:
    """Хранит временные метки запросов и проверяет лимит."""

    __slots__ = ("_limit", "_window", "_requests")

    def __init__(self, limit: int, window: int) -> None:
        self._limit = limit
        self._window = window
        self._requests: dict[int, list[float]] = {}

    def is_exceeded(self, user_id: int, now: float) -> bool:
        """Проверить, превышен ли лимит для пользователя."""
        self._cleanup(user_id, now)
        timestamps = self._requests.get(user_id, [])
        return len(timestamps) >= self._limit

    def record(self, user_id: int, now: float) -> None:
        """Зафиксировать запрос."""
        self._requests.setdefault(user_id, []).append(now)

    def _cleanup(self, user_id: int, now: float) -> None:
        timestamps = self._requests.get(user_id)
        if timestamps is None:
            return
        cutoff = now - self._window
        self._requests[user_id] = [t for t in timestamps if t > cutoff]


class ThrottleMiddleware(BaseMiddleware):
    """In-memory rate limiter по telegram_id с раздельными лимитами.

    - Текстовые сообщения: message_limit / message_window
    - Изображения (фото): image_limit / image_window
    - При превышении — хендлер НЕ вызывается, пользователю отправляется предупреждение.
    """

    def __init__(
        self,
        rate_limit: int | None = None,
        window_sec: int | None = None,
        message_limit: int = DEFAULT_MESSAGE_LIMIT,
        message_window: int = DEFAULT_MESSAGE_WINDOW,
        image_limit: int = DEFAULT_IMAGE_LIMIT,
        image_window: int = DEFAULT_IMAGE_WINDOW,
    ) -> None:
        # Обратная совместимость: если переданы rate_limit/window_sec — используем их
        if rate_limit is not None:
            message_limit = rate_limit
        if window_sec is not None:
            message_window = window_sec

        self._message_bucket = _RateBucket(message_limit, message_window)
        self._image_bucket = _RateBucket(image_limit, image_window)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_id = _extract_telegram_id(event)
        if telegram_id is None:
            return await handler(event, data)

        now = time.monotonic()
        is_image = _is_image_message(event)
        bucket = self._image_bucket if is_image else self._message_bucket

        if bucket.is_exceeded(telegram_id, now):
            logger.info(
                "Throttle: user=%s, тип=%s", telegram_id, "image" if is_image else "text"
            )
            await _send_throttle_warning(event, is_image=is_image)
            return None

        bucket.record(telegram_id, now)
        return await handler(event, data)


# --- Глобальный LLM rate limiter ---

_llm_bucket = _RateBucket(DEFAULT_LLM_LIMIT, DEFAULT_LLM_WINDOW)


def check_llm_limit(telegram_id: int) -> bool:
    """Проверить и зафиксировать LLM-запрос для пользователя.

    Возвращает True, если запрос разрешён, False — если лимит исчерпан.
    """
    now = time.monotonic()
    if _llm_bucket.is_exceeded(telegram_id, now):
        return False
    _llm_bucket.record(telegram_id, now)
    return True


def _is_image_message(event: TelegramObject) -> bool:
    """Определить, является ли событие отправкой изображения."""
    if isinstance(event, Update):
        msg = event.message
        if msg is not None and msg.content_type == ContentType.PHOTO:
            return True
        return False

    content_type = getattr(event, "content_type", None)
    return content_type == ContentType.PHOTO


def _extract_telegram_id(event: TelegramObject) -> int | None:
    """Извлечь telegram_id из события."""
    if isinstance(event, Update):
        if event.message and event.message.from_user:
            return event.message.from_user.id
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user.id
        return None

    from_user = getattr(event, "from_user", None)
    if from_user is not None:
        return from_user.id
    return None


async def _send_throttle_warning(
    event: TelegramObject, *, is_image: bool = False
) -> None:
    """Отправить пользователю предупреждение о превышении лимита."""
    if is_image:
        text = "⏳ Слишком много изображений, подождите немного."
    else:
        text = "⏳ Слишком много запросов, подождите немного."

    message = None

    if isinstance(event, Update):
        message = event.message
    elif hasattr(event, "answer"):
        try:
            await event.answer(text)
        except Exception:
            pass
        return
    elif hasattr(event, "reply"):
        message = event

    if message is not None:
        try:
            await message.answer(text)
        except Exception:
            pass
