"""Тесты для универсального in-memory кэша с TTL (core/cache.py)."""

from __future__ import annotations

from core.cache import (
    TTLCache,
    build_cache,
    invalidate_all_caches,
    meta_cache,
    profile_cache,
)

# ---------------------------------------------------------------------------
# TTLCache — базовая функциональность
# ---------------------------------------------------------------------------


class TestTTLCacheBasic:
    """Базовые операции get/set/invalidate."""

    def test_set_and_get(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_missing_key(self):
        cache = TTLCache(default_ttl=60)
        assert cache.get("nonexistent") is None

    def test_invalidate_key(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "value1")
        cache.invalidate("key1")
        assert cache.get("key1") is None

    def test_invalidate_missing_key_no_error(self):
        cache = TTLCache(default_ttl=60)
        cache.invalidate("nonexistent")  # Не должно бросать исключение

    def test_invalidate_all(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")
        assert len(cache) == 3
        cache.invalidate_all()
        assert len(cache) == 0

    def test_len(self):
        cache = TTLCache(default_ttl=60)
        assert len(cache) == 0
        cache.set("a", 1)
        cache.set("b", 2)
        assert len(cache) == 2

    def test_contains(self):
        cache = TTLCache(default_ttl=60)
        cache.set("exists", True)
        assert "exists" in cache
        assert "missing" not in cache

    def test_overwrite_value(self):
        cache = TTLCache(default_ttl=60)
        cache.set("key", "old")
        cache.set("key", "new")
        assert cache.get("key") == "new"


# ---------------------------------------------------------------------------
# TTLCache — TTL (время жизни)
# ---------------------------------------------------------------------------


class TestTTLCacheExpiry:
    """Проверка истечения TTL."""

    def test_expired_entry_returns_none(self):
        cache = TTLCache(default_ttl=1)  # 1 секунда
        cache.set("key", "value")

        # Подменяем время на будущее
        original_ts = cache._store["key"][0]
        cache._store["key"] = (original_ts - 2, "value")  # Сдвигаем на 2 секунды назад

        assert cache.get("key") is None

    def test_expired_entry_removed_from_store(self):
        cache = TTLCache(default_ttl=1)
        cache.set("key", "value")

        original_ts = cache._store["key"][0]
        cache._store["key"] = (original_ts - 2, "value")

        cache.get("key")  # Должен удалить запись
        assert "key" not in cache._store

    def test_not_expired_entry_returns_value(self):
        cache = TTLCache(default_ttl=3600)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_contains_respects_ttl(self):
        cache = TTLCache(default_ttl=1)
        cache.set("key", "value")

        original_ts = cache._store["key"][0]
        cache._store["key"] = (original_ts - 2, "value")

        assert "key" not in cache


# ---------------------------------------------------------------------------
# TTLCache — различные типы данных
# ---------------------------------------------------------------------------


class TestTTLCacheDataTypes:
    """Кэш работает с разными типами данных."""

    def test_cache_list(self):
        cache = TTLCache(default_ttl=60)
        data = [1, 2, 3, 4, 5]
        cache.set("list", data)
        assert cache.get("list") == data

    def test_cache_dict(self):
        cache = TTLCache(default_ttl=60)
        data = {"hero_id": 1, "winrate": 0.55}
        cache.set("dict", data)
        assert cache.get("dict") == data

    def test_cache_none_value(self):
        cache = TTLCache(default_ttl=60)
        cache.set("none_val", None)
        # None — допустимое значение, но get() возвращает None и для отсутствующих ключей
        # Поэтому None-значения не кэшируются корректно (by design)
        result = cache.get("none_val")
        assert result is None


# ---------------------------------------------------------------------------
# Глобальные экземпляры кэша
# ---------------------------------------------------------------------------


class TestGlobalCaches:
    """Проверка глобальных экземпляров кэша."""

    def test_meta_cache_ttl(self):
        assert meta_cache._default_ttl == 3600  # 1 час

    def test_build_cache_ttl(self):
        assert build_cache._default_ttl == 3600  # 1 час

    def test_profile_cache_ttl(self):
        assert profile_cache._default_ttl == 600  # 10 минут

    def test_invalidate_all_caches(self):
        meta_cache.set("test_meta", "data")
        build_cache.set("test_build", "data")
        profile_cache.set("test_profile", "data")

        invalidate_all_caches()

        assert meta_cache.get("test_meta") is None
        assert build_cache.get("test_build") is None
        assert profile_cache.get("test_profile") is None

    def test_caches_are_independent(self):
        meta_cache.set("key", "meta_value")
        build_cache.set("key", "build_value")

        assert meta_cache.get("key") == "meta_value"
        assert build_cache.get("key") == "build_value"

        meta_cache.invalidate_all()
        assert meta_cache.get("key") is None
        assert build_cache.get("key") == "build_value"

        build_cache.invalidate_all()


# ---------------------------------------------------------------------------
# Интеграция: кэш в services/meta.py
# ---------------------------------------------------------------------------


class TestMetaCacheIntegration:
    """Проверка что services/meta.py использует core.cache.meta_cache."""

    def test_invalidate_meta_cache_clears_meta_cache(self):
        from services.meta import invalidate_meta_cache

        meta_cache.set("test_key", [])
        assert len(meta_cache) > 0
        invalidate_meta_cache()
        assert len(meta_cache) == 0

    def test_meta_cache_ref_matches(self):
        """_cache в services/meta.py ссылается на хранилище meta_cache."""
        from services.meta import _cache

        assert _cache is meta_cache._store


# ---------------------------------------------------------------------------
# Интеграция: кэш в services/build.py
# ---------------------------------------------------------------------------


class TestBuildCacheIntegration:
    """Проверка что services/build.py использует core.cache.build_cache."""

    def test_invalidate_build_cache_clears_build_cache(self):
        from services.build import invalidate_build_cache

        build_cache.set("test_key", object())
        assert len(build_cache) > 0
        invalidate_build_cache()
        assert len(build_cache) == 0

    def test_build_cache_ref_matches(self):
        """_cache в services/build.py ссылается на хранилище build_cache."""
        from services.build import _cache

        assert _cache is build_cache._store
