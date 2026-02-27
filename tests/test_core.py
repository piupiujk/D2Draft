"""Тесты для core-модулей: hero_mapping, enums, constants, exceptions."""

import pytest

from core.constants import HERO_BY_ID, HEROES, TOTAL_HEROES
from core.enums import MatchOutcome, RankBracket, Role, SubscriptionPlan
from core.exceptions import HeroNotFound
from core.hero_mapping import (
    find_hero,
    get_hero_by_id,
    get_hero_id_by_name,
    get_name_en,
    get_name_ru,
)

# --- Тесты hero_mapping ---


class TestFindHero:
    """Поиск героя по имени EN, RU и сокращению."""

    def test_find_by_english_name(self):
        hero = find_hero("Anti-Mage")
        assert hero.hero_id == 1
        assert hero.name_en == "Anti-Mage"

    def test_find_by_russian_name(self):
        hero = find_hero("Анти-Маг")
        assert hero.hero_id == 1

    def test_find_by_alias(self):
        hero = find_hero("am")
        assert hero.hero_id == 1

    def test_find_case_insensitive(self):
        hero1 = find_hero("anti-mage")
        hero2 = find_hero("ANTI-MAGE")
        hero3 = find_hero("Anti-Mage")
        assert hero1.hero_id == hero2.hero_id == hero3.hero_id == 1

    def test_all_three_return_same_id(self):
        """Anti-Mage, Анти-Маг, am — все возвращают одинаковый hero_id."""
        id_en = get_hero_id_by_name("Anti-Mage")
        id_ru = get_hero_id_by_name("Анти-Маг")
        id_alias = get_hero_id_by_name("am")
        assert id_en == id_ru == id_alias == 1

    def test_find_by_numeric_id(self):
        hero = find_hero("14")
        assert hero.name_en == "Pudge"

    def test_find_pudge(self):
        hero = find_hero("Pudge")
        assert hero.hero_id == 14
        assert hero.name_ru == "Пудж"

    def test_find_invoker_alias(self):
        hero = find_hero("инвок")
        assert hero.hero_id == 74

    def test_find_qop_alias(self):
        hero = find_hero("qop")
        assert hero.hero_id == 39

    def test_find_nonexistent_raises(self):
        with pytest.raises(HeroNotFound):
            find_hero("НесуществующийГерой")

    def test_find_invalid_id_raises(self):
        with pytest.raises(HeroNotFound):
            find_hero("99999")

    def test_strip_whitespace(self):
        hero = find_hero("  Pudge  ")
        assert hero.hero_id == 14


class TestGetNameFunctions:
    """Получение имён по ID."""

    def test_get_name_en(self):
        assert get_name_en(14) == "Pudge"

    def test_get_name_ru(self):
        assert get_name_ru(14) == "Пудж"

    def test_get_hero_by_id_invalid(self):
        with pytest.raises(HeroNotFound):
            get_hero_by_id(9999)


# --- Тесты constants ---


class TestConstants:
    """Полнота списка героев."""

    def test_total_heroes_at_least_124(self):
        assert TOTAL_HEROES >= 124

    def test_all_heroes_have_unique_ids(self):
        ids = [h.hero_id for h in HEROES]
        assert len(ids) == len(set(ids))

    def test_all_heroes_in_index(self):
        for hero in HEROES:
            assert hero.hero_id in HERO_BY_ID

    def test_hero_data_fields(self):
        hero = HERO_BY_ID[1]
        assert hero.hero_id == 1
        assert isinstance(hero.name_en, str)
        assert isinstance(hero.name_ru, str)
        assert len(hero.name_en) > 0
        assert len(hero.name_ru) > 0


# --- Тесты enums ---


class TestRoleEnum:
    """Перечисление Role содержит значения 1-5."""

    def test_role_values(self):
        assert Role.CARRY == 1
        assert Role.MID == 2
        assert Role.OFFLANE == 3
        assert Role.SOFT_SUPPORT == 4
        assert Role.HARD_SUPPORT == 5

    def test_role_labels_ru(self):
        assert Role.CARRY.label_ru == "Керри"
        assert Role.HARD_SUPPORT.label_ru == "Хард-саппорт"

    def test_role_labels_en(self):
        assert Role.CARRY.label_en == "Carry"
        assert Role.HARD_SUPPORT.label_en == "Hard Support"

    def test_role_count(self):
        assert len(Role) == 5


class TestOtherEnums:
    """Проверка остальных перечислений."""

    def test_rank_brackets(self):
        assert len(RankBracket) == 8
        assert RankBracket.IMMORTAL == "IMMORTAL"

    def test_subscription_plans(self):
        assert SubscriptionPlan.FREE == "free"
        assert len(SubscriptionPlan) == 3

    def test_match_outcome(self):
        assert MatchOutcome.WIN == "win"
        assert MatchOutcome.LOSS == "loss"
