"""Репозиторий истории MMR — операции с таблицей mmr_history."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from repositories.base import BaseRepository


class MmrHistoryRepository(BaseRepository):
    """Операции с таблицей mmr_history."""

    TABLE = "mmr_history"

    async def insert(self, user_id: int, mmr: int) -> dict[str, Any]:
        """Добавить запись в историю MMR."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .insert({"user_id": user_id, "mmr": mmr})
            .execute()
        )
        return response.data[0]

    async def get_history(
        self, user_id: int, days: int = 30
    ) -> list[dict[str, Any]]:
        """Получить историю MMR за последние N дней.

        Возвращает записи отсортированные по дате (от новых к старым).
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .gte("recorded_at", since)
            .order("recorded_at", desc=True)
            .execute()
        )
        return response.data
