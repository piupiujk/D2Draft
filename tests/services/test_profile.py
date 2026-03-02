"""Тесты для services/profile.py — сервис профиля пользователя."""

import asyncio
import sys
import time
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

# --- Мокаем зависимости до импорта сервиса ---

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

from clients.opendota import PlayerHeroStats, RecentMatch  # noqa: E402
from core.enums import RankBracket, Role  # noqa: E402
from services.profile import (  # noqa: E402
    MmrPoint,
    UserProfile,
    _build_top_heroes,
    _calc_overall_winrate,
    _calc_recent_winrate,
    _calc_streaks,
    get_user_profile,
)

# ---------------------------------------------------------------------------
# Тестовые данные
# ---------------------------------------------------------------------------

NOW_TS = int(time.time())

HERO_STATS = [
    PlayerHeroStats(hero_id=1, games=100, win=60),  # 60%, Anti-Mage
    PlayerHeroStats(hero_id=2, games=80, win=40),   # 50%, Axe
    PlayerHeroStats(hero_id=8, games=50, win=30),   # 60%, Juggernaut
    PlayerHeroStats(hero_id=11, games=30, win=18),   # 60%, Shadow Fiend
    PlayerHeroStats(hero_id=44, games=20, win=14),   # 70%, Phantom Assassin
    PlayerHeroStats(hero_id=5, games=10, win=3),     # 30%, Crystal Maiden
]

HERO_STATS_EMPTY: list[PlayerHeroStats] = []

HERO_STATS_ZERO_GAMES = [
    PlayerHeroStats(hero_id=1, games=0, win=0),
]


def _make_match(match_id: int, *, is_win: bool, days_ago: int = 0) -> RecentMatch:
    """Создать тестовый RecentMatch."""
    return RecentMatch(
        match_id=match_id,
        hero_id=1,
        player_slot=0 if is_win else 128,  # slot < 128 = radiant
        radiant_win=True,
        duration=2400,
        game_mode=22,
        lobby_type=7,
        start_time=NOW_TS - days_ago * 86400,
    )


RECENT_MATCHES = [
    _make_match(1001, is_win=True, days_ago=0),
    _make_match(1002, is_win=True, days_ago=1),
    _make_match(1003, is_win=False, days_ago=2),
    _make_match(1004, is_win=True, days_ago=5),
    _make_match(1005, is_win=False, days_ago=10),
    _make_match(1006, is_win=True, days_ago=20),
    _make_match(1007, is_win=False, days_ago=25),
    _make_match(1008, is_win=True, days_ago=35),  # > 30 дней
]

TEST_USER = {
    "id": 42,
    "steam_id": "76561198047104768",
    "current_mmr": 3500,
    "main_role": 1,
    "username": "TestPlayer",
}

TEST_USER_NO_STEAM = {
    "id": 43,
    "steam_id": None,
    "current_mmr": 2000,
    "main_role": 3,
    "username": "NoSteam",
}


# ---------------------------------------------------------------------------
# _calc_overall_winrate
# ---------------------------------------------------------------------------


class TestCalcOverallWinrate:
    def test_calculates_winrate(self):
        result = _calc_overall_winrate(HERO_STATS)
        # 60+40+30+18+14+3 = 165 побед, 100+80+50+30+20+10 = 290 игр
        expected = round(165 / 290 * 100, 1)
        assert result == expected

    def test_empty_returns_none(self):
        assert _calc_overall_winrate(HERO_STATS_EMPTY) is None

    def test_zero_games_returns_none(self):
        assert _calc_overall_winrate(HERO_STATS_ZERO_GAMES) is None

    def test_returns_float(self):
        result = _calc_overall_winrate(HERO_STATS)
        assert isinstance(result, float)

    def test_range_0_to_100(self):
        result = _calc_overall_winrate(HERO_STATS)
        assert 0.0 <= result <= 100.0


# ---------------------------------------------------------------------------
# _build_top_heroes
# ---------------------------------------------------------------------------


