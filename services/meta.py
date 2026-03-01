"""Сервис мета-героев: топ герои по роли и рангу из Stratz + личная статистика."""

from __future__ import annotations

import time
from dataclasses import dataclass

from clients.opendota import OpenDotaClient, PlayerHeroStats
from clients.stratz import MetaHeroStats, StratzClient
from core.enums import RankBracket, Role
from core.hero_mapping import get_hero_by_id

# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------

# Примерные границы MMR для определения брекета
_MMR_BRACKETS: list[tuple[int, RankBracket]] = [
    (0, RankBracket.HERALD),
    (770, RankBracket.GUARDIAN),
    (1540, RankBracket.CRUSADER),
    (2310, RankBracket.ARCHON),
    (3080, RankBracket.LEGEND),
    (3850, RankBracket.ANCIENT),
    (4620, RankBracket.DIVINE),
    (5420, RankBracket.IMMORTAL),
]


def mmr_to_bracket(mmr: int) -> RankBracket:
    """Определить ранговый брекет по MMR."""
    bracket = RankBracket.HERALD
    for threshold, rank in _MMR_BRACKETS:
        if mmr >= threshold:
            bracket = rank
    return bracket


@dataclass
class MetaHero:
    """Герой из мета-списка с обогащёнными данными."""

    hero_id: int
    name_ru: str
    name_en: str
    winrate: float  # Винрейт меты (0.0 — 1.0)
    pick_rate: float  # Пикрейт (доля от общего кол-ва матчей, 0.0 — 1.0)
    match_count: int  # Кол-во матчей
    personal_winrate: float | None = None  # Личный винрейт (если привязан)
    personal_games: int | None = None  # Личное кол-во игр


# ---------------------------------------------------------------------------
# Кэш (in-memory с TTL)
# ---------------------------------------------------------------------------

_CACHE_TTL = 3600  # 1 час
_cache: dict[str, tuple[float, list[MetaHero]]] = {}


def _cache_key(role: int, bracket: str) -> str:
    return f"meta:{role}:{bracket}"


def _get_cached(key: str) -> list[MetaHero] | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.monotonic() - ts > _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _set_cached(key: str, data: list[MetaHero]) -> None:
    _cache[key] = (time.monotonic(), data)


def invalidate_meta_cache() -> None:
    """Сбросить весь кэш мета-героев."""
    _cache.clear()


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


async def get_meta_heroes(
    role: Role | int,
    bracket: RankBracket | str,
    *,
    stratz: StratzClient,
    opendota: OpenDotaClient | None = None,
    account_id: int | None = None,
    top_n: int = 10,
) -> list[MetaHero]:
    """Получить топ мета-героев по роли и ранговому брекету.

    Args:
        role: Роль (1-5).
        bracket: Ранговый брекет (HERALD..IMMORTAL).
        stratz: Клиент Stratz API.
        opendota: Клиент OpenDota API (для личного винрейта).
        account_id: Account ID игрока (32-bit) для обогащения личной статистикой.
        top_n: Кол-во героев в результате (по умолчанию 10).

    Returns:
        Список MetaHero, отсортированный по винрейту (убывание).
    """
    role_val = int(Role(role))
    bracket_val = str(RankBracket(bracket))
    key = _cache_key(role_val, bracket_val)

    # Проверяем кэш (без личной статистики)
    cached = _get_cached(key)

    if cached is None:
        # Получаем мета-данные из Stratz
        raw_heroes = await stratz.get_meta_heroes(role, bracket)
        cached = _build_meta_list(raw_heroes, top_n)
        _set_cached(key, cached)

    # Обогащаем личным винрейтом, если есть account_id
    if opendota is not None and account_id is not None:
        personal_stats = await opendota.get_player_heroes(account_id)
        result = _enrich_with_personal(cached, personal_stats)
    else:
        result = cached

    return result[:top_n]


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _build_meta_list(
    raw_heroes: list[MetaHeroStats],
    top_n: int,
) -> list[MetaHero]:
    """Построить список MetaHero из сырых данных Stratz."""
    if not raw_heroes:
        return []

    total_matches = sum(h.match_count for h in raw_heroes)

    heroes: list[MetaHero] = []
    for h in raw_heroes:
        try:
            hero_data = get_hero_by_id(h.hero_id)
        except Exception:
            continue

        pick_rate = h.match_count / total_matches if total_matches > 0 else 0.0

        heroes.append(
            MetaHero(
                hero_id=h.hero_id,
                name_ru=hero_data.name_ru,
                name_en=hero_data.name_en,
                winrate=h.winrate,
                pick_rate=pick_rate,
                match_count=h.match_count,
            )
        )

    # Сортируем по винрейту (убывание)
    heroes.sort(key=lambda m: m.winrate, reverse=True)
    return heroes[:top_n]


def _enrich_with_personal(
    heroes: list[MetaHero],
    personal_stats: list[PlayerHeroStats],
) -> list[MetaHero]:
    """Обогатить мета-героев личной статистикой игрока."""
    personal_map = {s.hero_id: s for s in personal_stats}

    result: list[MetaHero] = []
    for h in heroes:
        personal = personal_map.get(h.hero_id)
        result.append(
            MetaHero(
                hero_id=h.hero_id,
                name_ru=h.name_ru,
                name_en=h.name_en,
                winrate=h.winrate,
                pick_rate=h.pick_rate,
                match_count=h.match_count,
                personal_winrate=personal.winrate if personal else None,
                personal_games=personal.games if personal else None,
            )
        )
    return result
