"""Тесты для clients/stratz.py — StratzClient (GraphQL).

Все тесты мокают _sync_query (cloudscraper), а не httpx.AsyncClient.post,
потому что _query использует asyncio.to_thread(self._sync_query, ...).
"""

import asyncio
import json
from unittest.mock import MagicMock, patch

import httpx

from clients.stratz import (
    RANK_TO_STRATZ_BRACKET,
    RANK_TO_STRATZ_BRACKET_BASIC,
    ROLE_TO_STRATZ_POSITION,
    HeroBuildData,
    HeroMatchup,
    HeroMatchupData,
    ItemPurchase,
    MetaHeroStats,
    StratzClient,
    StratzGraphQLError,
    _RateLimiter,
)
from core.enums import RankBracket, Role
from core.exceptions import APIRateLimited

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

_TEST_TOKEN = "test-stratz-token-123"


def _sync_ok(data: object, status_code: int = 200) -> dict:
    """Возвращает ответ в формате _sync_query: {status_code, body, headers}."""
    return {
        "status_code": status_code,
        "body": json.dumps(data),
        "headers": {"content-type": "application/json"},
    }


def _make_client() -> StratzClient:
    """Создать StratzClient с замоканным cloudscraper."""
    client = StratzClient(token=_TEST_TOKEN)
    return client


# ---------------------------------------------------------------------------
# Тестовые данные
# ---------------------------------------------------------------------------

META_HEROES_RESPONSE = {
    "data": {
        "heroStats": {
            "winWeek": [
                {"heroId": 1, "matchCount": 15000, "winCount": 8250},
                {"heroId": 2, "matchCount": 12000, "winCount": 6000},
                {"heroId": 3, "matchCount": 0, "winCount": 0},
            ]
        }
    }
}

# Новый формат ответа: itemStartingPurchase + itemFullPurchase
HERO_BUILD_RESPONSE = {
    "data": {
        "heroStats": {
            "itemStartingPurchase": [
                {"itemId": 16, "matchCount": 5000, "winCount": 2800, "wasGiven": False},
                {"itemId": 17, "matchCount": 4500, "winCount": 2400, "wasGiven": True},
            ],
            "itemFullPurchase": [
                {"itemId": 50, "matchCount": 4500, "winCount": 2500, "time": 10},
                {"itemId": 108, "matchCount": 3800, "winCount": 2100, "time": 18},
                {"itemId": 139, "matchCount": 3000, "winCount": 1700, "time": 20},
                {"itemId": 116, "matchCount": 2000, "winCount": 1150, "time": 30},
            ],
        }
    }
}

EMPTY_BUILD_RESPONSE = {
    "data": {
        "heroStats": {
            "itemStartingPurchase": [],
            "itemFullPurchase": [],
        }
    }
}

MATCHUP_RESPONSE = {
    "data": {
        "heroStats": {
            "matchUp": {
                "advantage": [
                    {
                        "heroId": 1,
                        "with": [
                            {"heroId2": 5, "matchCount": 1200, "winCount": 680, "synergy": 3.5},
                            {"heroId2": 10, "matchCount": 1000, "winCount": 540, "synergy": 1.2},
                        ],
                        "vs": [
                            {"heroId2": 23, "matchCount": 1500, "winCount": 600, "synergy": -5.2},
                            {"heroId2": 8, "matchCount": 1100, "winCount": 500, "synergy": -3.0},
                        ],
                    }
                ]
            }
        }
    }
}

GRAPHQL_ERROR_RESPONSE = {
    "errors": [
        {"message": "Невалидный heroId"},
        {"message": "Поле 'xyz' не существует"},
    ]
}


# ---------------------------------------------------------------------------
# Тесты маппинга enum-ов
# ---------------------------------------------------------------------------

