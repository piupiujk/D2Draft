"""Тесты для repositories/mmr_history.py, match_analysis.py, draft_analysis.py, subscription.py."""

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

# --- Мокаем зависимости ---

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
    _mock_config.settings = _settings  # type: ignore[attr-defined]
    sys.modules["bot.config"] = _mock_config

from repositories.draft_analysis import DraftAnalysisRepository  # noqa: E402  # isort: skip
from repositories.match_analysis import MatchAnalysisRepository  # noqa: E402
from repositories.mmr_history import MmrHistoryRepository  # noqa: E402
from repositories.subscription import SubscriptionRepository  # noqa: E402

# --- Хелперы ---


def _mock_insert(client, table_name, returned_row):
    """Настроить мок для insert().execute()."""
    table_mock = MagicMock()
    insert_mock = MagicMock()
    response = MagicMock()
    response.data = [returned_row]
    insert_mock.execute = AsyncMock(return_value=response)
    table_mock.insert.return_value = insert_mock
    client.table.return_value = table_mock
    return table_mock


def _mock_select_list(client, table_name, rows):
    """Настроить мок для select().eq()...order().execute() -> список."""
    table_mock = MagicMock()
    response = MagicMock()
    response.data = rows

    # Цепочка: select -> eq -> gte/order/limit (всё возвращает себя)
    chain = MagicMock()
    chain.execute = AsyncMock(return_value=response)
    chain.eq.return_value = chain
    chain.gte.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.maybe_single.return_value = chain
    table_mock.select.return_value = chain

    client.table.return_value = table_mock
    return table_mock


def _mock_select_single(client, table_name, row):
    """Настроить мок для select().eq().maybe_single().execute() -> одна запись."""
    table_mock = MagicMock()
    response = MagicMock()
    response.data = row

    chain = MagicMock()
    chain.execute = AsyncMock(return_value=response)
    chain.eq.return_value = chain
    chain.order.return_value = chain
    chain.maybe_single.return_value = chain
    table_mock.select.return_value = chain

    client.table.return_value = table_mock
    return table_mock


def _mock_update(client, table_name, returned_row):
    """Настроить мок для update().eq().execute()."""
    table_mock = MagicMock()
    update_mock = MagicMock()
    eq_mock = MagicMock()
    response = MagicMock()
    response.data = [returned_row]
    eq_mock.execute = AsyncMock(return_value=response)
    update_mock.eq.return_value = eq_mock
    table_mock.update.return_value = update_mock
    client.table.return_value = table_mock
    return table_mock


# --- Тестовые данные ---

SAMPLE_MMR_RECORD = {
    "id": 1,
    "user_id": 42,
    "mmr": 3500,
    "recorded_at": "2026-02-28T12:00:00+00:00",
}

SAMPLE_MATCH_ANALYSIS = {
    "id": 1,
    "user_id": 42,
    "match_id": 7000000001,
    "hero_id": 1,
    "role": 1,
    "result": "win",
    "duration_sec": 2400,
    "stats": {"gpm": 650, "xpm": 700},
    "llm_summary": None,
    "created_at": "2026-02-28T12:00:00+00:00",
}

SAMPLE_DRAFT_ANALYSIS = {
    "id": 1,
    "user_id": 42,
    "ally_hero_ids": [1, 2, 3],
    "enemy_hero_ids": [10, 11, 12],
    "recommended_ids": [50, 51],
    "user_role": 1,
    "confidence": 0.85,
    "created_at": "2026-02-28T12:00:00+00:00",
}

SAMPLE_SUBSCRIPTION = {
    "id": 1,
    "user_id": 42,
    "plan": "premium",
    "status": "active",
    "started_at": "2026-02-28T00:00:00+00:00",
    "expires_at": "2026-03-28T00:00:00+00:00",
    "cancelled_at": None,
    "created_at": "2026-02-28T00:00:00+00:00",
}


# === Тесты MmrHistoryRepository ===


class TestMmrHistoryInsert:
    """Тесты MmrHistoryRepository.insert()."""

    def test_insert_returns_record(self):
        """insert() вставляет запись и возвращает её."""
        client = MagicMock()
        table_mock = _mock_insert(client, "mmr_history", SAMPLE_MMR_RECORD)

        repo = MmrHistoryRepository(client=client)
        result = asyncio.run(repo.insert(user_id=42, mmr=3500))

        assert result == SAMPLE_MMR_RECORD
        client.table.assert_called_with("mmr_history")
        table_mock.insert.assert_called_once()
        insert_data = table_mock.insert.call_args[0][0]
        assert insert_data["user_id"] == 42
        assert insert_data["mmr"] == 3500

    def test_insert_correct_table(self):
        """insert() работает с таблицей mmr_history."""
        client = MagicMock()
        _mock_insert(client, "mmr_history", SAMPLE_MMR_RECORD)

        repo = MmrHistoryRepository(client=client)
        asyncio.run(repo.insert(user_id=1, mmr=1000))
        client.table.assert_called_with("mmr_history")


