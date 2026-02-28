"""Middleware троттлинга — rate limit по telegram_id (in-memory dict с TTL)."""

from __future__ import annotations

import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

# Лимиты по умолчанию
DEFAULT_RATE_LIMIT = 30  # сообщений в минуту
DEFAULT_WINDOW_SEC = 60  # окно в секундах


class ThrottleMiddleware(BaseMiddleware):
    """In-memory rate limiter по telegram_id.

    Хранит dict {telegram_id: [timestamps]} и отклоняет запросы,
    превышающие лимит в заданном окне. При превышении — data['throttled'] = True,
    и хендлер НЕ вызывается (бот отвечает предупреждением).
    """

    def __init__(
        self,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_sec: int = DEFAULT_WINDOW_SEC,
    ) -> None:
        self._rate_limit = rate_limit
        self._window_sec = window_sec
        self._requests: dict[int, list[float]] = {}

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
        self._cleanup(telegram_id, now)

        timestamps = self._requests.setdefault(telegram_id, [])
        if len(timestamps) >= self._rate_limit:
            # Превышен лимит — отправляем предупреждение
            await _send_throttle_warning(event)
            return None

        timestamps.append(now)
        return await handler(event, data)

    def _cleanup(self, telegram_id: int, now: float) -> None:
        """Удалить устаревшие записи за пределами окна."""
        timestamps = self._requests.get(telegram_id)
        if timestamps is None:
            return
        cutoff = now - self._window_sec
        self._requests[telegram_id] = [t for t in timestamps if t > cutoff]


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


async def _send_throttle_warning(event: TelegramObject) -> None:
    """Отправить пользователю предупреждение о превышении лимита."""
    message = None

    if isinstance(event, Update):
        message = event.message
    elif hasattr(event, "answer"):
        # CallbackQuery
        try:
            await event.answer("⏳ Слишком много запросов, подождите немного.")
        except Exception:
            pass
        return
    elif hasattr(event, "reply"):
        message = event

    if message is not None:
        try:
            await message.answer("⏳ Слишком много запросов, подождите немного.")
        except Exception:
            pass