class TestEnumMapping:
    def test_all_ranks_mapped(self) -> None:
        for bracket in RankBracket:
            assert bracket in RANK_TO_STRATZ_BRACKET

    def test_all_roles_mapped(self) -> None:
        for role in Role:
            assert role in ROLE_TO_STRATZ_POSITION

    def test_rank_mapping_values(self) -> None:
        # RANK_TO_STRATZ_BRACKET — одиночные брекеты (для winWeek запросов)
        assert RANK_TO_STRATZ_BRACKET[RankBracket.HERALD] == "HERALD"
        assert RANK_TO_STRATZ_BRACKET[RankBracket.GUARDIAN] == "GUARDIAN"
        assert RANK_TO_STRATZ_BRACKET[RankBracket.DIVINE] == "DIVINE"
        assert RANK_TO_STRATZ_BRACKET[RankBracket.IMMORTAL] == "IMMORTAL"

    def test_rank_basic_mapping_values(self) -> None:
        # RANK_TO_STRATZ_BRACKET_BASIC — парные брекеты (для stats/builds запросов)
        assert RANK_TO_STRATZ_BRACKET_BASIC[RankBracket.HERALD] == "HERALD_GUARDIAN"
        assert RANK_TO_STRATZ_BRACKET_BASIC[RankBracket.GUARDIAN] == "HERALD_GUARDIAN"
        assert RANK_TO_STRATZ_BRACKET_BASIC[RankBracket.DIVINE] == "DIVINE_IMMORTAL"
        assert RANK_TO_STRATZ_BRACKET_BASIC[RankBracket.IMMORTAL] == "DIVINE_IMMORTAL"

    def test_role_mapping_values(self) -> None:
        assert ROLE_TO_STRATZ_POSITION[Role.CARRY] == "POSITION_1"
        assert ROLE_TO_STRATZ_POSITION[Role.MID] == "POSITION_2"
        assert ROLE_TO_STRATZ_POSITION[Role.HARD_SUPPORT] == "POSITION_5"


# ---------------------------------------------------------------------------
# Тесты RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_acquire_does_not_block_when_tokens_available(self) -> None:
        limiter = _RateLimiter(max_tokens=10, refill_period=1.0)
        for _ in range(10):
            asyncio.run(limiter.acquire())


# ---------------------------------------------------------------------------
# Тесты get_meta_heroes
# ---------------------------------------------------------------------------

class TestGetMetaHeroes:
    def test_parses_meta_heroes(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(META_HEROES_RESPONSE))

        result = asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE))

        assert len(result) == 3
        assert isinstance(result[0], MetaHeroStats)
        assert result[0].hero_id == 1
        assert result[0].match_count == 15000
        assert result[0].win_count == 8250

    def test_winrate_property(self) -> None:
        h = MetaHeroStats(hero_id=1, match_count=100, win_count=55)
        assert h.winrate == 0.55

    def test_winrate_zero_games(self) -> None:
        h = MetaHeroStats(hero_id=1, match_count=0, win_count=0)
        assert h.winrate == 0.0

    def test_sends_correct_variables(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(META_HEROES_RESPONSE))

        asyncio.run(client.get_meta_heroes(role=Role.MID, bracket=RankBracket.LEGEND))

        call_args = client._sync_query.call_args
        # _sync_query(url, headers, payload)
        payload = call_args[0][2]
        variables = payload["variables"]
        assert variables["bracketIds"] == ["LEGEND"]
        assert variables["positionIds"] == ["POSITION_2"]

    def test_sends_bearer_token(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(META_HEROES_RESPONSE))

        asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.HERALD))

        call_args = client._sync_query.call_args
        headers = call_args[0][1]
        assert headers["Authorization"] == f"Bearer {_TEST_TOKEN}"

    def test_accepts_int_role_and_str_bracket(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(META_HEROES_RESPONSE))

        result = asyncio.run(client.get_meta_heroes(role=1, bracket="DIVINE"))

        assert len(result) == 3

    def test_empty_response(self) -> None:
        empty = {"data": {"heroStats": {"winWeek": []}}}
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(empty))

        result = asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.HERALD))

        assert result == []


