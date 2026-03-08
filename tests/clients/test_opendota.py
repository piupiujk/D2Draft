"""Тесты парсинга ответов OpenDota API в типизированные модели.

Фокус на корректном маппинге JSON -> dataclass, обработке
опциональных полей и граничных случаях.
"""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx

from clients.opendota import (
    MatchDetails,
    OpenDotaClient,
    PlayerHeroStats,
    PlayerProfile,
    RecentMatch,
)

# ---------------------------------------------------------------------------
# Хелпер для создания мок-ответов httpx
# ---------------------------------------------------------------------------

def _json_response(data: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://api.opendota.com/api/test"),
    )


# ---------------------------------------------------------------------------
# Парсинг PlayerProfile
# ---------------------------------------------------------------------------

class TestParsePlayerProfile:
    """Тесты маппинга JSON-ответа /players/{id} в PlayerProfile."""

    def test_full_profile(self) -> None:
        raw = {
            "profile": {
                "personaname": "Dendi",
                "steamid": "76561198047104768",
                "avatar": "https://avatar.example.com/small.jpg",
                "avatarfull": "https://avatar.example.com/full.jpg",
            },
            "rank_tier": 80,
            "leaderboard_rank": 15,
            "mmr_estimate": {"estimate": 6500},
        }
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player(123456))

        assert isinstance(result, PlayerProfile)
        assert result.account_id == 123456
        assert result.personaname == "Dendi"
        assert result.steamid == "76561198047104768"
        assert result.avatar == "https://avatar.example.com/small.jpg"
        assert result.rank_tier == 80
        assert result.leaderboard_rank == 15
        assert result.mmr_estimate == 6500

    def test_missing_optional_fields(self) -> None:
        """Опциональные поля должны быть None при отсутствии."""
        raw = {"profile": {}}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player(999))

        assert result.personaname is None
        assert result.rank_tier is None
        assert result.mmr_estimate is None
        assert result.leaderboard_rank is None

    def test_missing_mmr_estimate_key(self) -> None:
        """mmr_estimate=None когда ключ mmr_estimate отсутствует."""
        raw = {"profile": {"personaname": "Test"}}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player(1))

        assert result.mmr_estimate is None

    def test_null_mmr_estimate(self) -> None:
        """mmr_estimate=None когда значение null."""
        raw = {"profile": {"personaname": "Test"}, "mmr_estimate": None}
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player(1))

        assert result.mmr_estimate is None


# ---------------------------------------------------------------------------
# Парсинг RecentMatch
# ---------------------------------------------------------------------------

class TestParseRecentMatches:
    """Тесты маппинга JSON-ответа /players/{id}/recentMatches в RecentMatch."""

    def test_full_match(self) -> None:
        raw = [
            {
                "match_id": 7001,
                "hero_id": 44,
                "player_slot": 3,
                "radiant_win": True,
                "duration": 2100,
                "game_mode": 22,
                "lobby_type": 7,
                "start_time": 1700000000,
                "kills": 15,
                "deaths": 2,
                "assists": 8,
                "xp_per_min": 800,
                "gold_per_min": 750,
                "hero_damage": 35000,
                "tower_damage": 5000,
                "hero_healing": 100,
                "last_hits": 300,
                "lane": 1,
                "lane_role": 1,
            }
        ]
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_recent_matches(123))

        assert len(result) == 1
        m = result[0]
        assert isinstance(m, RecentMatch)
        assert m.match_id == 7001
        assert m.hero_id == 44
        assert m.kills == 15
        assert m.gold_per_min == 750
        assert m.lane == 1
        assert m.lane_role == 1

    def test_missing_optional_stats(self) -> None:
        """Поля kills/deaths/assists по умолчанию 0."""
        raw = [
            {
                "match_id": 7002,
                "hero_id": 1,
                "player_slot": 128,
                "radiant_win": False,
                "duration": 1000,
                "game_mode": 22,
                "lobby_type": 7,
                "start_time": 0,
            }
        ]
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_recent_matches(123))

        m = result[0]
        assert m.kills == 0
        assert m.deaths == 0
        assert m.assists == 0
        assert m.gold_per_min == 0
        assert m.lane is None
        assert m.lane_role is None

    def test_limit_parameter(self) -> None:
        """limit ограничивает количество возвращённых матчей."""
        raw = [
            {"match_id": i, "hero_id": 1, "player_slot": 0,
             "radiant_win": True, "duration": 100, "game_mode": 22,
             "lobby_type": 7, "start_time": 0}
            for i in range(10)
        ]
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_recent_matches(123, limit=3))

        assert len(result) == 3

    def test_is_win_radiant_player_radiant_win(self) -> None:
        m = RecentMatch(
            match_id=1, hero_id=1, player_slot=0, radiant_win=True,
            duration=100, game_mode=22, lobby_type=7, start_time=0,
        )
        assert m.is_win is True

    def test_is_win_dire_player_radiant_win(self) -> None:
        m = RecentMatch(
            match_id=1, hero_id=1, player_slot=128, radiant_win=True,
            duration=100, game_mode=22, lobby_type=7, start_time=0,
        )
        assert m.is_win is False

    def test_is_win_dire_player_dire_win(self) -> None:
        m = RecentMatch(
            match_id=1, hero_id=1, player_slot=130, radiant_win=False,
            duration=100, game_mode=22, lobby_type=7, start_time=0,
        )
        assert m.is_win is True


