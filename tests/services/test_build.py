"""Тесты для services/build.py — сервис билдов героев."""

import asyncio
import time
from unittest.mock import AsyncMock

from clients.stratz import (
    AbilityInfo,
    HeroBuildData,
    HeroGuideData,
    ItemPurchase,
    TalentInfo,
)
from core.items import get_item_name_en, get_item_name_ru
from services.build import (
    BuildItem,
    HeroBuild,
    SkillSlot,
    TalentChoice,
    _assemble_build,
    _cache,
    _convert_items,
    _convert_talents,
    get_hero_build,
    invalidate_build_cache,
)

# ---------------------------------------------------------------------------
# Тестовые данные
# ---------------------------------------------------------------------------

STARTING_ITEMS = [
    ItemPurchase(item_id=44, match_count=5000, win_count=2750, was_given=True),  # Tango
    ItemPurchase(item_id=218, match_count=4000, win_count=2200),  # Iron Branch
    ItemPurchase(item_id=56, match_count=3500, win_count=1925),  # Quelling Blade
]

EARLY_ITEMS = [
    ItemPurchase(item_id=63, match_count=4500, win_count=2475, time=420),  # Power Treads
    ItemPurchase(item_id=226, match_count=3800, win_count=2090, time=780),  # Maelstrom
]

MID_ITEMS = [
    ItemPurchase(item_id=176, match_count=3200, win_count=1760, time=1200),  # Manta Style
    ItemPurchase(item_id=141, match_count=2800, win_count=1540, time=1500),  # BKB
    ItemPurchase(item_id=212, match_count=2500, win_count=1375, time=1800),  # Eye of Skadi
]

LATE_ITEMS = [
    ItemPurchase(item_id=196, match_count=1500, win_count=900, time=2400),  # Butterfly
    ItemPurchase(item_id=210, match_count=1200, win_count=720, time=2700),  # Satanic
    ItemPurchase(item_id=225, match_count=1000, win_count=600, time=2100),  # Mjollnir
]

ABILITY_ORDER = [
    AbilityInfo(ability_id=5003, slot=2),  # E
    AbilityInfo(ability_id=5001, slot=0),  # Q
    AbilityInfo(ability_id=5003, slot=2),  # E
    AbilityInfo(ability_id=5002, slot=1),  # W
]

TALENTS = [
    TalentInfo(ability_id=6001, slot=0, win_count=2000, match_count=4000),
    TalentInfo(ability_id=6002, slot=1, win_count=1800, match_count=3000),
    TalentInfo(ability_id=6003, slot=2, win_count=1500, match_count=2500),
    TalentInfo(ability_id=6004, slot=3, win_count=1200, match_count=2000),
]


def _make_build_data(hero_id: int = 1) -> HeroBuildData:
    return HeroBuildData(
        hero_id=hero_id,
        starting_items=STARTING_ITEMS,
        early_game=EARLY_ITEMS,
        mid_game=MID_ITEMS,
        late_game=LATE_ITEMS,
    )


def _make_guide_data(hero_id: int = 1) -> HeroGuideData:
    return HeroGuideData(
        hero_id=hero_id,
        match_count=5000,
        win_count=2750,
        ability_order=ABILITY_ORDER,
        talents=TALENTS,
    )


def _make_stratz_mock(
    build_data: HeroBuildData | None = None,
    guide_data: HeroGuideData | None = None,
) -> AsyncMock:
    stratz = AsyncMock()
    stratz.get_hero_build = AsyncMock(
        return_value=build_data or _make_build_data()
    )
    stratz.get_hero_guide = AsyncMock(
        return_value=guide_data or _make_guide_data()
    )
    return stratz


# ---------------------------------------------------------------------------
# _convert_items
# ---------------------------------------------------------------------------


