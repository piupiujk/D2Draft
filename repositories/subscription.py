"""Репозиторий подписок — операции с таблицей subscriptions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository):
    """Операции с таблицей subscriptions."""

    TABLE = "subscriptions"

    async def create(
        self,
        user_id: int,
        plan: str = "premium",
        expires_at: str | None = None,
    ) -> dict[str, Any]:
        """Создать новую подписку."""
        data: dict[str, Any] = {
            "user_id": user_id,
            "plan": plan,
            "status": "active",
        }
        if expires_at is not None:
            data["expires_at"] = expires_at

        client = await self._get_client()
        response = await client.table(self.TABLE).insert(data).execute()
        return response.data[0]

    async def get_active(self, user_id: int) -> dict[str, Any] | None:
        """Получить активную подписку пользователя. Возвращает None если нет."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "active")
            .order("created_at", desc=True)
            .maybe_single()
            .execute()
        )
        if response is None:
            return None
        return response.data

    async def deactivate(self, subscription_id: int) -> dict[str, Any]:
        """Деактивировать подписку (статус -> cancelled)."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .update({
                "status": "cancelled",
                "cancelled_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", subscription_id)
            .execute()
        )
        return response.data[0]

    async def get_expired_active(self) -> list[dict[str, Any]]:
        """Получить активные подписки с истёкшим сроком действия."""
        now = datetime.now(timezone.utc).isoformat()
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*, users!inner(telegram_id)")
            .eq("status", "active")
            .lt("expires_at", now)
            .execute()
        )
        return response.data
