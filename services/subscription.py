"""Сервис подписок — активация, проверка и деактивация Premium."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.logging import get_logger
from repositories.subscription import SubscriptionRepository
from repositories.user import UserRepository

logger = get_logger(__name__)


async def activate_premium(
    user_id: int,
    telegram_id: int,
    duration_days: int,
    plan: str = "premium",
    *,
    sub_repo: SubscriptionRepository | None = None,
    user_repo: UserRepository | None = None,
) -> dict:
    """Активировать Premium-подписку для пользователя.

    Создаёт запись в subscriptions и обновляет флаги в users.

    Args:
        user_id: ID пользователя в БД (users.id).
        telegram_id: Telegram ID пользователя (для обновления users).
        duration_days: Длительность подписки в днях.
        plan: Тарифный план (по умолчанию 'premium').
        sub_repo: Репозиторий подписок (DI).
        user_repo: Репозиторий пользователей (DI).

    Returns:
        Созданная запись подписки.
    """
    if sub_repo is None:
        sub_repo = SubscriptionRepository()
    if user_repo is None:
        user_repo = UserRepository()

    expires_at = datetime.now(timezone.utc) + timedelta(days=duration_days)

    subscription = await sub_repo.create(
        user_id=user_id,
        plan=plan,
        expires_at=expires_at.isoformat(),
    )

    await user_repo.update(
        telegram_id,
        is_premium=True,
        premium_expires_at=expires_at.isoformat(),
    )

    logger.info("Premium активирован: user_id=%s, план=%s, дней=%d", user_id, plan, duration_days)
    return subscription


async def check_premium(
    user_id: int,
    *,
    sub_repo: SubscriptionRepository | None = None,
) -> bool:
    """Проверить, есть ли у пользователя активная подписка.

    Args:
        user_id: ID пользователя в БД (users.id).
        sub_repo: Репозиторий подписок (DI).

    Returns:
        True если есть активная непросроченная подписка.
    """
    if sub_repo is None:
        sub_repo = SubscriptionRepository()

    active = await sub_repo.get_active(user_id)
    if active is None:
        return False

    expires_at = active.get("expires_at")
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


async def deactivate(
    subscription_id: int,
    telegram_id: int,
    *,
    sub_repo: SubscriptionRepository | None = None,
    user_repo: UserRepository | None = None,
) -> dict:
    """Деактивировать подписку и сбросить Premium-статус пользователя.

    Args:
        subscription_id: ID подписки для деактивации.
        telegram_id: Telegram ID пользователя.
        sub_repo: Репозиторий подписок (DI).
        user_repo: Репозиторий пользователей (DI).

    Returns:
        Обновлённая запись подписки.
    """
    if sub_repo is None:
        sub_repo = SubscriptionRepository()
    if user_repo is None:
        user_repo = UserRepository()

    result = await sub_repo.deactivate(subscription_id)

    await user_repo.update(
        telegram_id,
        is_premium=False,
        premium_expires_at=None,
    )

    return result