class TestConvertItems:
    def test_converts_items_with_names(self):
        result = _convert_items(STARTING_ITEMS)
        assert len(result) == 3
        assert all(isinstance(i, BuildItem) for i in result)
        # Tango
        assert result[0].item_id == 44
        assert result[0].name_en == get_item_name_en(44)
        assert result[0].name_ru == get_item_name_ru(44)

    def test_winrate_calculated(self):
        result = _convert_items(STARTING_ITEMS)
        # Tango: 2750/5000 = 0.55
        assert abs(result[0].winrate - 0.55) < 0.01

    def test_time_preserved(self):
        result = _convert_items(EARLY_ITEMS)
        assert result[0].time == 420  # Power Treads

    def test_empty_list(self):
        result = _convert_items([])
        assert result == []

    def test_unknown_item_id(self):
        items = [ItemPurchase(item_id=99999, match_count=100, win_count=50)]
        result = _convert_items(items)
        assert len(result) == 1
        assert result[0].name_en == "Item #99999"
        assert result[0].name_ru == "Предмет #99999"


# ---------------------------------------------------------------------------
# _convert_talents
# ---------------------------------------------------------------------------


class TestConvertTalents:
    def test_converts_talents(self):
        result = _convert_talents(TALENTS)
        assert len(result) == 4
        assert all(isinstance(t, TalentChoice) for t in result)

    def test_sorted_by_slot(self):
        # Передадим в обратном порядке
        reversed_talents = list(reversed(TALENTS))
        result = _convert_talents(reversed_talents)
        slots = [t.slot for t in result]
        assert slots == [0, 1, 2, 3]

    def test_winrate_calculated(self):
        result = _convert_talents(TALENTS)
        # Слот 0: 2000/4000 = 0.5
        assert abs(result[0].winrate - 0.5) < 0.01

    def test_empty_list(self):
        result = _convert_talents([])
        assert result == []


# ---------------------------------------------------------------------------
# _assemble_build
# ---------------------------------------------------------------------------


