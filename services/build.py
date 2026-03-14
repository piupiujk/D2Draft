"""Сервис билдов: получение item build и skill build героя.

Primary source: dota2protracker.com (про-игроки).
Fallback: Stratz GraphQL API.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from clients.llm import LLMClient, load_prompt
from clients.protracker import ProBuildData, ProtrackerClient, ProtrackerError
from clients.stratz import (
    HeroBuildData,
    HeroGuideData,
    HeroMatchup,
    ItemPurchase,
    StratzClient,
    TalentInfo,
)
from core.cache import build_cache
from core.enums import RankBracket, Role
from core.hero_mapping import get_hero_by_id
from core.items import ITEM_BY_ID, get_item_name_en, get_item_name_ru
from core.logging import get_logger

logger = get_logger(__name__)

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
    purchase_rate: float = 0.0  # 0.0 — 1.0


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
    name: str = ""
    level: int = 0


@dataclass
class MatchupEntry:
    """Запись о matchup-е героя."""

    hero_id: int
    name_en: str
    name_ru: str
    advantage: float  # synergy value (positive = good, negative = bad)


@dataclass
class HeroBuild:
    """Полный билд героя: предметы, скиллы, таланты, matchups."""

    hero_id: int
    name_en: str
    name_ru: str
    starting_items: list[BuildItem] = field(default_factory=list)
    boots: list[BuildItem] = field(default_factory=list)
    core_items: list[BuildItem] = field(default_factory=list)
    situational_items: list[BuildItem] = field(default_factory=list)
    skill_order: list[SkillSlot] = field(default_factory=list)
    talents: list[TalentChoice] = field(default_factory=list)
    guide_winrate: float = 0.0  # Винрейт гайда
    guide_match_count: int = 0  # Кол-во матчей гайда
    best_with: list[MatchupEntry] = field(default_factory=list)
    worst_against: list[MatchupEntry] = field(default_factory=list)
    best_against: list[MatchupEntry] = field(default_factory=list)
    # Protracker-specific fields
    patch: str = ""
    position: str = ""
    facet: str = ""
    source: str = ""  # "protracker" | "stratz"
    skill_order_labels: list[str] = field(default_factory=list)  # ["Q","W","E",...]
    starting_sets: list[list[str]] = field(default_factory=list)  # наборы стартовых
    neutral_items: dict[int, list[str]] = field(default_factory=dict)  # tier -> names


# ---------------------------------------------------------------------------
# Кэш (делегирован в core.cache.build_cache)
# ---------------------------------------------------------------------------

# Обратная совместимость: _cache ссылается на внутреннее хранилище build_cache
_cache = build_cache._store


def _cache_key(hero_id: int, role: int | None, bracket: str | None) -> str:
    return f"build:{hero_id}:{role}:{bracket}"


def invalidate_build_cache() -> None:
    """Сбросить весь кэш билдов."""
    build_cache.invalidate_all()


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

    Primary: dota2protracker.com (данные про-игроков).
    Fallback: Stratz GraphQL API.
    """
    role_val = int(Role(role)) if role is not None else None
    bracket_val = str(RankBracket(bracket)) if bracket is not None else None
    key = _cache_key(hero_id, role_val, bracket_val)

    cached = build_cache.get(key)
    if cached is not None:
        return cached

    hero_data = get_hero_by_id(hero_id)

    # Primary: protracker
    result = await _try_protracker(hero_id, hero_data.name_en, hero_data.name_ru)

    # Fallback: Stratz
    if result is None:
        result = await _build_from_stratz(hero_id, hero_data, role, bracket, stratz)

    # Matchups из Stratz (protracker их не даёт на основной странице)
    try:
        matchup_data = await stratz.get_hero_matchups(hero_id, bracket)
        if matchup_data:
            result.best_with = _convert_matchups(matchup_data.with_heroes[:3])
            result.worst_against = _convert_matchups(matchup_data.vs_heroes[:3])
            best_against_raw = sorted(matchup_data.vs_heroes, key=lambda m: m.synergy, reverse=True)
            result.best_against = _convert_matchups(best_against_raw[:3])
    except Exception:
        logger.warning("Не удалось получить matchups для hero_id=%s", hero_id, exc_info=True)

    build_cache.set(key, result)
    return result


