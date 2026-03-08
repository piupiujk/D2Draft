"""Универсальный in-memory кэш с TTL.

Поддерживает различные TTL для разных типов данных,
автоматическую очистку устаревших записей и сброс при смене патча.
"""

from __future__ import annotations

import time
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class TTLCache:
    """In-memory кэш с TTL для отдельных записей.

    Потокобезопасен в asyncio-контексте (один event loop).
    """

    def __init__(self, default_ttl: int = 3600) -> None:
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> Any | None:
        """Получить значение из кэша. Возвращает None если ключ отсутствует или истёк."""
        entry = self._store.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._default_ttl:
            del self._store[key]
            return None
        return data

    def set(self, key: str, value: Any) -> None:
        """Сохранить значение в кэш с текущим TTL."""
        self._store[key] = (time.monotonic(), value)

    def invalidate(self, key: str) -> None:
        """Удалить конкретный ключ из кэша."""
        self._store.pop(key, None)

    def invalidate_all(self) -> None:
        """Сбросить все данные кэша."""
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None


# ---------------------------------------------------------------------------
# Глобальные экземпляры кэша с разными TTL
# ---------------------------------------------------------------------------

# Мета-герои: TTL 1 час
meta_cache = TTLCache(default_ttl=3600)

# Билды героев: TTL 1 час
build_cache = TTLCache(default_ttl=3600)

# Профиль OpenDota: TTL 10 минут
profile_cache = TTLCache(default_ttl=600)


def invalidate_all_caches() -> None:
    """Сбросить все глобальные кэши. Вызывается при обнаружении нового патча."""
    meta_cache.invalidate_all()
    build_cache.invalidate_all()
    profile_cache.invalidate_all()
    logger.info("Все кэши сброшены")
