"""Тесты для clients/opendota.py — OpenDotaClient."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from clients.opendota import (
    MatchDetails,
    OpenDotaClient,
    PlayerHeroStats,
    PlayerProfile,
    RecentMatch,
    _RateLimiter,
)
from core.exceptions import APIRateLimited

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _json_response(data: object, status_code: int = 200) -> httpx.Response:
    """Создать мок-ответ httpx."""
    import json
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://api.opendota.com/api/test"),
    )


PLAYER_RESPONSE = {
    "profile": {
        "personaname": "Dendi",
        "steamid": "76561198047104768",
        "avatar": "https://avatar.example.com/small.jpg",
        "avatarfull": "https://avatar.example.com/full.jpg",
    },
    "rank_tier": 80,
    "leaderboard_rank": None,
    "mmr_estimate": {"estimate": 6500},
}

RECENT_MATCHES_RESPONSE = [
    {
        "match_id": 1001,
        "hero_id": 1,
        "player_slot": 0,
        "radiant_win": True,
        "duration": 2400,
        "game_mode": 22,
        "lobby_type": 7,
        "start_time": 1700000000,
        "kills": 10,
        "deaths": 3,
        "assists": 5,
        "xp_per_min": 650,
        "gold_per_min": 700,
        "hero_damage": 25000,
        "tower_damage": 3000,
        "hero_healing": 0,
        "last_hits": 250,
        "lane": 1,
        "lane_role": 1,
    },
    {
        "match_id": 1002,
        "hero_id": 2,
        "player_slot": 128,
        "radiant_win": True,
        "duration": 1800,
        "game_mode": 22,
        "lobby_type": 7,
        "start_time": 1700003600,
        "kills": 2,
        "deaths": 7,
        "assists": 10,
    },
]

PLAYER_HEROES_RESPONSE = [
    {"hero_id": "1", "games": "50", "win": "30", "last_played": 1700000000},
    {"hero_id": "2", "games": "20", "win": "12", "last_played": 1699000000},
    {"hero_id": "0", "games": "5", "win": "3", "last_played": 0},
]

MATCH_DETAILS_RESPONSE = {
    "match_id": 1001,
    "radiant_win": True,
    "duration": 2400,
    "start_time": 1700000000,
    "game_mode": 22,
    "lobby_type": 7,
    "radiant_score": 35,
    "dire_score": 20,
    "players": [
        {"account_id": 123, "hero_id": 1, "kills": 10, "deaths": 3, "assists": 5},
    ],
}


# ---------------------------------------------------------------------------
# Тесты RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_acquire_does_not_block_when_tokens_available(self) -> None:
        limiter = _RateLimiter(max_tokens=10, refill_period=60.0)
        # 10 запросов должны пройти мгновенно
        for _ in range(10):
            asyncio.run(limiter.acquire())


# ---------------------------------------------------------------------------
# Тесты PlayerProfile (парсинг)
# ---------------------------------------------------------------------------

class TestGetPlayer:
    def test_parses_player_profile(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(PLAYER_RESPONSE))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player(123456))

        assert isinstance(result, PlayerProfile)
        assert result.account_id == 123456
        assert result.personaname == "Dendi"
        assert result.steamid == "76561198047104768"
        assert result.rank_tier == 80
        assert result.mmr_estimate == 6500

    def test_handles_missing_profile_fields(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response({"profile": {}}))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player(999))

        assert result.personaname is None
        assert result.rank_tier is None
        assert result.mmr_estimate is None


# ---------------------------------------------------------------------------
# Тесты RecentMatches
# ---------------------------------------------------------------------------

class TestGetRecentMatches:
    def test_parses_recent_matches(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            return_value=_json_response(RECENT_MATCHES_RESPONSE)
        )

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_recent_matches(123456))

        assert len(result) == 2
        assert isinstance(result[0], RecentMatch)
        assert result[0].match_id == 1001
        assert result[0].hero_id == 1
        assert result[0].kills == 10
        assert result[0].gold_per_min == 700

    def test_respects_limit_parameter(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            return_value=_json_response(RECENT_MATCHES_RESPONSE)
        )

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_recent_matches(123456, limit=1))

        assert len(result) == 1

    def test_is_win_property_radiant(self) -> None:
        m = RecentMatch(
            match_id=1, hero_id=1, player_slot=0, radiant_win=True,
            duration=100, game_mode=22, lobby_type=7, start_time=0,
        )
        assert m.is_win is True

    def test_is_win_property_dire_loss(self) -> None:
        m = RecentMatch(
            match_id=1, hero_id=1, player_slot=128, radiant_win=True,
            duration=100, game_mode=22, lobby_type=7, start_time=0,
        )
        assert m.is_win is False


# ---------------------------------------------------------------------------
# Тесты PlayerHeroes
# ---------------------------------------------------------------------------

class TestGetPlayerHeroes:
    def test_parses_hero_stats(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            return_value=_json_response(PLAYER_HEROES_RESPONSE)
        )

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player_heroes(123456))

        # hero_id=0 должен быть отфильтрован
        assert len(result) == 2
        assert isinstance(result[0], PlayerHeroStats)
        assert result[0].hero_id == 1
        assert result[0].games == 50
        assert result[0].win == 30

    def test_winrate_property(self) -> None:
        h = PlayerHeroStats(hero_id=1, games=100, win=60)
        assert h.winrate == 0.6

    def test_winrate_zero_games(self) -> None:
        h = PlayerHeroStats(hero_id=1, games=0, win=0)
        assert h.winrate == 0.0


# ---------------------------------------------------------------------------
# Тесты MatchDetails
# ---------------------------------------------------------------------------

class TestGetMatch:
    def test_parses_match_details(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            return_value=_json_response(MATCH_DETAILS_RESPONSE)
        )

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_match(1001))

        assert isinstance(result, MatchDetails)
        assert result.match_id == 1001
        assert result.radiant_win is True
        assert result.radiant_score == 35
        assert result.dire_score == 20
        assert len(result.players) == 1


# ---------------------------------------------------------------------------
# Тесты retry и rate limit
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_retries_on_500(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp_500 = _json_response({}, status_code=500)
        resp_ok = _json_response(PLAYER_RESPONSE)
        mock_client.get = AsyncMock(side_effect=[resp_500, resp_ok])

        client = OpenDotaClient(client=mock_client)
        with patch("clients.opendota._RETRY_BACKOFF", 0.01):
            result = asyncio.run(client.get_player(123))

        assert result.personaname == "Dendi"
        assert mock_client.get.call_count == 2

    def test_raises_api_rate_limited_on_persistent_429(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp_429 = _json_response(
            {"error": "rate limit"}, status_code=429,
        )
        mock_client.get = AsyncMock(return_value=resp_429)

        client = OpenDotaClient(client=mock_client)
        try:
            with patch("clients.opendota._RETRY_BACKOFF", 0.01):
                asyncio.run(client.get_player(123))
            raise AssertionError("Ожидали APIRateLimited")  # noqa: TRY301
        except APIRateLimited as exc:
            assert exc.service == "OpenDota"

    def test_retries_on_network_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=[
                httpx.ConnectError("сеть недоступна"),
                _json_response(PLAYER_RESPONSE),
            ]
        )

        client = OpenDotaClient(client=mock_client)
        with patch("clients.opendota._RETRY_BACKOFF", 0.01):
            result = asyncio.run(client.get_player(123))

        assert result.personaname == "Dendi"

    def test_raises_after_max_retries_on_network_error(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.ConnectError("сеть недоступна")
        )

        client = OpenDotaClient(client=mock_client)
        try:
            with patch("clients.opendota._RETRY_BACKOFF", 0.01):
                asyncio.run(client.get_player(123))
            raise AssertionError("Ожидали httpx.ConnectError")  # noqa: TRY301
        except httpx.ConnectError:
            pass

    def test_raises_on_4xx_without_retry(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        resp_404 = httpx.Response(
            status_code=404,
            request=httpx.Request("GET", "https://api.opendota.com/api/test"),
        )
        mock_client.get = AsyncMock(return_value=resp_404)

        client = OpenDotaClient(client=mock_client)
        try:
            asyncio.run(client.get_player(123))
            raise AssertionError("Ожидали HTTPStatusError")  # noqa: TRY301
        except httpx.HTTPStatusError:
            # 404 не должен ретраиться — один вызов
            assert mock_client.get.call_count == 1


# ---------------------------------------------------------------------------
# Тесты context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_close_does_not_close_external_client(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        client = OpenDotaClient(client=mock_client)
        asyncio.run(client.close())
        mock_client.aclose.assert_not_called()

    def test_close_closes_internal_client(self) -> None:
        with patch("clients.opendota.httpx.AsyncClient") as mock_cls:
            mock_instance = AsyncMock()
            mock_cls.return_value = mock_instance
            client = OpenDotaClient()
            asyncio.run(client.close())
            mock_instance.aclose.assert_called_once()
