"""Базовый класс репозитория с доступом к Supabase клиенту."""

from __future__ import annotations

from typing import TYPE_CHECKING

from db.supabase import get_supabase

if TYPE_CHECKING:
    from supabase import AsyncClient


class BaseRepository:
    """Базовый репозиторий — предоставляет доступ к Supabase клиенту."""

    def __init__(self, client: AsyncClient | None = None) -> None:
        self._client = client

    async def _get_client(self) -> AsyncClient:
        """Получить Supabase клиент (lazy-инициализация через singleton)."""
        if self._client is None:
            self._client = await get_supabase()
        return self._client