class TestAssembleBuild:
    def test_returns_hero_build(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        assert isinstance(build, HeroBuild)
        assert build.hero_id == 1
        assert build.name_en == "Anti-Mage"
        assert build.name_ru == "Анти-Маг"

    def test_starting_items_filled(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        assert len(build.starting_items) == 3
        assert build.starting_items[0].item_id == 44  # Tango

    def test_core_items_from_early_and_mid(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        # early (2) + mid (3) = 5 уникальных, все < 6 → все core
        assert len(build.core_items) == 5
        core_ids = [i.item_id for i in build.core_items]
        assert 63 in core_ids  # Power Treads
        assert 176 in core_ids  # Manta Style

    def test_situational_items_from_late(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        # late items не дублируются с core → попадают в situational
        sit_ids = [i.item_id for i in build.situational_items]
        assert 196 in sit_ids  # Butterfly
        assert 210 in sit_ids  # Satanic

    def test_no_duplicate_items(self):
        # Добавим дубликат: item_id=63 в mid_game (уже есть в early_game)
        build_data = HeroBuildData(
            hero_id=1,
            starting_items=STARTING_ITEMS,
            early_game=EARLY_ITEMS,
            mid_game=[ItemPurchase(item_id=63, match_count=100, win_count=50)],
            late_game=LATE_ITEMS,
        )
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                build_data, _make_guide_data())
        # item_id=63 должен быть только один раз
        all_ids = ([i.item_id for i in build.core_items]
                   + [i.item_id for i in build.situational_items])
        assert all_ids.count(63) == 1

    def test_skill_order_filled(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        assert len(build.skill_order) == 4
        assert all(isinstance(s, SkillSlot) for s in build.skill_order)
        assert build.skill_order[0].slot == 2  # E первым

    def test_talents_filled(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        assert len(build.talents) == 4
        assert all(isinstance(t, TalentChoice) for t in build.talents)

    def test_guide_winrate(self):
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                _make_build_data(), _make_guide_data())
        # 2750/5000 = 0.55
        assert abs(build.guide_winrate - 0.55) < 0.01

    def test_empty_build_data(self):
        empty_build = HeroBuildData(hero_id=1)
        empty_guide = HeroGuideData(hero_id=1)
        build = _assemble_build(1, "Anti-Mage", "Анти-Маг",
                                empty_build, empty_guide)
        assert build.starting_items == []
        assert build.core_items == []
        assert build.situational_items == []
        assert build.skill_order == []
        assert build.talents == []


# ---------------------------------------------------------------------------
# get_hero_build (интеграционный)
# ---------------------------------------------------------------------------


class TestGetHeroBuild:
    def setup_method(self):
        invalidate_build_cache()

    def test_returns_hero_build(self):
        stratz = _make_stratz_mock()
        result = asyncio.run(get_hero_build(1, stratz=stratz))
        assert isinstance(result, HeroBuild)
        assert result.hero_id == 1
        assert result.name_ru == "Анти-Маг"

    def test_calls_stratz_with_params(self):
        stratz = _make_stratz_mock()
        asyncio.run(get_hero_build(1, role=1, bracket="LEGEND", stratz=stratz))
        stratz.get_hero_build.assert_called_once_with(1, 1, "LEGEND")
        stratz.get_hero_guide.assert_called_once_with(1, 1, "LEGEND")

    def test_calls_without_role_bracket(self):
        stratz = _make_stratz_mock()
        asyncio.run(get_hero_build(1, stratz=stratz))
        stratz.get_hero_build.assert_called_once_with(1, None, None)
        stratz.get_hero_guide.assert_called_once_with(1, None, None)

    def test_starting_items_filled(self):
        stratz = _make_stratz_mock()
        result = asyncio.run(get_hero_build(1, stratz=stratz))
        assert len(result.starting_items) == 3

    def test_core_items_filled(self):
        stratz = _make_stratz_mock()
        result = asyncio.run(get_hero_build(1, stratz=stratz))
        assert len(result.core_items) > 0

    def test_skill_order_filled(self):
        stratz = _make_stratz_mock()
        result = asyncio.run(get_hero_build(1, stratz=stratz))
        assert len(result.skill_order) == 4

    def test_talents_filled(self):
        stratz = _make_stratz_mock()
        result = asyncio.run(get_hero_build(1, stratz=stratz))
        assert len(result.talents) == 4

    def test_caching_second_call_no_api(self):
        stratz = _make_stratz_mock()
        invalidate_build_cache()
        asyncio.run(get_hero_build(1, role=1, bracket="LEGEND", stratz=stratz))
        asyncio.run(get_hero_build(1, role=1, bracket="LEGEND", stratz=stratz))
        # API вызван только один раз
        assert stratz.get_hero_build.call_count == 1
        assert stratz.get_hero_guide.call_count == 1

    def test_different_params_not_cached(self):
        stratz = _make_stratz_mock()
        invalidate_build_cache()
        asyncio.run(get_hero_build(1, role=1, bracket="LEGEND", stratz=stratz))
        asyncio.run(get_hero_build(1, role=2, bracket="DIVINE", stratz=stratz))
        assert stratz.get_hero_build.call_count == 2

    def test_cache_invalidation(self):
        stratz = _make_stratz_mock()
        invalidate_build_cache()
        asyncio.run(get_hero_build(1, stratz=stratz))
        invalidate_build_cache()
        asyncio.run(get_hero_build(1, stratz=stratz))
        assert stratz.get_hero_build.call_count == 2


# ---------------------------------------------------------------------------
# invalidate_build_cache
# ---------------------------------------------------------------------------


class TestInvalidateBuildCache:
    def test_clears_cache(self):
        _cache["test_key"] = (time.monotonic(), HeroBuild(
            hero_id=1, name_en="Test", name_ru="Тест",
        ))
        assert len(_cache) > 0
        invalidate_build_cache()
        assert len(_cache) == 0


# ---------------------------------------------------------------------------
# core/items.py — тесты маппинга предметов
# ---------------------------------------------------------------------------


class TestItemMapping:
    def test_known_item_en(self):
        assert get_item_name_en(141) == "Black King Bar"

    def test_known_item_ru(self):
        assert get_item_name_ru(141) == "Посох Чёрного Короля"

    def test_unknown_item_en(self):
        assert get_item_name_en(99999) == "Item #99999"

    def test_unknown_item_ru(self):
        assert get_item_name_ru(99999) == "Предмет #99999"

    def test_tango(self):
        assert get_item_name_en(44) == "Tango"
        assert get_item_name_ru(44) == "Танго"
