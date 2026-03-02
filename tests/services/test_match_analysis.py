"""Тесты для services/match_analysis.py — сервис анализа матча."""

import asyncio
import sys
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

from clients.opendota import MatchDetails, RecentMatch  # noqa: E402
from core.enums import MatchOutcome, Role  # noqa: E402
from services.match_analysis import (  # noqa: E402
    MatchAnalysis,
    RoleMetric,
    _build_metrics,
    _detect_role,
    _determine_result,
    _find_player_in_match,
    _scale_median_by_duration,
    analyze_last_match,
)

# ---------------------------------------------------------------------------
# Тестовые данные
# ---------------------------------------------------------------------------

_STEAM_ID_64 = 76561198047104768
_ACCOUNT_ID = 86839040  # = _STEAM_ID_64 - 76561197960265728

_PLAYER_DATA_CARRY = {
    "account_id": _ACCOUNT_ID,
    "hero_id": 1,
    "player_slot": 0,  # radiant
    "lane_role": 1,
    "last_hits": 300,
    "kills": 12,
    "deaths": 3,
    "assists": 8,
    "gold_per_min": 650,
    "xp_per_min": 700,
    "hero_damage": 25000,
    "tower_damage": 6000,
    "hero_healing": 0,
    "obs_placed": 0,
    "sen_placed": 0,
    "stuns": 10,
    "duration": 1800,
}

_PLAYER_DATA_SUPPORT = {
    "account_id": _ACCOUNT_ID,
    "hero_id": 5,
    "player_slot": 132,  # dire
    "lane_role": 1,
    "last_hits": 30,
    "kills": 2,
    "deaths": 8,
    "assists": 22,
    "gold_per_min": 250,
    "xp_per_min": 350,
    "hero_damage": 5000,
    "tower_damage": 200,
    "hero_healing": 8000,
    "obs_placed": 15,
    "sen_placed": 12,
    "stuns": 45,
    "duration": 1800,
}

_PLAYER_DATA_MID = {
    "account_id": _ACCOUNT_ID,
    "hero_id": 11,
    "player_slot": 1,
    "lane_role": 2,
    "last_hits": 250,
    "kills": 15,
    "deaths": 4,
    "assists": 10,
    "gold_per_min": 600,
    "xp_per_min": 750,
    "hero_damage": 30000,
    "tower_damage": 5000,
    "hero_healing": 0,
    "obs_placed": 1,
    "sen_placed": 0,
    "stuns": 20,
    "duration": 1800,
}

_PLAYER_DATA_ROAMING = {
    "account_id": _ACCOUNT_ID,
    "hero_id": 7,
    "player_slot": 3,
    "lane_role": 3,
    "is_roaming": True,
    "last_hits": 50,
    "kills": 5,
    "deaths": 6,
    "assists": 18,
    "gold_per_min": 300,
    "xp_per_min": 400,
    "hero_damage": 12000,
    "tower_damage": 1000,
    "hero_healing": 0,
    "obs_placed": 6,
    "sen_placed": 4,
    "stuns": 60,
    "duration": 1800,
}

_PLAYER_DATA_OFFLANE = {
    "account_id": _ACCOUNT_ID,
    "hero_id": 44,
    "player_slot": 2,
    "lane_role": 3,
    "last_hits": 180,
    "kills": 7,
    "deaths": 5,
    "assists": 15,
    "gold_per_min": 480,
    "xp_per_min": 580,
    "hero_damage": 22000,
    "tower_damage": 3500,
    "hero_healing": 0,
    "obs_placed": 2,
    "sen_placed": 1,
    "stuns": 70,
    "duration": 1800,
}

_MATCH_DETAILS = MatchDetails(
    match_id=7000000001,
    radiant_win=True,
    duration=1800,
    start_time=1700000000,
    game_mode=22,
    lobby_type=7,
    radiant_score=30,
    dire_score=20,
    players=[_PLAYER_DATA_CARRY],
)

