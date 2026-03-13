"""Тесты для services/meta.py — сервис мета-героев."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from clients.opendota import PlayerHeroStats
from clients.stratz import MetaHeroStats
from core.enums import RankBracket, Role
from services.meta import (
    MetaHero,
    _build_meta_list,
    _cache,
    _enrich_with_personal,
    get_meta_heroes,
    invalidate_meta_cache,
    mmr_to_bracket,
)

# ---------------------------------------------------------------------------
# Тестовые данные
# ---------------------------------------------------------------------------

STRATZ_META_HEROES = [
    MetaHeroStats(hero_id=1, match_count=5000, win_count=2800),  # 56%
    MetaHeroStats(hero_id=2, match_count=4000, win_count=2000),  # 50%
    MetaHeroStats(hero_id=8, match_count=6000, win_count=3300),  # 55%
    MetaHeroStats(hero_id=11, match_count=3000, win_count=1650),  # 55%
    MetaHeroStats(hero_id=44, match_count=7000, win_count=3850),  # 55%
]

PERSONAL_HERO_STATS = [
    PlayerHeroStats(hero_id=1, games=50, win=30),  # 60%
    PlayerHeroStats(hero_id=8, games=100, win=55),  # 55%
    PlayerHeroStats(hero_id=99, games=20, win=12),  # 60%, не в мете
]


# ---------------------------------------------------------------------------
# mmr_to_bracket
# ---------------------------------------------------------------------------


class TestMmrToBracket:
    def test_herald(self):
        assert mmr_to_bracket(0) == RankBracket.HERALD
        assert mmr_to_bracket(500) == RankBracket.HERALD

    def test_guardian(self):
        assert mmr_to_bracket(770) == RankBracket.GUARDIAN
        assert mmr_to_bracket(1000) == RankBracket.GUARDIAN

    def test_crusader(self):
        assert mmr_to_bracket(1540) == RankBracket.CRUSADER

    def test_archon(self):
        assert mmr_to_bracket(2310) == RankBracket.ARCHON

    def test_legend(self):
        assert mmr_to_bracket(3080) == RankBracket.LEGEND

    def test_ancient(self):
        assert mmr_to_bracket(3850) == RankBracket.ANCIENT

    def test_divine(self):
        assert mmr_to_bracket(4620) == RankBracket.DIVINE

    def test_immortal(self):
        assert mmr_to_bracket(5420) == RankBracket.IMMORTAL
        assert mmr_to_bracket(10000) == RankBracket.IMMORTAL


# ---------------------------------------------------------------------------
# _build_meta_list
# ---------------------------------------------------------------------------


class TestBuildMetaList:
    def test_returns_sorted_by_meta_score(self):
        result = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        assert len(result) > 0
        # Результат отсортирован по meta_score (убывание)
        scores = [h.meta_score for h in result]
        assert scores == sorted(scores, reverse=True)

    def test_first_hero_has_highest_meta_score(self):
        result = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        # Первый герой имеет наивысший meta_score
        assert result[0].meta_score == max(h.meta_score for h in result)

    def test_pick_rate_calculated(self):
        result = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        total = sum(h.match_count for h in STRATZ_META_HEROES)
        for hero in result:
            expected_pick_rate = hero.match_count / total
            assert abs(hero.pick_rate - expected_pick_rate) < 0.0001

    def test_names_filled(self):
        result = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        for hero in result:
            assert hero.name_ru != ""
            assert hero.name_en != ""

    def test_top_n_limits_result(self):
        result = _build_meta_list(STRATZ_META_HEROES, top_n=2)
        assert len(result) == 2

    def test_empty_input(self):
        result = _build_meta_list([], top_n=10)
        assert result == []

    def test_skips_unknown_hero_ids(self):
        bad_heroes = [MetaHeroStats(hero_id=99999, match_count=100, win_count=50)]
        result = _build_meta_list(bad_heroes, top_n=10)
        assert len(result) == 0

    def test_personal_winrate_is_none_by_default(self):
        result = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        for hero in result:
            assert hero.personal_winrate is None
            assert hero.personal_games is None


# ---------------------------------------------------------------------------
# _enrich_with_personal
# ---------------------------------------------------------------------------


class TestEnrichWithPersonal:
    def test_enriches_matching_heroes(self):
        base = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        result = _enrich_with_personal(base, PERSONAL_HERO_STATS)
        # hero_id=1 должен иметь personal_winrate
        hero_1 = next(h for h in result if h.hero_id == 1)
        assert hero_1.personal_winrate is not None
        assert abs(hero_1.personal_winrate - 0.6) < 0.001
        assert hero_1.personal_games == 50

    def test_non_matching_heroes_stay_none(self):
        base = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        result = _enrich_with_personal(base, PERSONAL_HERO_STATS)
        # hero_id=2 не в personal stats
        hero_2 = next(h for h in result if h.hero_id == 2)
        assert hero_2.personal_winrate is None
        assert hero_2.personal_games is None

    def test_preserves_meta_data(self):
        base = _build_meta_list(STRATZ_META_HEROES, top_n=10)
        result = _enrich_with_personal(base, PERSONAL_HERO_STATS)
        for i, hero in enumerate(result):
            assert hero.hero_id == base[i].hero_id
            assert hero.winrate == base[i].winrate
            assert hero.pick_rate == base[i].pick_rate


# ---------------------------------------------------------------------------
# get_meta_heroes (интеграционный)
# ---------------------------------------------------------------------------


class TestGetMetaHeroes:
    def setup_method(self):
        invalidate_meta_cache()

    def test_returns_meta_heroes(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)

        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )

        assert len(result) > 0
        assert all(isinstance(h, MetaHero) for h in result)
        stratz.get_meta_heroes.assert_called_once_with(Role.CARRY, RankBracket.LEGEND)

    def test_winrate_positive(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)

        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )

        for hero in result:
            assert hero.winrate > 0

    def test_names_in_russian(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)

        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )

        for hero in result:
            assert hero.name_ru != ""

    def test_caching_second_call_no_api(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)

        # Первый вызов — из API
        asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )
        # Второй вызов — из кэша
        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )

        assert len(result) > 0
        # API вызван только один раз
        assert stratz.get_meta_heroes.call_count == 1

    def test_different_params_not_cached(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)

        asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )
        asyncio.run(
            get_meta_heroes(
                role=Role.MID,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
            )
        )

        assert stratz.get_meta_heroes.call_count == 2

    def test_enrichment_with_opendota(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)
        opendota = MagicMock()
        opendota.get_player_heroes = AsyncMock(return_value=PERSONAL_HERO_STATS)

        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
                opendota=opendota,
                account_id=123456,
            )
        )

        # hero_id=1 должен быть обогащён
        hero_1 = next(h for h in result if h.hero_id == 1)
        assert hero_1.personal_winrate is not None
        opendota.get_player_heroes.assert_called_once_with(123456)

    def test_no_enrichment_without_account_id(self):
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=STRATZ_META_HEROES)
        opendota = MagicMock()

        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
                opendota=opendota,
                account_id=None,
            )
        )

        for hero in result:
            assert hero.personal_winrate is None
        opendota.get_player_heroes.assert_not_called()

    def test_top_n_default_10(self):
        # Создаём 15 мета-героев
        many_heroes = [
            MetaHeroStats(hero_id=i, match_count=1000, win_count=500 + i)
            for i in range(1, 16)
            if i not in (15,)  # hero_id=15 может не быть в маппинге
        ]
        stratz = MagicMock()
        stratz.get_meta_heroes = AsyncMock(return_value=many_heroes)

        result = asyncio.run(
            get_meta_heroes(
                role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=stratz,
                top_n=10,
            )
        )

        assert len(result) <= 10


# ---------------------------------------------------------------------------
# invalidate_meta_cache
# ---------------------------------------------------------------------------


class TestInvalidateCache:
    def test_clears_cache(self):
        _cache["test_key"] = (time.monotonic(), [])
        assert len(_cache) > 0
        invalidate_meta_cache()
        assert len(_cache) == 0
