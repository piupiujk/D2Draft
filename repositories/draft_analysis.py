"""Репозиторий анализа драфтов — операции с таблицей draft_analyses."""

from __future__ import annotations

from typing import Any

from repositories.base import BaseRepository


class DraftAnalysisRepository(BaseRepository):
    """Операции с таблицей draft_analyses."""

    TABLE = "draft_analyses"

    async def insert(
        self,
        user_id: int,
        ally_hero_ids: list[int],
        enemy_hero_ids: list[int],
        recommended_ids: list[int] | None = None,
        user_role: int | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """Вставить запись анализа драфта."""
        data: dict[str, Any] = {
            "user_id": user_id,
            "ally_hero_ids": ally_hero_ids,
            "enemy_hero_ids": enemy_hero_ids,
            "recommended_ids": recommended_ids or [],
        }
        if user_role is not None:
            data["user_role"] = user_role
        if confidence is not None:
            data["confidence"] = confidence

        client = await self._get_client()
        response = await client.table(self.TABLE).insert(data).execute()
        return response.data[0]

    async def get_latest(
        self, user_id: int, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Получить последние анализы драфтов пользователя."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data
