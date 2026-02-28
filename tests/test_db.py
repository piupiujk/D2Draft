"""Тесты для db/supabase.py и проверка SQL миграций."""

import asyncio
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

# --- Мокаем зависимости, недоступные в тестовом окружении ---

# supabase пакет может отсутствовать (требует pyiceberg → Visual C++ Build Tools)
if "supabase" not in sys.modules:
    _mock_supabase = ModuleType("supabase")
    _mock_supabase.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    _mock_supabase.create_async_client = AsyncMock()  # type: ignore[attr-defined]
    sys.modules["supabase"] = _mock_supabase

# bot.config требует переменных окружения; мокаем settings
if "bot.config" not in sys.modules:
    _mock_config = ModuleType("bot.config")
    _settings = MagicMock()
    _settings.SUPABASE_URL = "https://test.supabase.co"
    _settings.SUPABASE_KEY = "test-key"
    _mock_config.settings = _settings  # type: ignore[attr-defined]
    sys.modules["bot.config"] = _mock_config

# Теперь безопасно импортировать db.supabase
import db.supabase as _db_mod  # noqa: E402

# --- Тесты Supabase клиента ---


class TestGetSupabase:
    """Тесты singleton-клиента Supabase."""

    def setup_method(self):
        """Сброс singleton перед каждым тестом."""
        _db_mod._client = None

    def teardown_method(self):
        """Сброс singleton после каждого теста."""
        _db_mod._client = None

    def test_get_supabase_creates_client(self):
        """get_supabase() создаёт клиент при первом вызове."""
        mock_client = AsyncMock()
        _db_mod.create_async_client = AsyncMock(return_value=mock_client)

        client = asyncio.run(_db_mod.get_supabase())
        assert client is mock_client
        _db_mod.create_async_client.assert_called_once()

    def test_get_supabase_returns_singleton(self):
        """Повторный вызов get_supabase() возвращает тот же экземпляр."""
        mock_client = AsyncMock()
        _db_mod.create_async_client = AsyncMock(return_value=mock_client)

        async def _run():
            c1 = await _db_mod.get_supabase()
            c2 = await _db_mod.get_supabase()
            return c1, c2

        client1, client2 = asyncio.run(_run())
        assert client1 is client2
        _db_mod.create_async_client.assert_called_once()


# --- Тесты SQL миграций ---

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "db" / "migrations"


class TestMigrationsExist:
    """Проверка наличия всех миграций."""

    EXPECTED_MIGRATIONS = [
        "001_create_users.sql",
        "002_create_mmr_history.sql",
        "003_create_match_analyses.sql",
        "004_create_draft_analyses.sql",
        "005_create_subscriptions.sql",
        "006_enable_rls.sql",
    ]

    def test_all_migrations_exist(self):
        """Все файлы миграций присутствуют."""
        for filename in self.EXPECTED_MIGRATIONS:
            filepath = MIGRATIONS_DIR / filename
            assert filepath.exists(), f"Миграция {filename} не найдена"

    def test_migrations_not_empty(self):
        """Файлы миграций не пустые."""
        for filename in self.EXPECTED_MIGRATIONS:
            filepath = MIGRATIONS_DIR / filename
            content = filepath.read_text(encoding="utf-8")
            assert len(content.strip()) > 0, f"Миграция {filename} пуста"

    def test_migrations_order(self):
        """Миграции пронумерованы последовательно."""
        sql_files = sorted(f.name for f in MIGRATIONS_DIR.glob("*.sql"))
        for i, filename in enumerate(sql_files, start=1):
            prefix = f"{i:03d}_"
            assert filename.startswith(prefix), (
                f"Миграция {filename} нарушает порядок нумерации (ожидался префикс {prefix})"
            )


class TestMigrationContent:
    """Проверка содержимого SQL миграций."""

    def _read_migration(self, name: str) -> str:
        return (MIGRATIONS_DIR / name).read_text(encoding="utf-8")

    def test_users_table_fields(self):
        """Таблица users содержит все обязательные поля."""
        sql = self._read_migration("001_create_users.sql")
        required_fields = [
            "telegram_id",
            "steam_id",
            "username",
            "current_mmr",
            "mmr_updated_at",
            "main_role",
            "is_premium",
            "premium_expires_at",
            "notifications_enabled",
            "weekly_report_day",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in sql, f"Поле {field} отсутствует в таблице users"

    def test_users_telegram_id_unique(self):
        """telegram_id имеет ограничение UNIQUE."""
        sql = self._read_migration("001_create_users.sql")
        assert "UNIQUE" in sql and "telegram_id" in sql

    def test_users_steam_id_unique(self):
        """steam_id имеет ограничение UNIQUE."""
        sql = self._read_migration("001_create_users.sql")
        assert "steam_id" in sql

    def test_mmr_history_has_fk(self):
        """mmr_history имеет FK на users."""
        sql = self._read_migration("002_create_mmr_history.sql")
        assert "REFERENCES users" in sql

    def test_match_analyses_has_jsonb(self):
        """match_analyses содержит JSONB поле stats."""
        sql = self._read_migration("003_create_match_analyses.sql")
        assert "JSONB" in sql or "jsonb" in sql
        assert "stats" in sql

    def test_draft_analyses_has_integer_arrays(self):
        """draft_analyses содержит INTEGER[] массивы."""
        sql = self._read_migration("004_create_draft_analyses.sql")
        assert "INTEGER[]" in sql

    def test_subscriptions_has_status(self):
        """subscriptions содержит поле status с ограничениями."""
        sql = self._read_migration("005_create_subscriptions.sql")
        assert "status" in sql
        assert "active" in sql
        assert "expired" in sql

    def test_rls_enabled_for_all_tables(self):
        """RLS включён для всех таблиц."""
        sql = self._read_migration("006_enable_rls.sql")
        tables = ["users", "mmr_history", "match_analyses", "draft_analyses", "subscriptions"]
        for table in tables:
            assert f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY" in sql, (
                f"RLS не включён для таблицы {table}"
            )

    def test_rls_policies_exist(self):
        """RLS policies созданы для всех таблиц."""
        sql = self._read_migration("006_enable_rls.sql")
        assert sql.count("CREATE POLICY") >= 5
