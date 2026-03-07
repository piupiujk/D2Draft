"""Джоб: деактивация просроченных подписок."""

from __future__ import annotations

from core.logging import get_logger
from repositories.subscription import SubscriptionRepository
from repositories.user import UserRepository

logger = get_logger(__name__)


async def expire_subscriptions_job(
    *,
    sub_repo: SubscriptionRepository | None = None,
    user_repo: UserRepository | None = None,
) -> int:
    """Найти и деактивировать все подписки с истёкшим сроком действия.

    Для каждой просроченной подписки:
    1. Ставит статус cancelled в subscriptions.
    2. Сбрасывает is_premium и premium_expires_at в users.

    Returns:
        Количество деактивированных подписок.
    """
    if sub_repo is None:
        sub_repo = SubscriptionRepository()
    if user_repo is None:
        user_repo = UserRepository()

    expired = await sub_repo.get_expired_active()
    logger.info("Проверка подписок: найдено %d просроченных", len(expired))

    deactivated = 0
    for sub in expired:
        try:
            await sub_repo.deactivate(sub["id"])

            # Извлекаем telegram_id из join-а users
            users_data = sub.get("users")
            if isinstance(users_data, dict):
                telegram_id = users_data.get("telegram_id")
            else:
                telegram_id = None

            if telegram_id is not None:
                await user_repo.update(
                    telegram_id,
                    is_premium=False,
                    premium_expires_at=None,
                )

            deactivated += 1
            logger.info(
                "Подписка id=%s деактивирована (просрочена)", sub["id"],
            )
        except Exception:
            logger.exception(
                "Ошибка деактивации подписки id=%s", sub.get("id"),
            )

    logger.info("Деактивация подписок завершена: %d из %d", deactivated, len(expired))
    return deactivated
