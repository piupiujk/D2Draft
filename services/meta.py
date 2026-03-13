"""Сервис мета-героев: топ герои по роли и рангу из Stratz + личная статистика."""

from __future__ import annotations

from dataclasses import dataclass

from clients.opendota import OpenDotaClient, PlayerHeroStats
from clients.stratz import MetaHeroStats, StratzClient
from core.cache import meta_cache
from core.enums import RankBracket, Role
from core.hero_mapping import get_hero_by_id
from core.logging import get_logger

logger = get_logger(__name__)

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
    trend: float = 0.0  # Дельта винрейта (this_week - last_week)
    meta_score: float = 0.0  # Комбинированный рейтинг для сортировки
    personal_winrate: float | None = None  # Личный винрейт (если привязан)
    personal_games: int | None = None  # Личное кол-во игр


# ---------------------------------------------------------------------------
# Кэш (делегирован в core.cache.meta_cache)
# ---------------------------------------------------------------------------

# Обратная совместимость: _cache ссылается на внутреннее хранилище meta_cache
_cache = meta_cache._store


def _cache_key(role: int, bracket: str) -> str:
    return f"meta:{role}:{bracket}"


def invalidate_meta_cache() -> None:
    """Сбросить весь кэш мета-героев."""
    meta_cache.invalidate_all()


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
    cached = meta_cache.get(key)

    if cached is None:
        logger.debug("Кэш-промах мета-героев: role=%s, bracket=%s", role_val, bracket_val)
        raw_heroes = await stratz.get_meta_heroes(role, bracket)
        cached = _build_meta_list(raw_heroes, top_n)
        meta_cache.set(key, cached)
    else:
        logger.debug("Кэш-попадание мета-героев: role=%s, bracket=%s", role_val, bracket_val)

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
    max_pick_rate = max(
        (h.match_count / total_matches for h in raw_heroes if total_matches > 0),
        default=1.0,
    )

    heroes: list[MetaHero] = []
    for h in raw_heroes:
        try:
            hero_data = get_hero_by_id(h.hero_id)
        except Exception:
            continue

        pick_rate = h.match_count / total_matches if total_matches > 0 else 0.0
        norm_pick = pick_rate / max_pick_rate if max_pick_rate > 0 else 0.0
        meta_score = h.winrate * 0.7 + norm_pick * 0.3

        heroes.append(
            MetaHero(
                hero_id=h.hero_id,
                name_ru=hero_data.name_ru,
                name_en=hero_data.name_en,
                winrate=h.winrate,
                pick_rate=pick_rate,
                match_count=h.match_count,
                trend=h.trend,
                meta_score=meta_score,
            )
        )

    # Сортируем по meta_score (убывание)
    heroes.sort(key=lambda m: m.meta_score, reverse=True)
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
                trend=h.trend,
                meta_score=h.meta_score,
                personal_winrate=personal.winrate if personal else None,
                personal_games=personal.games if personal else None,
            )
        )
    return result
