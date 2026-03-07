"""Репозиторий анализа матчей — операции с таблицей match_analyses."""

from __future__ import annotations

from typing import Any

from repositories.base import BaseRepository


class MatchAnalysisRepository(BaseRepository):
    """Операции с таблицей match_analyses."""

    TABLE = "match_analyses"

    async def insert(
        self,
        user_id: int,
        match_id: int,
        hero_id: int,
        role: int,
        result: str,
        duration_sec: int,
        stats: dict[str, Any] | None = None,
        llm_summary: str | None = None,
    ) -> dict[str, Any]:
        """Вставить запись анализа матча."""
        data: dict[str, Any] = {
            "user_id": user_id,
            "match_id": match_id,
            "hero_id": hero_id,
            "role": role,
            "result": result,
            "duration_sec": duration_sec,
            "stats": stats or {},
        }
        if llm_summary is not None:
            data["llm_summary"] = llm_summary

        client = await self._get_client()
        response = await client.table(self.TABLE).insert(data).execute()
        return response.data[0]

    async def get_by_match_id(
        self, user_id: int, match_id: int
    ) -> dict[str, Any] | None:
        """Получить анализ матча по match_id для конкретного пользователя."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .eq("match_id", match_id)
            .maybe_single()
            .execute()
        )
        if response is None:
            return None
        return response.data

    async def update_llm_summary(
        self, user_id: int, match_id: int, llm_summary: str
    ) -> dict[str, Any] | None:
        """Сохранить LLM-совет в существующую запись анализа матча."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .update({"llm_summary": llm_summary})
            .eq("user_id", user_id)
            .eq("match_id", match_id)
            .execute()
        )
        if response.data:
            return response.data[0]
        return None

    async def get_latest(
        self, user_id: int, limit: int = 1
    ) -> list[dict[str, Any]]:
        """Получить последние анализы матчей пользователя."""
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
