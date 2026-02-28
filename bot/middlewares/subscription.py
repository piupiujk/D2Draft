"""Middleware проверки подписки — определяет is_premium статус пользователя."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class SubscriptionMiddleware(BaseMiddleware):
    """Проверяет is_premium и premium_expires_at, инжектит data['is_premium'].

    Зависит от AuthMiddleware — ожидает data['user'] в данных.
    Если пользователь не найден или подписка истекла — data['is_premium'] = False.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("user")
        data["is_premium"] = _check_premium(user)
        return await handler(event, data)


def _check_premium(user: dict[str, Any] | None) -> bool:
    """Проверить, активна ли premium-подписка пользователя."""
    if user is None:
        return False

    if not user.get("is_premium"):
        return False

    expires_at = user.get("premium_expires_at")
    if expires_at is None:
        return True

    if isinstance(expires_at, str):
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except ValueError:
            return False
    elif isinstance(expires_at, datetime):
        expires_dt = expires_at
    else:
        return False

    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=timezone.utc)

    return expires_dt > datetime.now(timezone.utc)