async def _try_protracker(
    hero_id: int,
    name_en: str,
    name_ru: str,
) -> HeroBuild | None:
    """Попробовать получить билд из protracker."""
    try:
        client = ProtrackerClient()
        try:
            pro_data = await client.get_hero_build(name_en)
        finally:
            client.close()
        return _build_from_protracker(hero_id, name_en, name_ru, pro_data)
    except ProtrackerError as exc:
        logger.warning("Protracker недоступен для %s: %s", name_en, exc)
        return None
    except Exception:
        logger.warning("Ошибка protracker для %s", name_en, exc_info=True)
        return None


def _build_from_protracker(
    hero_id: int,
    name_en: str,
    name_ru: str,
    pro: ProBuildData,
) -> HeroBuild:
    """Конвертировать ProBuildData в HeroBuild."""
    # Core items: anchor_items + дополняем из mid_late до 8
    core_items: list[BuildItem] = []
    core_names: set[str] = set()
    for item in pro.core_items:
        core_items.append(
            BuildItem(
                item_id=0,
                name_en=item.name,
                name_ru=item.name,
                winrate=item.winrate,
                match_count=0,
                time=item.avg_time * 60 if item.avg_time > 0 else None,
                purchase_rate=item.purchase_rate,
            )
        )
        core_names.add(item.name)

    # Дополняем core из mid/late (по purchase_rate, до 8 штук)
    if len(core_items) < 8:
        for item in pro.mid_late_items:
            if item.name in core_names:
                continue
            core_items.append(
                BuildItem(
                    item_id=0,
                    name_en=item.name,
                    name_ru=item.name,
                    winrate=item.winrate,
                    match_count=0,
                    time=item.avg_time * 60 if item.avg_time > 0 else None,
                    purchase_rate=item.purchase_rate,
                )
            )
            core_names.add(item.name)
            if len(core_items) >= 8:
                break
    situational_items: list[BuildItem] = []
    for item in pro.mid_late_items:
        if item.name in core_names:
            continue
        if len(situational_items) >= 8:
            break
        situational_items.append(
            BuildItem(
                item_id=0,
                name_en=item.name,
                name_ru=item.name,
                winrate=item.winrate,
                match_count=0,
                time=item.avg_time * 60 if item.avg_time > 0 else None,
                purchase_rate=item.purchase_rate,
            )
        )

    # Таланты
    talents: list[TalentChoice] = []
    for i, t in enumerate(pro.talents):
        talents.append(
            TalentChoice(
                ability_id=0,
                slot=i,
                winrate=t.pick_rate,  # pickrate как основная метрика
                match_count=0,
                name=t.name,
                level=t.level,
            )
        )

    # Скиллы — готовые буквы из protracker
    skill_order: list[SkillSlot] = []
    label_to_slot = {"Q": 0, "W": 1, "E": 2, "R": 3, "D": 4, "F": 5}
    for label in pro.skill_order:
        slot = label_to_slot.get(label, -1)
        skill_order.append(SkillSlot(ability_id=0, slot=slot))

    return HeroBuild(
        hero_id=hero_id,
        name_en=name_en,
        name_ru=name_ru,
        core_items=core_items,
        situational_items=situational_items,
        skill_order=skill_order,
        talents=talents,
        guide_winrate=pro.winrate,
        guide_match_count=pro.matches,
        patch=pro.patch,
        position=pro.position,
        facet=pro.facet_name,
        source="protracker",
        skill_order_labels=pro.skill_order,
        starting_sets=pro.starting_items,
        neutral_items=pro.neutral_items,
    )