_RECENT_MATCH = RecentMatch(
    match_id=7000000001,
    hero_id=1,
    player_slot=0,
    radiant_win=True,
    duration=1800,
    game_mode=22,
    lobby_type=7,
    start_time=1700000000,
    kills=12,
    deaths=3,
    assists=8,
)


# ---------------------------------------------------------------------------
# _detect_role
# ---------------------------------------------------------------------------


class TestDetectRole:
    def test_carry_on_safe_lane_with_high_cs(self):
        assert _detect_role(_PLAYER_DATA_CARRY) == Role.CARRY

    def test_support_on_safe_lane_with_low_cs(self):
        assert _detect_role(_PLAYER_DATA_SUPPORT) == Role.HARD_SUPPORT

    def test_mid(self):
        assert _detect_role(_PLAYER_DATA_MID) == Role.MID

    def test_offlane_with_high_cs(self):
        assert _detect_role(_PLAYER_DATA_OFFLANE) == Role.OFFLANE

    def test_offlane_with_low_cs_is_soft_support(self):
        data = {**_PLAYER_DATA_OFFLANE, "last_hits": 30}
        assert _detect_role(data) == Role.SOFT_SUPPORT

    def test_roaming_is_soft_support(self):
        assert _detect_role(_PLAYER_DATA_ROAMING) == Role.SOFT_SUPPORT

    def test_no_lane_role_returns_none(self):
        data = {"account_id": _ACCOUNT_ID}
        assert _detect_role(data) is None

    def test_unknown_lane_role_returns_none(self):
        data = {"account_id": _ACCOUNT_ID, "lane_role": 99}
        assert _detect_role(data) is None


# ---------------------------------------------------------------------------
# _determine_result
# ---------------------------------------------------------------------------


class TestDetermineResult:
    def test_radiant_win_radiant_player(self):
        result = _determine_result({"player_slot": 0}, radiant_win=True)
        assert result == MatchOutcome.WIN

    def test_radiant_win_dire_player(self):
        result = _determine_result({"player_slot": 128}, radiant_win=True)
        assert result == MatchOutcome.LOSS

    def test_dire_win_dire_player(self):
        result = _determine_result({"player_slot": 132}, radiant_win=False)
        assert result == MatchOutcome.WIN

    def test_dire_win_radiant_player(self):
        result = _determine_result({"player_slot": 4}, radiant_win=False)
        assert result == MatchOutcome.LOSS


# ---------------------------------------------------------------------------
# _find_player_in_match
# ---------------------------------------------------------------------------


class TestFindPlayerInMatch:
    def test_finds_player(self):
        player = _find_player_in_match(_MATCH_DETAILS, _ACCOUNT_ID)
        assert player is not None
        assert player["account_id"] == _ACCOUNT_ID

    def test_returns_none_for_unknown(self):
        player = _find_player_in_match(_MATCH_DETAILS, 999999)
        assert player is None

    def test_empty_players(self):
        match = MatchDetails(
            match_id=1, radiant_win=True, duration=0,
            start_time=0, game_mode=0, lobby_type=0, players=[],
        )
        assert _find_player_in_match(match, _ACCOUNT_ID) is None


# ---------------------------------------------------------------------------
# _scale_median_by_duration
# ---------------------------------------------------------------------------


class TestScaleMedianByDuration:
    def test_gpm_not_scaled(self):
        assert _scale_median_by_duration(550, 3600, "gold_per_min") == 550

    def test_xpm_not_scaled(self):
        assert _scale_median_by_duration(600, 3600, "xp_per_min") == 600

    def test_kills_scaled_to_60min(self):
        # 30мин стандарт, 60мин матч → x2
        result = _scale_median_by_duration(8, 3600, "kills")
        assert result == 16.0

    def test_kills_scaled_to_15min(self):
        # 30мин стандарт, 15мин матч → x0.5
        result = _scale_median_by_duration(8, 900, "kills")
        assert result == 4.0

    def test_standard_duration(self):
        result = _scale_median_by_duration(8, 1800, "kills")
        assert result == 8.0


# ---------------------------------------------------------------------------
# _build_metrics
# ---------------------------------------------------------------------------


