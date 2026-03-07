"""Middleware аутентификации — загрузка пользователя из БД по telegram_id."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update

from core.logging import get_logger
from repositories.user import UserRepository

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Загружает пользователя из Supabase и инжектит в data['user'].

    Если пользователь не найден — data['user'] = None.
    Хендлер сам решает, что делать с незарегистрированным пользователем.
    """

    def __init__(self, user_repo: UserRepository | None = None) -> None:
        self._user_repo = user_repo or UserRepository()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        telegram_id = _extract_telegram_id(event)
        if telegram_id is not None:
            user = await self._user_repo.get_by_telegram_id(telegram_id)
            data["user"] = user
        else:
            data["user"] = None

        return await handler(event, data)


def _extract_telegram_id(event: TelegramObject) -> int | None:
    """Извлечь telegram_id из события (Message, CallbackQuery и т.д.)."""
    if isinstance(event, Update):
        if event.message and event.message.from_user:
            return event.message.from_user.id
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user.id
        if event.inline_query and event.inline_query.from_user:
            return event.inline_query.from_user.id
        return None

    # Для прямых типов (Message, CallbackQuery) — берём from_user
    from_user = getattr(event, "from_user", None)
    if from_user is not None:
        return from_user.id
    return None
