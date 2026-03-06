"""Сервис билдов: получение item build и skill build героя из Stratz."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from clients.stratz import (
    HeroBuildData,
    HeroGuideData,
    ItemPurchase,
    StratzClient,
    TalentInfo,
)
from core.enums import RankBracket, Role
from core.hero_mapping import get_hero_by_id
from core.items import get_item_name_en, get_item_name_ru

# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------


@dataclass
class BuildItem:
    """Предмет в билде с именами на двух языках."""

    item_id: int
    name_en: str
    name_ru: str
    winrate: float  # 0.0 — 1.0
    match_count: int
    time: int | None = None  # Среднее время покупки (секунды), None для стартовых


@dataclass
class SkillSlot:
    """Один слот в порядке прокачки скиллов."""

    ability_id: int
    slot: int  # 0-3: Q/W/E/R (ult)


@dataclass
class TalentChoice:
    """Выбранный талант."""

    ability_id: int
    slot: int
    winrate: float  # 0.0 — 1.0
    match_count: int


@dataclass
class HeroBuild:
    """Полный билд героя: предметы, скиллы, таланты."""

    hero_id: int
    name_en: str
    name_ru: str
    starting_items: list[BuildItem] = field(default_factory=list)
    core_items: list[BuildItem] = field(default_factory=list)
    situational_items: list[BuildItem] = field(default_factory=list)
    skill_order: list[SkillSlot] = field(default_factory=list)
    talents: list[TalentChoice] = field(default_factory=list)
    guide_winrate: float = 0.0  # Винрейт гайда


# ---------------------------------------------------------------------------
# Кэш (in-memory с TTL)
# ---------------------------------------------------------------------------

_CACHE_TTL = 3600  # 1 час
_cache: dict[str, tuple[float, HeroBuild]] = {}


def _cache_key(hero_id: int, role: int | None, bracket: str | None) -> str:
    return f"build:{hero_id}:{role}:{bracket}"


def _get_cached(key: str) -> HeroBuild | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _set_cached(key: str, data: HeroBuild) -> None:
    _cache[key] = (time.monotonic(), data)


def invalidate_build_cache() -> None:
    """Сбросить весь кэш билдов."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


async def get_hero_build(
    hero_id: int,
    role: Role | int | None = None,
    bracket: RankBracket | str | None = None,
    *,
    stratz: StratzClient,
) -> HeroBuild:
    """Получить полный билд героя: предметы, порядок скиллов, таланты.

    Args:
        hero_id: ID героя.
        role: Роль (1-5). Если None — без фильтра по роли.
        bracket: Ранговый брекет. Если None — без фильтра по рангу.
        stratz: Клиент Stratz API.

    Returns:
        HeroBuild с starting_items, core_items, situational_items,
        skill_order и talents.
    """
    role_val = int(Role(role)) if role is not None else None
    bracket_val = str(RankBracket(bracket)) if bracket is not None else None
    key = _cache_key(hero_id, role_val, bracket_val)

    cached = _get_cached(key)
    if cached is not None:
        return cached

    # Получаем item build из Stratz
    build_data = await stratz.get_hero_build(hero_id, role, bracket)
    # Guide API изменился — скиллы/таланты временно недоступны
    guide_data = HeroGuideData(hero_id=hero_id)

    hero_data = get_hero_by_id(hero_id)

    result = _assemble_build(hero_id, hero_data.name_en, hero_data.name_ru,
                             build_data, guide_data)

    _set_cached(key, result)
    return result


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

# Количество core-предметов (основных) — остальные считаются ситуативными
_CORE_ITEMS_COUNT = 6


def _assemble_build(
    hero_id: int,
    name_en: str,
    name_ru: str,
    build_data: HeroBuildData,
    guide_data: HeroGuideData,
) -> HeroBuild:
    """Собрать HeroBuild из сырых данных Stratz."""
    starting = _convert_items(build_data.starting_items)

    # core_items = early_game + mid_game (основные предметы по порядку покупки)
    all_main = _convert_items(build_data.early_game) + _convert_items(build_data.mid_game)

    # Убираем дубликаты (по item_id), сохраняя порядок
    seen: set[int] = set()
    unique_main: list[BuildItem] = []
    for item in all_main:
        if item.item_id not in seen:
            seen.add(item.item_id)
            unique_main.append(item)

    core = unique_main[:_CORE_ITEMS_COUNT]
    situational_from_main = unique_main[_CORE_ITEMS_COUNT:]

    # late_game → ситуативные предметы
    late = _convert_items(build_data.late_game)
    # Убираем дубликаты с core
    for item in late:
        if item.item_id not in seen:
            seen.add(item.item_id)
            situational_from_main.append(item)

    # Скиллы
    skill_order = [
        SkillSlot(ability_id=ab.ability_id, slot=ab.slot)
        for ab in guide_data.ability_order
    ]

    # Таланты
    talents = _convert_talents(guide_data.talents)

    return HeroBuild(
        hero_id=hero_id,
        name_en=name_en,
        name_ru=name_ru,
        starting_items=starting,
        core_items=core,
        situational_items=situational_from_main,
        skill_order=skill_order,
        talents=talents,
        guide_winrate=guide_data.winrate,
    )


def _convert_items(items: list[ItemPurchase]) -> list[BuildItem]:
    """Конвертировать ItemPurchase из Stratz в BuildItem с именами."""
    result: list[BuildItem] = []
    for ip in items:
        result.append(
            BuildItem(
                item_id=ip.item_id,
                name_en=get_item_name_en(ip.item_id),
                name_ru=get_item_name_ru(ip.item_id),
                winrate=ip.winrate,
                match_count=ip.match_count,
                time=ip.time,
            )
        )
    return result


def _convert_talents(talents: list[TalentInfo]) -> list[TalentChoice]:
    """Конвертировать TalentInfo из Stratz в TalentChoice."""
    result: list[TalentChoice] = []
    for t in talents:
        result.append(
            TalentChoice(
                ability_id=t.ability_id,
                slot=t.slot,
                winrate=t.winrate,
                match_count=t.match_count,
            )
        )
    # Сортируем по слоту (порядок выбора талантов)
    result.sort(key=lambda tc: tc.slot)
    return result
