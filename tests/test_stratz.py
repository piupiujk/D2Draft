"""Тесты для clients/stratz.py — StratzClient (GraphQL)."""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx

from clients.stratz import (
    RANK_TO_STRATZ_BRACKET,
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
_GRAPHQL_URL = "https://api.stratz.com/graphql"


def _json_response(data: object, status_code: int = 200) -> httpx.Response:
    """Создать мок-ответ httpx."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", _GRAPHQL_URL),
    )


# Ответ на запрос мета-героев
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

# Ответ на запрос билда героя
HERO_BUILD_RESPONSE = {
    "data": {
        "heroStats": {
            "stats": [
                {
                    "heroId": 1,
                    "matchCount": 15000,
                    "winCount": 8250,
                    "purchasePattern": {
                        "startingItems": [
                            {"itemId": 16, "matchCount": 5000, "winCount": 2800, "wasGiven": False},
                            {"itemId": 17, "matchCount": 4500, "winCount": 2400, "wasGiven": True},
                        ],
                        "earlyGame": [
                            {"itemId": 50, "matchCount": 4500, "winCount": 2500, "time": 480},
                        ],
                        "midGame": [
                            {"itemId": 108, "matchCount": 3800, "winCount": 2100, "time": 1200},
                            {"itemId": 139, "matchCount": 3000, "winCount": 1700, "time": 1500},
                        ],
                        "lateGame": [
                            {"itemId": 116, "matchCount": 2000, "winCount": 1150, "time": 2400},
                        ],
                    },
                }
            ]
        }
    }
}

# Пустой ответ на билд (герой без данных)
EMPTY_BUILD_RESPONSE = {
    "data": {
        "heroStats": {
            "stats": []
        }
    }
}

# Ответ на запрос matchups
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

# Ответ с GraphQL ошибками
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
        assert RANK_TO_STRATZ_BRACKET[RankBracket.HERALD] == "HERALD_GUARDIAN"
        assert RANK_TO_STRATZ_BRACKET[RankBracket.GUARDIAN] == "HERALD_GUARDIAN"
        assert RANK_TO_STRATZ_BRACKET[RankBracket.DIVINE] == "DIVINE_IMMORTAL"
        assert RANK_TO_STRATZ_BRACKET[RankBracket.IMMORTAL] == "DIVINE_IMMORTAL"

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
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(META_HEROES_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
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
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(META_HEROES_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        asyncio.run(client.get_meta_heroes(role=Role.MID, bracket=RankBracket.LEGEND))

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        variables = payload["variables"]
        assert variables["bracketIds"] == ["LEGEND_ANCIENT"]
        assert variables["positionIds"] == ["POSITION_2"]

    def test_sends_bearer_token(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(META_HEROES_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.HERALD))

        call_args = mock_client.post.call_args
        headers = call_args.kwargs.get("headers") or call_args[1].get("headers")
        assert headers["Authorization"] == f"Bearer {_TEST_TOKEN}"

    def test_accepts_int_role_and_str_bracket(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(META_HEROES_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_meta_heroes(role=1, bracket="DIVINE"))

        assert len(result) == 3

    def test_empty_response(self) -> None:
        empty = {"data": {"heroStats": {"winWeek": []}}}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=_json_response(empty))

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.HERALD))

        assert result == []


# ---------------------------------------------------------------------------
# Тесты get_hero_build
# ---------------------------------------------------------------------------

class TestGetHeroBuild:
    def test_parses_hero_build(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(HERO_BUILD_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(
            client.get_hero_build(hero_id=1, role=Role.CARRY, bracket=RankBracket.LEGEND)
        )

        assert isinstance(result, HeroBuildData)
        assert result.hero_id == 1
        assert len(result.starting_items) == 2
        assert len(result.early_game) == 1
        assert len(result.mid_game) == 2
        assert len(result.late_game) == 1

    def test_starting_items_parsed_correctly(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(HERO_BUILD_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
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
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(HERO_BUILD_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_hero_build(hero_id=1))

        # starting_items отсортированы по matchCount desc
        assert result.starting_items[0].match_count >= result.starting_items[1].match_count
        # mid_game тоже
        assert result.mid_game[0].match_count >= result.mid_game[1].match_count

    def test_empty_stats_returns_empty_build(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(EMPTY_BUILD_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_hero_build(hero_id=999))

        assert result.hero_id == 999
        assert result.starting_items == []
        assert result.early_game == []
        assert result.mid_game == []
        assert result.late_game == []

    def test_optional_role_and_bracket(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(HERO_BUILD_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        # Без указания роли и брекета — не должно падать
        asyncio.run(client.get_hero_build(hero_id=1))

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        variables = payload["variables"]
        # Только heroId, без bracketBasicIds и positionId
        assert "bracketBasicIds" not in variables
        assert "positionId" not in variables


# ---------------------------------------------------------------------------
# Тесты get_hero_matchups
# ---------------------------------------------------------------------------

class TestGetHeroMatchups:
    def test_parses_matchups(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(MATCHUP_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_hero_matchups(hero_id=1))

        assert isinstance(result, HeroMatchupData)
        assert result.hero_id == 1
        assert len(result.with_heroes) == 2
        assert len(result.vs_heroes) == 2

    def test_with_heroes_sorted_by_synergy_desc(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(MATCHUP_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_hero_matchups(hero_id=1))

        # with_heroes отсортированы по synergy по убыванию
        assert result.with_heroes[0].synergy >= result.with_heroes[1].synergy
        assert result.with_heroes[0].hero_id2 == 5  # synergy=3.5
        assert result.with_heroes[1].hero_id2 == 10  # synergy=1.2

    def test_vs_heroes_sorted_by_synergy_asc(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(MATCHUP_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        result = asyncio.run(client.get_hero_matchups(hero_id=1))

        # vs_heroes отсортированы по synergy по возрастанию (самые плохие первые)
        assert result.vs_heroes[0].synergy <= result.vs_heroes[1].synergy
        assert result.vs_heroes[0].hero_id2 == 23  # synergy=-5.2

    def test_matchup_winrate(self) -> None:
        m = HeroMatchup(hero_id2=5, match_count=100, win_count=60, synergy=2.0)
        assert m.winrate == 0.6

    def test_matchup_winrate_zero_games(self) -> None:
        m = HeroMatchup(hero_id2=5, match_count=0, win_count=0, synergy=0.0)
        assert m.winrate == 0.0

    def test_with_bracket_filter(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(MATCHUP_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        asyncio.run(client.get_hero_matchups(hero_id=1, bracket=RankBracket.IMMORTAL))

        call_args = mock_client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        variables = payload["variables"]
        assert variables["bracketBasicIds"] == ["DIVINE_IMMORTAL"]


# ---------------------------------------------------------------------------
# Тесты GraphQL ошибок
# ---------------------------------------------------------------------------

class TestGraphQLErrors:
    def test_raises_on_graphql_errors(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(GRAPHQL_ERROR_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        try:
            asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE))
            raise AssertionError("Ожидали StratzGraphQLError")  # noqa: TRY301
        except StratzGraphQLError as exc:
            assert "Невалидный heroId" in str(exc)
            assert len(exc.errors) == 2

    def test_graphql_error_message_joined(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            return_value=_json_response(GRAPHQL_ERROR_RESPONSE)
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        try:
            asyncio.run(client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE))
            raise AssertionError("Ожидали StratzGraphQLError")  # noqa: TRY301
        except StratzGraphQLError as exc:
            # Оба сообщения объединены через "; "
            assert "Невалидный heroId" in str(exc)
            assert "не существует" in str(exc)


# ---------------------------------------------------------------------------
# Тесты retry и rate limit
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_retries_on_500(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp_500 = _json_response({}, status_code=500)
        resp_ok = _json_response(META_HEROES_RESPONSE)
        mock_client.post = AsyncMock(side_effect=[resp_500, resp_ok])

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        with patch("clients.stratz._RETRY_BACKOFF", 0.01):
            result = asyncio.run(
                client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
            )

        assert len(result) == 3
        assert mock_client.post.call_count == 2

    def test_raises_api_rate_limited_on_persistent_429(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp_429 = _json_response({"error": "rate limit"}, status_code=429)
        mock_client.post = AsyncMock(return_value=resp_429)

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        try:
            with patch("clients.stratz._RETRY_BACKOFF", 0.01):
                asyncio.run(
                    client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
                )
            raise AssertionError("Ожидали APIRateLimited")  # noqa: TRY301
        except APIRateLimited as exc:
            assert exc.service == "Stratz"

    def test_retries_on_network_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=[
                httpx.ConnectError("сеть недоступна"),
                _json_response(META_HEROES_RESPONSE),
            ]
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        with patch("clients.stratz._RETRY_BACKOFF", 0.01):
            result = asyncio.run(
                client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
            )

        assert len(result) == 3

    def test_raises_after_max_retries_on_network_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(
            side_effect=httpx.ConnectError("сеть недоступна")
        )

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        try:
            with patch("clients.stratz._RETRY_BACKOFF", 0.01):
                asyncio.run(
                    client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
                )
            raise AssertionError("Ожидали httpx.ConnectError")  # noqa: TRY301
        except httpx.ConnectError:
            pass

    def test_raises_on_4xx_without_retry(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp_401 = httpx.Response(
            status_code=401,
            request=httpx.Request("POST", _GRAPHQL_URL),
        )
        mock_client.post = AsyncMock(return_value=resp_401)

        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        try:
            asyncio.run(
                client.get_meta_heroes(role=Role.CARRY, bracket=RankBracket.DIVINE)
            )
            raise AssertionError("Ожидали HTTPStatusError")  # noqa: TRY301
        except httpx.HTTPStatusError:
            # 401 не должен ретраиться — один вызов
            assert mock_client.post.call_count == 1


# ---------------------------------------------------------------------------
# Тесты context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_close_does_not_close_external_client(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client = StratzClient(token=_TEST_TOKEN, client=mock_client)
        asyncio.run(client.close())
        mock_client.aclose.assert_not_called()

    def test_close_closes_internal_client(self) -> None:
        with patch("clients.stratz.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_cls.return_value = mock_instance
            client = StratzClient(token=_TEST_TOKEN)
            asyncio.run(client.close())
            mock_instance.aclose.assert_called_once()