# ---------------------------------------------------------------------------
# Тесты get_hero_build
# ---------------------------------------------------------------------------

class TestGetHeroBuild:
    def test_parses_hero_build(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(HERO_BUILD_RESPONSE))

        result = asyncio.run(
            client.get_hero_build(hero_id=1, role=Role.CARRY, bracket=RankBracket.LEGEND)
        )

        assert isinstance(result, HeroBuildData)
        assert result.hero_id == 1
        assert len(result.starting_items) == 2
        assert len(result.early_game) == 1   # time=10 < 15
        assert len(result.mid_game) == 2     # time=18, time=20 (15..25)
        assert len(result.late_game) == 1    # time=30 >= 25

    def test_starting_items_parsed_correctly(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(HERO_BUILD_RESPONSE))

        result = asyncio.run(client.get_hero_build(hero_id=1))

        first_item = result.starting_items[0]
        assert isinstance(first_item, ItemPurchase)
        assert first_item.item_id == 16
        assert first_item.match_count == 5000
        assert first_item.win_count == 2800

    def test_item_winrate_property(self) -> None:
        item = ItemPurchase(item_id=100, match_count=200, win_count=110)
        assert item.winrate == 0.55

    def test_item_winrate_zero_matches(self) -> None:
        item = ItemPurchase(item_id=100, match_count=0, win_count=0)
        assert item.winrate == 0.0

    def test_items_sorted_by_match_count(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(HERO_BUILD_RESPONSE))

        result = asyncio.run(client.get_hero_build(hero_id=1))

        # starting_items отсортированы по matchCount desc
        assert result.starting_items[0].match_count >= result.starting_items[1].match_count
        # mid_game тоже
        assert result.mid_game[0].match_count >= result.mid_game[1].match_count

    def test_empty_stats_returns_empty_build(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(EMPTY_BUILD_RESPONSE))

        result = asyncio.run(client.get_hero_build(hero_id=999))

        assert result.hero_id == 999
        assert result.starting_items == []
        assert result.early_game == []
        assert result.mid_game == []
        assert result.late_game == []

    def test_optional_role_and_bracket(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(HERO_BUILD_RESPONSE))

        # Без указания роли и брекета — не должно падать
        asyncio.run(client.get_hero_build(hero_id=1))

        call_args = client._sync_query.call_args
        payload = call_args[0][2]
        variables = payload["variables"]
        assert "bracketBasicIds" not in variables
        assert "positionIds" not in variables


# ---------------------------------------------------------------------------
# Тесты get_hero_matchups
# ---------------------------------------------------------------------------

class TestGetHeroMatchups:
    def test_parses_matchups(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(MATCHUP_RESPONSE))

        result = asyncio.run(client.get_hero_matchups(hero_id=1))

        assert isinstance(result, HeroMatchupData)
        assert result.hero_id == 1
        assert len(result.with_heroes) == 2
        assert len(result.vs_heroes) == 2

    def test_with_heroes_sorted_by_synergy_desc(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(MATCHUP_RESPONSE))

        result = asyncio.run(client.get_hero_matchups(hero_id=1))

        assert result.with_heroes[0].synergy >= result.with_heroes[1].synergy
        assert result.with_heroes[0].hero_id2 == 5   # synergy=3.5
        assert result.with_heroes[1].hero_id2 == 10  # synergy=1.2

    def test_vs_heroes_sorted_by_synergy_asc(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(MATCHUP_RESPONSE))

        result = asyncio.run(client.get_hero_matchups(hero_id=1))

        assert result.vs_heroes[0].synergy <= result.vs_heroes[1].synergy
        assert result.vs_heroes[0].hero_id2 == 23  # synergy=-5.2

    def test_matchup_winrate(self) -> None:
        m = HeroMatchup(hero_id2=5, match_count=100, win_count=60, synergy=2.0)
        assert m.winrate == 0.6

    def test_matchup_winrate_zero_games(self) -> None:
        m = HeroMatchup(hero_id2=5, match_count=0, win_count=0, synergy=0.0)
        assert m.winrate == 0.0

    def test_with_bracket_filter(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(MATCHUP_RESPONSE))

        asyncio.run(client.get_hero_matchups(hero_id=1, bracket=RankBracket.IMMORTAL))

        call_args = client._sync_query.call_args
        payload = call_args[0][2]
        variables = payload["variables"]
        assert variables["bracketBasicIds"] == ["DIVINE_IMMORTAL"]