async def _build_from_stratz(
    hero_id: int,
    hero_data: object,
    role: Role | int | None,
    bracket: RankBracket | str | None,
    stratz: StratzClient,
) -> HeroBuild:
    """Получить билд из Stratz (fallback)."""
    build_data = await stratz.get_hero_build(hero_id, role, bracket)

    try:
        guide_data = await stratz.get_hero_guide(hero_id, role, bracket)
    except Exception:
        logger.warning("Не удалось получить гайд для hero_id=%s", hero_id, exc_info=True)
        guide_data = HeroGuideData(hero_id=hero_id)

    result = _assemble_build(
        hero_id,
        hero_data.name_en,
        hero_data.name_ru,
        build_data,
        guide_data,
    )
    result.source = "stratz"
    return result


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

# Лимиты предметов по секциям
_STARTING_ITEMS_COUNT = 6
_CORE_ITEMS_COUNT = 6
_SITUATIONAL_ITEMS_COUNT = 8

# Расходники — всегда исключаем из core/situational
_CONSUMABLE_IDS: set[int] = {
    38,  # Clarity
    39,  # Faerie Fire
    40,  # Smoke of Deceit
    41,  # Tome of Knowledge
    42,  # Observer Ward
    43,  # Sentry Ward
    44,  # Tango
    45,  # Animal Courier
    46,  # Flying Courier
    216,  # Dust of Appearance
    218,  # Iron Branch
    237,  # Healing Salve
    241,  # Mango
    265,  # Infused Raindrops
    593,  # Blood Grenade
}

# Сырые компоненты — промежуточные предметы, которые всегда встраиваются в конечные.
# Исключаем из core/situational, чтобы показать только «готовые» предметы.
_COMPONENT_IDS: set[int] = {
    2,  # Blades of Attack
    4,  # Chainmail
    5,  # Broadsword
    6,  # Quarterstaff
    7,  # Platemail
    8,  # Helm of Iron Will
    10,  # Ring of Protection
    11,  # Ring of Regen
    12,  # Gloves of Haste
    13,  # Mithril Hammer
    14,  # Demon Edge
    15,  # Cloak
    16,  # Gauntlets of Strength
    17,  # Slippers of Agility
    18,  # Mantle of Intelligence
    19,  # Circlet
    20,  # Belt of Strength
    21,  # Band of Elvenskin
    22,  # Robe of the Magi
    23,  # Ogre Axe
    24,  # Blade of Alacrity
    25,  # Staff of Wizardry
    26,  # Point Booster
    27,  # Ring of Health
    29,  # Claymore
    30,  # Javelin
    31,  # Morbid Mask
    32,  # Sacred Relic
    33,  # Hyperstone
    48,  # Stout Shield
    51,  # Oblivion Staff
    55,  # Perseverance
    60,  # Void Stone
    61,  # Mystic Staff
    65,  # Ultimate Orb
    67,  # Reaver
    69,  # Eagle Song
    77,  # Wind Lace
    137,  # Shadow Amulet
    240,  # Crown
    273,  # Voodoo Mask
    573,  # Fluffy Hat
    600,  # Cornucopia
}

# Дешёвые утилиты — покупаются на каждом герое, не являются core-предметами
_CHEAP_UTILITY_IDS: set[int] = {
    36,  # Magic Wand
    73,  # Blight Stone
    75,  # Urn of Shadows
    180,  # Ring of Basilius
    182,  # Sage's Mask (composes into items)
    34,  # Bottle
}

# Удалённые из игры предметы (исторические данные в Stratz)
_REMOVED_ITEM_IDS: set[int] = {
    116,  # Necronomicon 1
    117,  # Necronomicon 2
    118,  # Necronomicon 3
    239,  # Iron Talon
    187,  # Helm of the Dominator (old version)
    193,  # Ring of Aquila
    104,  # Stygian Desolator (old)
}

# Объединённый набор предметов, исключаемых из core/situational
_EXCLUDED_FROM_BUILD: set[int] = (
    _CONSUMABLE_IDS | _COMPONENT_IDS | _CHEAP_UTILITY_IDS | _REMOVED_ITEM_IDS
)