class TestBuildMetrics:
    def test_carry_metrics(self):
        metrics = _build_metrics(_PLAYER_DATA_CARRY, Role.CARRY, 1800)
        names = [m.name for m in metrics]
        assert "gold_per_min" in names
        assert "xp_per_min" in names
        assert "last_hits" in names
        assert "hero_damage" in names
        assert "tower_damage" in names

    def test_carry_no_wards(self):
        metrics = _build_metrics(_PLAYER_DATA_CARRY, Role.CARRY, 1800)
        names = [m.name for m in metrics]
        assert "obs_placed" not in names
        assert "sen_placed" not in names

    def test_support_metrics(self):
        metrics = _build_metrics(_PLAYER_DATA_SUPPORT, Role.HARD_SUPPORT, 1800)
        names = [m.name for m in metrics]
        assert "obs_placed" in names
        assert "sen_placed" in names
        assert "hero_healing" in names

    def test_support_no_gpm(self):
        metrics = _build_metrics(_PLAYER_DATA_SUPPORT, Role.HARD_SUPPORT, 1800)
        names = [m.name for m in metrics]
        assert "gold_per_min" not in names

    def test_metric_values_from_player_data(self):
        metrics = _build_metrics(_PLAYER_DATA_CARRY, Role.CARRY, 1800)
        gpm = next(m for m in metrics if m.name == "gold_per_min")
        assert gpm.value == 650
        assert gpm.median == 550  # стандартная медиана

    def test_median_scaled_for_long_match(self):
        metrics = _build_metrics(_PLAYER_DATA_CARRY, Role.CARRY, 3600)
        lh = next(m for m in metrics if m.name == "last_hits")
        # 250 медиана * (3600/1800) = 500
        assert lh.median == 500.0


# ---------------------------------------------------------------------------
# RoleMetric
# ---------------------------------------------------------------------------


class TestRoleMetric:
    def test_diff_positive(self):
        m = RoleMetric(name="gpm", label_ru="GPM", value=650, median=550)
        assert m.diff == 100

    def test_diff_negative(self):
        m = RoleMetric(name="gpm", label_ru="GPM", value=400, median=550)
        assert m.diff == -150

    def test_diff_pct(self):
        m = RoleMetric(name="gpm", label_ru="GPM", value=660, median=600)
        assert abs(m.diff_pct - 10.0) < 0.01

    def test_diff_pct_zero_median(self):
        m = RoleMetric(name="x", label_ru="X", value=10, median=0)
        assert m.diff_pct == 0.0


# ---------------------------------------------------------------------------
# analyze_last_match
# ---------------------------------------------------------------------------