class TestBuildTopHeroes:
    def test_returns_top_5(self):
        result = _build_top_heroes(HERO_STATS, top_n=5)
        assert len(result) == 5

    def test_sorted_by_games_desc(self):
        result = _build_top_heroes(HERO_STATS, top_n=5)
        games = [h.games for h in result]
        assert games == sorted(games, reverse=True)

    def test_first_hero_most_games(self):
        result = _build_top_heroes(HERO_STATS, top_n=5)
        assert result[0].hero_id == 1
        assert result[0].games == 100

    def test_has_russian_name(self):
        result = _build_top_heroes(HERO_STATS, top_n=1)
        assert result[0].name_ru  # Непустое

    def test_has_english_name(self):
        result = _build_top_heroes(HERO_STATS, top_n=1)
        assert result[0].name_en  # Непустое

    def test_winrate_calculated(self):
        result = _build_top_heroes(HERO_STATS, top_n=1)
        assert result[0].winrate == 0.6  # 60/100

    def test_empty_stats(self):
        result = _build_top_heroes([], top_n=5)
        assert result == []

    def test_zero_games_excluded(self):
        result = _build_top_heroes(HERO_STATS_ZERO_GAMES, top_n=5)
        assert result == []

    def test_top_n_limits(self):
        result = _build_top_heroes(HERO_STATS, top_n=2)
        assert len(result) == 2

    def test_unknown_hero_fallback(self):
        stats = [PlayerHeroStats(hero_id=99999, games=10, win=5)]
        result = _build_top_heroes(stats, top_n=1)
        assert len(result) == 1
        assert "99999" in result[0].name_ru


# ---------------------------------------------------------------------------
# _calc_recent_winrate
# ---------------------------------------------------------------------------


class TestCalcRecentWinrate:
    def test_7_days(self):
        result = _calc_recent_winrate(RECENT_MATCHES, days=7)
        # Матчи за 7 дней: 1001(W), 1002(W), 1003(L), 1004(W) = 3/4 = 75%
        assert result == 75.0

    def test_30_days(self):
        result = _calc_recent_winrate(RECENT_MATCHES, days=30)
        # Матчи за 30 дней: 1001-1007 (7 матчей), 4 побед, 3 поражения
        assert result == round(4 / 7 * 100, 1)

    def test_empty_matches(self):
        assert _calc_recent_winrate([], days=7) is None

    def test_no_recent_matches(self):
        # Все матчи старше 1 дня, cutoff = 0 дней
        old_matches = [_make_match(1, is_win=True, days_ago=5)]
        assert _calc_recent_winrate(old_matches, days=0) is None

    def test_all_wins(self):
        wins = [_make_match(i, is_win=True, days_ago=0) for i in range(5)]
        assert _calc_recent_winrate(wins, days=7) == 100.0

    def test_all_losses(self):
        losses = [_make_match(i, is_win=False, days_ago=0) for i in range(5)]
        assert _calc_recent_winrate(losses, days=7) == 0.0


# ---------------------------------------------------------------------------
# _calc_streaks
# ---------------------------------------------------------------------------


class TestCalcStreaks:
    def test_win_streak(self):
        # Первые 2 матча — победы
        win_s, loss_s = _calc_streaks(RECENT_MATCHES)
        assert win_s == 2
        assert loss_s == 0

    def test_loss_streak(self):
        matches = [
            _make_match(1, is_win=False, days_ago=0),
            _make_match(2, is_win=False, days_ago=1),
            _make_match(3, is_win=False, days_ago=2),
            _make_match(4, is_win=True, days_ago=3),
        ]
        win_s, loss_s = _calc_streaks(matches)
        assert win_s == 0
        assert loss_s == 3

    def test_no_streak(self):
        win_s, loss_s = _calc_streaks([])
        assert win_s == 0
        assert loss_s == 0

    def test_single_win(self):
        matches = [_make_match(1, is_win=True, days_ago=0)]
        win_s, loss_s = _calc_streaks(matches)
        assert win_s == 1
        assert loss_s == 0

    def test_single_loss(self):
        matches = [_make_match(1, is_win=False, days_ago=0)]
        win_s, loss_s = _calc_streaks(matches)
        assert win_s == 0
        assert loss_s == 1

    def test_alternating(self):
        matches = [
            _make_match(1, is_win=True, days_ago=0),
            _make_match(2, is_win=False, days_ago=1),
        ]
        win_s, loss_s = _calc_streaks(matches)
        assert win_s == 1
        assert loss_s == 0