def _is_build_item(item: BuildItem) -> bool:
    """Проверить, что предмет — «готовый» (не расходник и не компонент)."""
    return item.item_id not in _EXCLUDED_FROM_BUILD


def _is_build_item_id(item_id: int) -> bool:
    """Проверить по ID, что предмет — «готовый» (не расходник и не компонент)."""
    return item_id not in _EXCLUDED_FROM_BUILD


def _dedup_items(items: list[BuildItem]) -> list[BuildItem]:
    """Убрать дубликаты по item_id, сохраняя порядок (первое вхождение)."""
    seen: set[int] = set()
    result: list[BuildItem] = []
    for item in items:
        if item.item_id not in seen:
            seen.add(item.item_id)
            result.append(item)
    return result


def _assemble_build(
    hero_id: int,
    name_en: str,
    name_ru: str,
    build_data: HeroBuildData,
    guide_data: HeroGuideData,
) -> HeroBuild:
    """Собрать HeroBuild из сырых данных Stratz."""
    # Стартовые: из itemStartingPurchase, без компонентов
    starting_raw = _convert_items(build_data.starting_items)
    starting_raw = [it for it in starting_raw if it.item_id not in _COMPONENT_IDS]
    starting = _dedup_items(starting_raw)[:_STARTING_ITEMS_COUNT]

    # Ботинки: из itemBootPurchase, топ-1 по matchCount
    boots_raw = _convert_items(build_data.boot_items)
    boots = _dedup_items(boots_raw)[:3]

    # Core/situational: из itemFullPurchase (уже агрегировано и отсортировано по matchCount)
    core, situational = _items_from_stats(build_data)

    # Скиллы: abilityMaxLevel уже отсортированы по level
    skill_order = [
        SkillSlot(ability_id=ab.ability_id, slot=ab.slot) for ab in guide_data.ability_order
    ]

    # Таланты: группируем по тирам (4 тира, лучший выбор на каждом)
    talents = _convert_talents(guide_data.talents)

    return HeroBuild(
        hero_id=hero_id,
        name_en=name_en,
        name_ru=name_ru,
        starting_items=starting,
        boots=boots,
        core_items=core,
        situational_items=situational,
        skill_order=skill_order,
        talents=talents,
        guide_winrate=guide_data.winrate,
        guide_match_count=guide_data.match_count,
    )


def _items_from_stats(build_data: HeroBuildData) -> tuple[list[BuildItem], list[BuildItem]]:
    """Собрать core/situational из itemFullPurchase (агрегировано, сортировка по matchCount)."""
    # early_game содержит все агрегированные предметы, уже отсортированные по matchCount desc
    all_items = _convert_items(build_data.early_game)
    build_items = [it for it in all_items if _is_build_item(it)]
    build_items = _dedup_items(build_items)

    core = build_items[:_CORE_ITEMS_COUNT]
    situational = build_items[_CORE_ITEMS_COUNT : _CORE_ITEMS_COUNT + _SITUATIONAL_ITEMS_COUNT]
    return core, situational


def _convert_items(items: list[ItemPurchase]) -> list[BuildItem]:
    """Конвертировать ItemPurchase из Stratz в BuildItem с именами.

    Предметы, отсутствующие в маппинге (Item #XXX), отфильтровываются.
    """
    result: list[BuildItem] = []
    for ip in items:
        if ip.item_id not in ITEM_BY_ID:
            continue
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


def _convert_matchups(matchups: list[HeroMatchup]) -> list[MatchupEntry]:
    """Конвертировать HeroMatchup из Stratz в MatchupEntry с именами."""
    result: list[MatchupEntry] = []
    for m in matchups:
        try:
            hero_data = get_hero_by_id(m.hero_id2)
            result.append(
                MatchupEntry(
                    hero_id=m.hero_id2,
                    name_en=hero_data.name_en,
                    name_ru=hero_data.name_ru,
                    advantage=m.synergy,
                )
            )
        except Exception:
            continue
    return result