class TestMmrHistoryGetHistory:
    """Тесты MmrHistoryRepository.get_history()."""

    def test_returns_list_of_records(self):
        """get_history() возвращает список записей."""
        client = MagicMock()
        rows = [SAMPLE_MMR_RECORD, {**SAMPLE_MMR_RECORD, "id": 2, "mmr": 3600}]
        _mock_select_list(client, "mmr_history", rows)

        repo = MmrHistoryRepository(client=client)
        result = asyncio.run(repo.get_history(user_id=42, days=30))

        assert len(result) == 2
        assert result[0]["mmr"] == 3500

    def test_returns_empty_list(self):
        """get_history() возвращает пустой список если записей нет."""
        client = MagicMock()
        _mock_select_list(client, "mmr_history", [])

        repo = MmrHistoryRepository(client=client)
        result = asyncio.run(repo.get_history(user_id=999))

        assert result == []

    def test_default_days_30(self):
        """get_history() по умолчанию запрашивает за 30 дней."""
        client = MagicMock()
        table_mock = _mock_select_list(client, "mmr_history", [])

        repo = MmrHistoryRepository(client=client)
        asyncio.run(repo.get_history(user_id=42))

        # Проверяем что gte был вызван (фильтр по дате)
        chain = table_mock.select.return_value.eq.return_value
        chain.gte.assert_called_once()


# === Тесты MatchAnalysisRepository ===


class TestMatchAnalysisInsert:
    """Тесты MatchAnalysisRepository.insert()."""

    def test_insert_returns_record(self):
        """insert() вставляет анализ матча и возвращает запись."""
        client = MagicMock()
        _mock_insert(client, "match_analyses", SAMPLE_MATCH_ANALYSIS)

        repo = MatchAnalysisRepository(client=client)
        result = asyncio.run(repo.insert(
            user_id=42,
            match_id=7000000001,
            hero_id=1,
            role=1,
            result="win",
            duration_sec=2400,
            stats={"gpm": 650, "xpm": 700},
        ))

        assert result == SAMPLE_MATCH_ANALYSIS
        client.table.assert_called_with("match_analyses")

    def test_insert_with_llm_summary(self):
        """insert() с llm_summary включает его в данные."""
        client = MagicMock()
        record = {**SAMPLE_MATCH_ANALYSIS, "llm_summary": "Отличная игра"}
        table_mock = _mock_insert(client, "match_analyses", record)

        repo = MatchAnalysisRepository(client=client)
        asyncio.run(repo.insert(
            user_id=42,
            match_id=7000000001,
            hero_id=1,
            role=1,
            result="win",
            duration_sec=2400,
            llm_summary="Отличная игра",
        ))

        insert_data = table_mock.insert.call_args[0][0]
        assert insert_data["llm_summary"] == "Отличная игра"

    def test_insert_default_stats_empty(self):
        """insert() без stats устанавливает пустой dict."""
        client = MagicMock()
        table_mock = _mock_insert(client, "match_analyses", SAMPLE_MATCH_ANALYSIS)

        repo = MatchAnalysisRepository(client=client)
        asyncio.run(repo.insert(
            user_id=42,
            match_id=7000000001,
            hero_id=1,
            role=1,
            result="win",
            duration_sec=2400,
        ))

        insert_data = table_mock.insert.call_args[0][0]
        assert insert_data["stats"] == {}


class TestMatchAnalysisGetByMatchId:
    """Тесты MatchAnalysisRepository.get_by_match_id()."""

    def test_returns_record_when_found(self):
        """get_by_match_id() возвращает анализ при нахождении."""
        client = MagicMock()
        _mock_select_single(client, "match_analyses", SAMPLE_MATCH_ANALYSIS)

        repo = MatchAnalysisRepository(client=client)
        result = asyncio.run(repo.get_by_match_id(user_id=42, match_id=7000000001))

        assert result == SAMPLE_MATCH_ANALYSIS

    def test_returns_none_when_not_found(self):
        """get_by_match_id() возвращает None если не найден."""
        client = MagicMock()
        _mock_select_single(client, "match_analyses", None)

        repo = MatchAnalysisRepository(client=client)
        result = asyncio.run(repo.get_by_match_id(user_id=42, match_id=999))

        assert result is None


class TestMatchAnalysisGetLatest:
    """Тесты MatchAnalysisRepository.get_latest()."""

    def test_returns_list(self):
        """get_latest() возвращает список последних анализов."""
        client = MagicMock()
        _mock_select_list(client, "match_analyses", [SAMPLE_MATCH_ANALYSIS])

        repo = MatchAnalysisRepository(client=client)
        result = asyncio.run(repo.get_latest(user_id=42))

        assert len(result) == 1

    def test_returns_empty_list(self):
        """get_latest() возвращает пустой список если анализов нет."""
        client = MagicMock()
        _mock_select_list(client, "match_analyses", [])

        repo = MatchAnalysisRepository(client=client)
        result = asyncio.run(repo.get_latest(user_id=999))

        assert result == []