# ---------------------------------------------------------------------------
# get_user_profile
# ---------------------------------------------------------------------------


class TestGetUserProfile:
    def test_returns_user_profile(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert isinstance(result, UserProfile)

    def test_current_mmr(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.current_mmr == 3500

    def test_rank_bracket(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.rank_bracket == RankBracket.LEGEND  # 3500 MMR

    def test_main_role(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.main_role == Role.CARRY

    def test_overall_winrate(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.overall_winrate is not None
        assert 0.0 <= result.overall_winrate <= 100.0

    def test_top_heroes_count(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert len(result.top_heroes) == 5

    def test_winrate_7d(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.winrate_7d is not None
        assert 0.0 <= result.winrate_7d <= 100.0

    def test_winrate_30d(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.winrate_30d is not None
        assert 0.0 <= result.winrate_30d <= 100.0

    def test_win_streak(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.win_streak == 2
        assert result.loss_streak == 0

    def test_total_matches(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.total_matches == 290  # 100+80+50+30+20+10

    def test_personaname(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.personaname == "TestPlayer"

    def test_no_steam_id_returns_minimal(self):
        opendota = AsyncMock()
        result = asyncio.run(get_user_profile(TEST_USER_NO_STEAM, opendota=opendota))
        assert result.current_mmr == 2000
        assert result.rank_bracket == RankBracket.CRUSADER  # 2000 MMR
        assert result.main_role == Role.OFFLANE
        assert result.overall_winrate is None
        assert result.top_heroes == []
        # OpenDota не вызывался
        opendota.get_player_heroes.assert_not_called()
        opendota.get_recent_matches.assert_not_called()

    def test_mmr_history_from_repo(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        mmr_repo = AsyncMock()
        mmr_repo.get_history = AsyncMock(return_value=[
            {"mmr": 3400, "recorded_at": "2026-02-25T12:00:00Z"},
            {"mmr": 3500, "recorded_at": "2026-02-28T12:00:00Z"},
        ])

        result = asyncio.run(
            get_user_profile(TEST_USER, opendota=opendota, mmr_repo=mmr_repo)
        )
        assert len(result.mmr_history) == 2
        assert result.mmr_history[0].mmr == 3400
        assert isinstance(result.mmr_history[0], MmrPoint)

    def test_mmr_history_without_repo(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=HERO_STATS)
        opendota.get_recent_matches = AsyncMock(return_value=RECENT_MATCHES)

        result = asyncio.run(get_user_profile(TEST_USER, opendota=opendota))
        assert result.mmr_history == []

    def test_no_mmr_no_bracket(self):
        user = {"id": 1, "steam_id": None, "current_mmr": None, "main_role": None}
        opendota = AsyncMock()
        result = asyncio.run(get_user_profile(user, opendota=opendota))
        assert result.rank_bracket is None
        assert result.main_role is None

    def test_invalid_role_fallback(self):
        user = {"id": 1, "steam_id": None, "current_mmr": 1000, "main_role": 99}
        opendota = AsyncMock()
        result = asyncio.run(get_user_profile(user, opendota=opendota))
        assert result.main_role is None

    def test_calls_opendota_with_account_id(self):
        opendota = AsyncMock()
        opendota.get_player_heroes = AsyncMock(return_value=[])
        opendota.get_recent_matches = AsyncMock(return_value=[])

        asyncio.run(get_user_profile(TEST_USER, opendota=opendota))

        # account_id = steam_id_64 - base = 86839040
        expected_account_id = 86839040
        opendota.get_player_heroes.assert_called_once_with(expected_account_id)
        opendota.get_recent_matches.assert_called_once_with(
            expected_account_id, limit=100
        )
