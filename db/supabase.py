"""Инициализация async Supabase клиента (singleton)."""

from supabase import AsyncClient, create_async_client

from bot.config import settings

_client: AsyncClient | None = None


async def get_supabase() -> AsyncClient:
    """Получить singleton-экземпляр async Supabase клиента."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = await create_async_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY,
        )
    return _client