# ---------------------------------------------------------------------------
# Тесты GraphQL ошибок
# ---------------------------------------------------------------------------

class TestGraphQLErrors:
    def test_raises_on_graphql_errors(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(GRAPHQL_ERROR_RESPONSE))

        try:
            asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE))
            raise AssertionError("Ожидали StratzGraphQLError")  # noqa: TRY301
        except StratzGraphQLError as exc:
            assert "Невалидный heroId" in str(exc)
            assert len(exc.errors) == 2

    def test_graphql_error_message_joined(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok(GRAPHQL_ERROR_RESPONSE))

        try:
            asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE))
            raise AssertionError("Ожидали StratzGraphQLError")  # noqa: TRY301
        except StratzGraphQLError as exc:
            assert "Невалидный heroId" in str(exc)
            assert "не существует" in str(exc)


# ---------------------------------------------------------------------------
# Тесты retry и rate limit
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_retries_on_500(self) -> None:
        client = _make_client()
        resp_500 = _sync_ok({}, status_code=500)
        resp_ok = _sync_ok(META_HEROES_RESPONSE)
        client._sync_query = MagicMock(side_effect=[resp_500, resp_ok])

        with patch("clients.stratz._RETRY_BACKOFF", 0.01):
            result = asyncio.run(
                client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
            )

        assert len(result) == 3
        assert client._sync_query.call_count == 2

    def test_raises_api_rate_limited_on_persistent_429(self) -> None:
        client = _make_client()
        resp_429 = _sync_ok({"error": "rate limit"}, status_code=429)
        client._sync_query = MagicMock(return_value=resp_429)

        try:
            with patch("clients.stratz._RETRY_BACKOFF", 0.01):
                asyncio.run(
                    client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
                )
            raise AssertionError("Ожидали APIRateLimited")  # noqa: TRY301
        except APIRateLimited as exc:
            assert exc.service == "Stratz"

    def test_retries_on_network_error(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(
            side_effect=[
                Exception("сеть недоступна"),
                _sync_ok(META_HEROES_RESPONSE),
            ]
        )

        with patch("clients.stratz._RETRY_BACKOFF", 0.01):
            result = asyncio.run(
                client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
            )

        assert len(result) == 3

    def test_raises_after_max_retries_on_network_error(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(side_effect=Exception("сеть недоступна"))

        try:
            with patch("clients.stratz._RETRY_BACKOFF", 0.01):
                asyncio.run(
                    client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
                )
            raise AssertionError("Ожидали Exception")  # noqa: TRY301
        except Exception as exc:
            assert "сеть недоступна" in str(exc)

    def test_raises_on_4xx_without_retry(self) -> None:
        client = _make_client()
        client._sync_query = MagicMock(return_value=_sync_ok({}, status_code=401))

        try:
            asyncio.run(
                client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
            )
            raise AssertionError("Ожидали HTTPStatusError")  # noqa: TRY301
        except httpx.HTTPStatusError:
            # 401 не должен ретраиться — один вызов
            assert client._sync_query.call_count == 1


# ---------------------------------------------------------------------------
# Тесты context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_close_does_not_close_external_client(self) -> None:
        from unittest.mock import AsyncMock

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        asyncio.run(client.close())
        mock_client.aclose.assert_not_called()

    def test_close_closes_internal_client(self) -> None:
        from unittest.mock import AsyncMock

        with patch("clients.stratz.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_cls.return_value = mock_instance
            client = StratzClient(token=_TEST_TOKEN)
            asyncio.run(client.close())
            mock_instance.aclose.assert_called_once()