def _convert_talents(talents: list[TalentInfo]) -> list[TalentChoice]:
    """Конвертировать TalentInfo из Stratz в TalentChoice.

    API возвращает все 8 талантов (2 на каждый тир).
    Группируем по парам (0-1, 2-3, 4-5, 6-7) и берём лучший по matchCount.
    """
    if not talents:
        return []

    # Группируем по тирам (пары: 0-1=tier1, 2-3=tier2, 4-5=tier3, 6-7=tier4)
    tiers: dict[int, list[TalentInfo]] = {}
    for t in talents:
        tier = t.slot // 2
        if tier not in tiers:
            tiers[tier] = []
        tiers[tier].append(t)

    result: list[TalentChoice] = []
    for tier_idx in sorted(tiers.keys()):
        # Берём талант с наибольшим matchCount в тире
        best = max(tiers[tier_idx], key=lambda t: t.match_count)
        result.append(
            TalentChoice(
                ability_id=best.ability_id,
                slot=tier_idx,  # 0=lvl10, 1=lvl15, 2=lvl20, 3=lvl25
                winrate=best.winrate,
                match_count=best.match_count,
            )
        )
    return result


# ---------------------------------------------------------------------------
# Ситуативная адаптация билда (Premium)
# ---------------------------------------------------------------------------


@dataclass
class SituationalBuild:
    """Билд героя, адаптированный под вражеский состав."""

    base_build: HeroBuild
    adaptation_text: str  # Текст от LLM с пояснениями по адаптации


async def get_situational_build(
    hero_id: int,
    role: Role | int | None = None,
    bracket: RankBracket | str | None = None,
    enemy_heroes: list[int] | None = None,
    *,
    stratz: StratzClient,
    llm_client: LLMClient,
) -> SituationalBuild:
    """Получить билд героя, адаптированный под вражеский состав.

    Args:
        hero_id: ID героя.
        role: Роль (1-5).
        bracket: Ранговый брекет.
        enemy_heroes: Список hero_id вражеских героев.
        stratz: Клиент Stratz API.
        llm_client: Клиент LLM для генерации пояснений.

    Returns:
        SituationalBuild со стандартным билдом и текстом адаптации.
    """
    # Получаем стандартный билд
    base_build = await get_hero_build(
        hero_id=hero_id,
        role=role,
        bracket=bracket,
        stratz=stratz,
    )

    if not enemy_heroes:
        return SituationalBuild(
            base_build=base_build,
            adaptation_text="Нет данных о вражеском составе для адаптации билда.",
        )

    # Собираем имена вражеских героев
    enemies_info = []
    for eid in enemy_heroes:
        try:
            edata = get_hero_by_id(eid)
            enemies_info.append({"hero_id": eid, "name": edata.name_en})
        except Exception:
            enemies_info.append({"hero_id": eid, "name": f"Hero #{eid}"})

    hero_data = get_hero_by_id(hero_id)

    # Формируем контекст для LLM
    role_val = int(Role(role)) if role is not None else 1
    bracket_val = str(RankBracket(bracket)) if bracket is not None else "LEGEND"

    llm_context = {
        "hero": hero_data.name_en,
        "hero_id": hero_id,
        "role": role_val,
        "bracket": bracket_val,
        "standard_build": {
            "core_items": [
                {"name": item.name_en, "name_ru": item.name_ru} for item in base_build.core_items
            ],
            "situational_items": [
                {"name": item.name_en, "name_ru": item.name_ru}
                for item in base_build.situational_items
            ],
        },
        "enemy_heroes": enemies_info,
    }

    # Загружаем промпт и отправляем запрос к LLM
    system_prompt = load_prompt("build_situational")
    if not system_prompt:
        system_prompt = (
            "Ты — эксперт по предметным сборкам Dota 2. "
            "Адаптируй стандартный билд героя под вражеский состав. "
            "Отвечай на русском языке, кратко."
        )

    prompt = json.dumps(llm_context, ensure_ascii=False, indent=2)
    response = await llm_client.complete(prompt, system=system_prompt, max_tokens=1024)

    return SituationalBuild(
        base_build=base_build,
        adaptation_text=response.text,
    )
