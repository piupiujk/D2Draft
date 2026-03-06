"""Репозиторий пользователей — CRUD операции с таблицей users."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.exceptions import UserNotRegistered
from repositories.base import BaseRepository


class DuplicateUserError(Exception):
    """Пользователь с таким telegram_id или steam_id уже существует."""

    def __init__(self, field: str, value: Any) -> None:
        self.field = field
        self.value = value
        super().__init__(f"Пользователь с {field}={value} уже существует")


class UserRepository(BaseRepository):
    """CRUD-операции для таблицы users."""

    TABLE = "users"

    async def get_by_telegram_id(self, telegram_id: int) -> dict[str, Any] | None:
        """Получить пользователя по telegram_id. Возвращает None если не найден."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*")
            .eq("telegram_id", telegram_id)
            .maybe_single()
            .execute()
        )
        if response is None:
            return None
        return response.data

    async def get_by_steam_id(self, steam_id: str) -> dict[str, Any] | None:
        """Получить пользователя по steam_id. Возвращает None если не найден."""
        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .select("*")
            .eq("steam_id", steam_id)
            .maybe_single()
            .execute()
        )
        if response is None:
            return None
        return response.data

    async def create(
        self,
        telegram_id: int,
        steam_id: str | None = None,
        username: str | None = None,
        current_mmr: int | None = None,
        main_role: int | None = None,
    ) -> dict[str, Any]:
        """Создать нового пользователя. Возвращает созданную запись.

        Raises:
            DuplicateUserError: если telegram_id или steam_id уже заняты.
        """
        existing = await self.get_by_telegram_id(telegram_id)
        if existing is not None:
            raise DuplicateUserError("telegram_id", telegram_id)

        if steam_id is not None:
            existing_steam = await self.get_by_steam_id(steam_id)
            if existing_steam is not None:
                raise DuplicateUserError("steam_id", steam_id)

        data: dict[str, Any] = {"telegram_id": telegram_id}
        if steam_id is not None:
            data["steam_id"] = steam_id
        if username is not None:
            data["username"] = username
        if current_mmr is not None:
            data["current_mmr"] = current_mmr
            data["mmr_updated_at"] = datetime.now(timezone.utc).isoformat()
        if main_role is not None:
            data["main_role"] = main_role

        client = await self._get_client()
        response = await client.table(self.TABLE).insert(data).execute()
        return response.data[0]

    async def update(
        self, telegram_id: int, **fields: Any
    ) -> dict[str, Any]:
        """Обновить поля пользователя по telegram_id.

        Raises:
            UserNotRegistered: если пользователь не найден.
        """
        existing = await self.get_by_telegram_id(telegram_id)
        if existing is None:
            raise UserNotRegistered(telegram_id)

        client = await self._get_client()
        response = (
            await client.table(self.TABLE)
            .update(fields)
            .eq("telegram_id", telegram_id)
            .execute()
        )
        return response.data[0]

    async def update_mmr(self, telegram_id: int, new_mmr: int) -> dict[str, Any]:
        """Обновить MMR пользователя и зафиксировать время обновления.

        Raises:
            UserNotRegistered: если пользователь не найден.
        """
        return await self.update(
            telegram_id,
            current_mmr=new_mmr,
            mmr_updated_at=datetime.now(timezone.utc).isoformat(),
        )
