"""Общие фикстуры для тестов D2Draft.

Мокаем supabase и bot.config до импорта любых модулей проекта,
чтобы тесты не требовали реальных подключений к БД.
"""

import json
import sys
from datetime import datetime, timezone
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Мок supabase модуля (до импорта кода проекта)
# ---------------------------------------------------------------------------

if "supabase" not in sys.modules:
    _mock_supabase = ModuleType("supabase")
    _mock_supabase.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    _mock_supabase.create_async_client = AsyncMock()  # type: ignore[attr-defined]
    sys.modules["supabase"] = _mock_supabase

if "bot.config" not in sys.modules:
    _mock_config = ModuleType("bot.config")
    _settings = MagicMock()
    _settings.SUPABASE_URL = "https://test.supabase.co"
    _settings.SUPABASE_KEY = "test-key"
    _settings.STRATZ_TOKEN = "test-stratz-token"
    _settings.STEAM_API_KEY = "test-steam-key"
    _settings.LLM_API_KEY = "test-llm-key"
    _settings.LLM_PROVIDER = "openai"
    _settings.OPENDOTA_BASE_URL = "https://api.opendota.com/api"
    _settings.BOT_TOKEN = "123456:ABC-DEF"
    _settings.REDIS_URL = ""
    _mock_config.settings = _settings  # type: ignore[attr-defined]
    sys.modules["bot.config"] = _mock_config


# ---------------------------------------------------------------------------
# Фикстуры API-клиентов
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_opendota():
    """Мок OpenDotaClient с базовыми методами."""
    from clients.opendota import PlayerProfile

    mock = AsyncMock()
    mock.get_player = AsyncMock(
        return_value=PlayerProfile(
            account_id=12345678,
            steam_id="76561198012345678",
            personaname="TestPlayer",
            avatar="https://example.com/avatar.jpg",
            rank_tier=62,
        )
    )
    mock.get_recent_matches = AsyncMock(return_value=[])
    mock.get_player_heroes = AsyncMock(return_value=[])
    mock.get_match = AsyncMock(return_value=None)
    mock.close = AsyncMock()
    return mock


@pytest.fixture()
def mock_stratz():
    """Мок StratzClient с базовыми методами."""
    from clients.stratz import MetaHeroStats

    mock = MagicMock()
    mock.get_meta_heroes = AsyncMock(
        return_value=[
            MetaHeroStats(hero_id=1, match_count=5000, win_count=2800),
            MetaHeroStats(hero_id=2, match_count=4000, win_count=2000),
        ]
    )
    mock.get_hero_build = AsyncMock()
    mock.get_hero_matchups = AsyncMock()
    mock.get_hero_guide = AsyncMock()
    mock.close = AsyncMock()
    return mock


@pytest.fixture()
def mock_llm():
    """Мок LLMClient с базовыми методами."""
    mock = AsyncMock()
    mock.recognize_draft = AsyncMock(return_value={
        "allies": [1, 2, 3],
        "enemies": [4, 5],
        "confidence": 0.9,
    })
    mock.summarize_match = AsyncMock(return_value="Тестовый совет по матчу.")
    mock.recommend_picks = AsyncMock(return_value=[])
    mock.close = AsyncMock()
    return mock


@pytest.fixture()
def test_user():
    """Тестовый пользователь (dict в формате Supabase row)."""
    return {
        "id": 1,
        "telegram_id": 999888777,
        "steam_id": "76561198012345678",
        "username": "TestPlayer",
        "current_mmr": 4500,
        "mmr_updated_at": datetime.now(tz=timezone.utc).isoformat(),
        "main_role": 1,
        "is_premium": False,
        "premium_expires_at": None,
        "notifications_enabled": True,
        "weekly_report_day": 1,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture()
def test_premium_user(test_user):
    """Тестовый Premium-пользователь."""
    return {
        **test_user,
        "is_premium": True,
        "premium_expires_at": "2099-12-31T23:59:59+00:00",
    }


@pytest.fixture()
def mock_supabase_table():
    """Мок таблицы Supabase с цепочкой select/insert/update/delete."""
    table = MagicMock()

    # Настраиваем цепочку вызовов для select
    select_chain = MagicMock()
    select_chain.eq = MagicMock(return_value=select_chain)
    select_chain.limit = MagicMock(return_value=select_chain)
    select_chain.order = MagicMock(return_value=select_chain)
    select_chain.gte = MagicMock(return_value=select_chain)
    execute_result = MagicMock()
    execute_result.data = []
    select_chain.execute = AsyncMock(return_value=execute_result)
    table.select = MagicMock(return_value=select_chain)

    # Настраиваем insert
    insert_chain = MagicMock()
    insert_result = MagicMock()
    insert_result.data = [{}]
    insert_chain.execute = AsyncMock(return_value=insert_result)
    table.insert = MagicMock(return_value=insert_chain)

    # Настраиваем update
    update_chain = MagicMock()
    update_chain.eq = MagicMock(return_value=update_chain)
    update_result = MagicMock()
    update_result.data = [{}]
    update_chain.execute = AsyncMock(return_value=update_result)
    table.update = MagicMock(return_value=update_chain)

    return table


# ---------------------------------------------------------------------------
# Хелпер для создания мок-ответов _sync_query (Stratz cloudscraper)
# ---------------------------------------------------------------------------


def stratz_sync_response(data: object, status_code: int = 200) -> dict:
    """Создать ответ в формате StratzClient._sync_query."""
    return {
        "status_code": status_code,
        "body": json.dumps(data),
        "headers": {"content-type": "application/json"},
    }