# === Тесты DraftAnalysisRepository ===


class TestDraftAnalysisInsert:
    """Тесты DraftAnalysisRepository.insert()."""

    def test_insert_returns_record(self):
        """insert() вставляет анализ драфта и возвращает запись."""
        client = MagicMock()
        _mock_insert(client, "draft_analyses", SAMPLE_DRAFT_ANALYSIS)

        repo = DraftAnalysisRepository(client=client)
        result = asyncio.run(repo.insert(
            user_id=42,
            ally_hero_ids=[1, 2, 3],
            enemy_hero_ids=[10, 11, 12],
            recommended_ids=[50, 51],
            user_role=1,
            confidence=0.85,
        ))

        assert result == SAMPLE_DRAFT_ANALYSIS
        client.table.assert_called_with("draft_analyses")

    def test_insert_minimal_data(self):
        """insert() работает только с обязательными полями."""
        client = MagicMock()
        table_mock = _mock_insert(client, "draft_analyses", SAMPLE_DRAFT_ANALYSIS)

        repo = DraftAnalysisRepository(client=client)
        asyncio.run(repo.insert(
            user_id=42,
            ally_hero_ids=[1],
            enemy_hero_ids=[10],
        ))

        insert_data = table_mock.insert.call_args[0][0]
        assert insert_data["recommended_ids"] == []
        assert "user_role" not in insert_data
        assert "confidence" not in insert_data


class TestDraftAnalysisGetLatest:
    """Тесты DraftAnalysisRepository.get_latest()."""

    def test_returns_list(self):
        """get_latest() возвращает список последних анализов."""
        client = MagicMock()
        rows = [SAMPLE_DRAFT_ANALYSIS, {**SAMPLE_DRAFT_ANALYSIS, "id": 2}]
        _mock_select_list(client, "draft_analyses", rows)

        repo = DraftAnalysisRepository(client=client)
        result = asyncio.run(repo.get_latest(user_id=42, limit=5))

        assert len(result) == 2

    def test_returns_empty_list(self):
        """get_latest() возвращает пустой список если анализов нет."""
        client = MagicMock()
        _mock_select_list(client, "draft_analyses", [])

        repo = DraftAnalysisRepository(client=client)
        result = asyncio.run(repo.get_latest(user_id=999))

        assert result == []


# === Тесты SubscriptionRepository ===


class TestSubscriptionCreate:
    """Тесты SubscriptionRepository.create()."""

    def test_create_returns_record(self):
        """create() создаёт подписку и возвращает запись."""
        client = MagicMock()
        table_mock = _mock_insert(client, "subscriptions", SAMPLE_SUBSCRIPTION)

        repo = SubscriptionRepository(client=client)
        result = asyncio.run(repo.create(
            user_id=42,
            expires_at="2026-03-28T00:00:00+00:00",
        ))

        assert result == SAMPLE_SUBSCRIPTION
        client.table.assert_called_with("subscriptions")
        insert_data = table_mock.insert.call_args[0][0]
        assert insert_data["status"] == "active"
        assert insert_data["plan"] == "premium"

    def test_create_default_plan_premium(self):
        """create() по умолчанию создаёт premium подписку."""
        client = MagicMock()
        table_mock = _mock_insert(client, "subscriptions", SAMPLE_SUBSCRIPTION)

        repo = SubscriptionRepository(client=client)
        asyncio.run(repo.create(user_id=42))

        insert_data = table_mock.insert.call_args[0][0]
        assert insert_data["plan"] == "premium"


class TestSubscriptionGetActive:
    """Тесты SubscriptionRepository.get_active()."""

    def test_returns_active_subscription(self):
        """get_active() возвращает активную подписку."""
        client = MagicMock()
        _mock_select_single(client, "subscriptions", SAMPLE_SUBSCRIPTION)

        repo = SubscriptionRepository(client=client)
        result = asyncio.run(repo.get_active(user_id=42))

        assert result == SAMPLE_SUBSCRIPTION

    def test_returns_none_when_no_active(self):
        """get_active() возвращает None если активной подписки нет."""
        client = MagicMock()
        _mock_select_single(client, "subscriptions", None)

        repo = SubscriptionRepository(client=client)
        result = asyncio.run(repo.get_active(user_id=999))

        assert result is None


class TestSubscriptionDeactivate:
    """Тесты SubscriptionRepository.deactivate()."""

    def test_deactivate_sets_cancelled(self):
        """deactivate() меняет статус на cancelled."""
        client = MagicMock()
        cancelled = {**SAMPLE_SUBSCRIPTION, "status": "cancelled"}
        table_mock = _mock_update(client, "subscriptions", cancelled)

        repo = SubscriptionRepository(client=client)
        result = asyncio.run(repo.deactivate(subscription_id=1))

        assert result["status"] == "cancelled"
        client.table.assert_called_with("subscriptions")
        update_data = table_mock.update.call_args[0][0]
        assert update_data["status"] == "cancelled"
        assert "cancelled_at" in update_data