# ---------------------------------------------------------------------------
# Парсинг PlayerHeroStats
# ---------------------------------------------------------------------------

class TestParsePlayerHeroes:
    """Тесты маппинга JSON-ответа /players/{id}/heroes в PlayerHeroStats."""

    def test_parses_hero_stats(self) -> None:
        raw = [
            {"hero_id": "1", "games": "50", "win": "30", "last_played": 1700000000},
            {"hero_id": "2", "games": "20", "win": "12", "last_played": 1699000000},
        ]
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player_heroes(123))

        assert len(result) == 2
        assert isinstance(result[0], PlayerHeroStats)
        assert result[0].hero_id == 1
        assert result[0].games == 50
        assert result[0].win == 30

    def test_filters_out_hero_id_zero(self) -> None:
        """hero_id=0 (общая статистика) должен быть отфильтрован."""
        raw = [
            {"hero_id": "0", "games": "100", "win": "50"},
            {"hero_id": "1", "games": "20", "win": "10"},
        ]
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player_heroes(123))

        assert len(result) == 1
        assert result[0].hero_id == 1

    def test_string_to_int_conversion(self) -> None:
        """OpenDota API возвращает строки — должны конвертироваться в int."""
        raw = [{"hero_id": "44", "games": "100", "win": "55"}]
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_player_heroes(123))

        assert result[0].hero_id == 44
        assert isinstance(result[0].hero_id, int)
        assert isinstance(result[0].games, int)

    def test_winrate_property(self) -> None:
        h = PlayerHeroStats(hero_id=1, games=100, win=60)
        assert h.winrate == 0.6

    def test_winrate_zero_games(self) -> None:
        h = PlayerHeroStats(hero_id=1, games=0, win=0)
        assert h.winrate == 0.0


# ---------------------------------------------------------------------------
# Парсинг MatchDetails
# ---------------------------------------------------------------------------

class TestParseMatchDetails:
    """Тесты маппинга JSON-ответа /matches/{id} в MatchDetails."""

    def test_full_match_details(self) -> None:
        raw = {
            "match_id": 8001,
            "radiant_win": True,
            "duration": 2400,
            "start_time": 1700000000,
            "game_mode": 22,
            "lobby_type": 7,
            "radiant_score": 35,
            "dire_score": 20,
            "players": [
                {"account_id": 111, "hero_id": 1, "kills": 10},
                {"account_id": 222, "hero_id": 2, "kills": 5},
            ],
        }
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_match(8001))

        assert isinstance(result, MatchDetails)
        assert result.match_id == 8001
        assert result.radiant_win is True
        assert result.radiant_score == 35
        assert result.dire_score == 20
        assert len(result.players) == 2

    def test_missing_scores_default_zero(self) -> None:
        raw = {
            "match_id": 8002,
            "radiant_win": False,
            "duration": 1000,
            "start_time": 0,
            "game_mode": 22,
            "lobby_type": 7,
            "players": [],
        }
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_match(8002))

        assert result.radiant_score == 0
        assert result.dire_score == 0
        assert result.players == []

    def test_empty_players_list(self) -> None:
        raw = {
            "match_id": 8003,
            "radiant_win": True,
            "duration": 500,
            "start_time": 0,
            "game_mode": 22,
            "lobby_type": 7,
        }
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=_json_response(raw))

        client = OpenDotaClient(client=mock_client)
        result = asyncio.run(client.get_match(8003))

        assert result.players == []