class TestAnalyzeLastMatch:
    def _make_opendota(
        self,
        recent_matches=None,
        match_details=None,
    ):
        mock = AsyncMock()
        mock.get_recent_matches = AsyncMock(
            return_value=recent_matches if recent_matches is not None else [_RECENT_MATCH]
        )
        mock.get_match = AsyncMock(
            return_value=match_details if match_details is not None else _MATCH_DETAILS
        )
        return mock

    def test_returns_match_analysis(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert isinstance(result, MatchAnalysis)
        assert result.match_id == 7000000001

    def test_hero_info_filled(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.hero_id == 1
        assert result.hero_name_ru  # не пустое
        assert result.hero_name_en  # не пустое

    def test_role_detected_as_carry(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.role == Role.CARRY
        assert result.role_detected is True

    def test_result_is_win(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.result == MatchOutcome.WIN

    def test_result_is_loss(self):
        match = MatchDetails(
            match_id=7000000001,
            radiant_win=False,
            duration=1800,
            start_time=1700000000,
            game_mode=22,
            lobby_type=7,
            players=[_PLAYER_DATA_CARRY],
        )
        opendota = self._make_opendota(match_details=match)
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.result == MatchOutcome.LOSS

    def test_metrics_for_carry(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        names = [m.name for m in result.metrics]
        assert "gold_per_min" in names
        assert "obs_placed" not in names

    def test_kda_filled(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.kills == 12
        assert result.deaths == 3
        assert result.assists == 8

    def test_no_recent_matches_raises(self):
        opendota = self._make_opendota(recent_matches=[])
        try:
            asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
            assert False, "Должен был бросить ValueError"
        except ValueError as e:
            assert "нет недавних матчей" in str(e).lower()

    def test_player_not_in_match_raises(self):
        match = MatchDetails(
            match_id=7000000001,
            radiant_win=True,
            duration=1800,
            start_time=0,
            game_mode=22,
            lobby_type=7,
            players=[{"account_id": 999999}],
        )
        opendota = self._make_opendota(match_details=match)
        try:
            asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
            assert False, "Должен был бросить ValueError"
        except ValueError as e:
            assert "не найден" in str(e).lower()

    def test_fallback_role_when_not_detected(self):
        player = {**_PLAYER_DATA_CARRY, "lane_role": None}
        match = MatchDetails(
            match_id=7000000001,
            radiant_win=True,
            duration=1800,
            start_time=0,
            game_mode=22,
            lobby_type=7,
            players=[player],
        )
        opendota = self._make_opendota(match_details=match)
        result = asyncio.run(
            analyze_last_match(
                _STEAM_ID_64, opendota=opendota, user_role=Role.MID,
            )
        )
        assert result.role == Role.MID
        assert result.role_detected is False

    def test_default_role_carry_when_nothing(self):
        player = {**_PLAYER_DATA_CARRY, "lane_role": None}
        match = MatchDetails(
            match_id=7000000001,
            radiant_win=True,
            duration=1800,
            start_time=0,
            game_mode=22,
            lobby_type=7,
            players=[player],
        )
        opendota = self._make_opendota(match_details=match)
        result = asyncio.run(
            analyze_last_match(_STEAM_ID_64, opendota=opendota)
        )
        assert result.role == Role.CARRY
        assert result.role_detected is False

    def test_saves_to_repo_when_provided(self):
        repo = AsyncMock()
        repo.insert = AsyncMock(return_value={"id": 1})
        opendota = self._make_opendota()
        asyncio.run(
            analyze_last_match(
                _STEAM_ID_64,
                opendota=opendota,
                match_repo=repo,
                user_id=42,
            )
        )
        repo.insert.assert_called_once()
        call_kwargs = repo.insert.call_args[1]
        assert call_kwargs["user_id"] == 42
        assert call_kwargs["match_id"] == 7000000001
        assert call_kwargs["hero_id"] == 1
        assert call_kwargs["role"] == 1
        assert call_kwargs["result"] == "win"
        assert isinstance(call_kwargs["stats"], dict)

    def test_does_not_save_without_repo(self):
        opendota = self._make_opendota()
        # Не должен падать без repo
        result = asyncio.run(
            analyze_last_match(_STEAM_ID_64, opendota=opendota)
        )
        assert result.match_id == 7000000001

    def test_does_not_save_without_user_id(self):
        repo = AsyncMock()
        opendota = self._make_opendota()
        asyncio.run(
            analyze_last_match(
                _STEAM_ID_64,
                opendota=opendota,
                match_repo=repo,
            )
        )
        repo.insert.assert_not_called()

    def test_support_role_detected(self):
        match = MatchDetails(
            match_id=7000000001,
            radiant_win=False,
            duration=1800,
            start_time=0,
            game_mode=22,
            lobby_type=7,
            players=[_PLAYER_DATA_SUPPORT],
        )
        opendota = self._make_opendota(match_details=match)
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.role == Role.HARD_SUPPORT
        names = [m.name for m in result.metrics]
        assert "obs_placed" in names
        assert "gold_per_min" not in names

    def test_duration_in_result(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        assert result.duration_sec == 1800

    def test_median_comparison_present(self):
        opendota = self._make_opendota()
        result = asyncio.run(analyze_last_match(_STEAM_ID_64, opendota=opendota))
        for m in result.metrics:
            assert m.median >= 0, f"Медиана {m.name} должна быть >= 0"
