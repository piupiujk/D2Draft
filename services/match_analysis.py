"""Сервис анализа матча: базовый разбор с метриками по ролям и LLM-советы."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clients.llm import LLMClient
from clients.opendota import MatchDetails, OpenDotaClient
from clients.steam import steam_id_64_to_account_id
from core.enums import MatchOutcome, Role
from core.hero_mapping import get_hero_by_id
from core.logging import get_logger
from repositories.match_analysis import MatchAnalysisRepository

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------


@dataclass
class RoleMetric:
    """Одна метрика с значением и медианой для сравнения."""

    name: str  # Название метрики (например, "GPM")
    label_ru: str  # Отображаемое имя на русском
    value: float  # Значение игрока
    median: float  # Медиана для героя/ранга
    unit: str = ""  # Единица измерения (%, "/мин" и т.д.)

    @property
    def diff(self) -> float:
        """Разница между значением и медианой."""
        return self.value - self.median

    @property
    def diff_pct(self) -> float:
        """Разница в процентах от медианы."""
        if self.median == 0:
            return 0.0
        return (self.value - self.median) / self.median * 100


@dataclass
class MatchAnalysis:
    """Результат анализа одного матча."""

    match_id: int
    hero_id: int
    hero_name_ru: str
    hero_name_en: str
    role: Role
    role_detected: bool  # True если роль определена автоматически
    duration_sec: int
    result: MatchOutcome
    kills: int
    deaths: int
    assists: int
    metrics: list[RoleMetric] = field(default_factory=list)
    player_stats: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Определение роли по данным OpenDota
# ---------------------------------------------------------------------------

# OpenDota lane_role: 1=safe, 2=mid, 3=off, 4=jungle
# player_slot < 128 → radiant, >= 128 → dire
_LANE_ROLE_MAP: dict[int, Role] = {
    1: Role.CARRY,
    2: Role.MID,
    3: Role.OFFLANE,
    4: Role.SOFT_SUPPORT,  # "jungle" → обычно роуминг/софт
}


def _detect_role(player_data: dict[str, Any]) -> Role | None:
    """Определить роль игрока по данным матча OpenDota.

    Используем lane_role + is_roaming + obs_placed.
    """
    lane_role = player_data.get("lane_role")
    is_roaming = player_data.get("is_roaming", False)

    if is_roaming:
        return Role.SOFT_SUPPORT

    if lane_role and lane_role in _LANE_ROLE_MAP:
        role = _LANE_ROLE_MAP[lane_role]
        # Различаем carry и hard support на safe lane
        if lane_role == 1:
            # Если мало last hits → скорее саппорт
            lh = player_data.get("last_hits", 0)
            duration = player_data.get("duration", 1)
            lh_per_min = lh / (duration / 60) if duration > 0 else 0
            if lh_per_min < 3:
                return Role.HARD_SUPPORT
        # Различаем offlane и soft support на off lane
        if lane_role == 3:
            lh = player_data.get("last_hits", 0)
            duration = player_data.get("duration", 1)
            lh_per_min = lh / (duration / 60) if duration > 0 else 0
            if lh_per_min < 3:
                return Role.SOFT_SUPPORT
        return role

    return None


# ---------------------------------------------------------------------------
# Метрики по ролям
# ---------------------------------------------------------------------------

# Базовые метрики (для всех ролей)
_BASE_METRICS = [
    ("kills", "Убийства"),
    ("deaths", "Смерти"),
    ("assists", "Ассисты"),
]

# Специфичные метрики по ролям
_ROLE_METRICS: dict[Role, list[tuple[str, str]]] = {
    Role.CARRY: [
        ("gold_per_min", "GPM"),
        ("xp_per_min", "XPM"),
        ("last_hits", "Ластхиты"),
        ("hero_damage", "Урон героям"),
        ("tower_damage", "Урон строениям"),
    ],
    Role.MID: [
        ("gold_per_min", "GPM"),
        ("xp_per_min", "XPM"),
        ("last_hits", "Ластхиты"),
        ("hero_damage", "Урон героям"),
        ("tower_damage", "Урон строениям"),
    ],
    Role.OFFLANE: [
        ("gold_per_min", "GPM"),
        ("xp_per_min", "XPM"),
        ("hero_damage", "Урон героям"),
        ("tower_damage", "Урон строениям"),
        ("stuns", "Оглушение (сек)"),
    ],
    Role.SOFT_SUPPORT: [
        ("obs_placed", "Обсервер варды"),
        ("sen_placed", "Сентри варды"),
        ("hero_healing", "Лечение"),
        ("assists", "Ассисты"),
        ("stuns", "Оглушение (сек)"),
    ],
    Role.HARD_SUPPORT: [
        ("obs_placed", "Обсервер варды"),
        ("sen_placed", "Сентри варды"),
        ("hero_healing", "Лечение"),
        ("assists", "Ассисты"),
        ("stuns", "Оглушение (сек)"),
    ],
}

# Приблизительные медианы метрик по ролям (для среднего ранга Legend)
# Эти значения нормализованы к 30-минутному матчу
_MEDIAN_VALUES: dict[Role, dict[str, float]] = {
    Role.CARRY: {
        "kills": 8,
        "deaths": 5,
        "assists": 10,
        "gold_per_min": 550,
        "xp_per_min": 600,
        "last_hits": 250,
        "hero_damage": 20000,
        "tower_damage": 5000,
    },
    Role.MID: {
        "kills": 9,
        "deaths": 5,
        "assists": 10,
        "gold_per_min": 550,
        "xp_per_min": 650,
        "last_hits": 230,
        "hero_damage": 22000,
        "tower_damage": 4000,
    },
    Role.OFFLANE: {
        "kills": 6,
        "deaths": 6,
        "assists": 14,
        "gold_per_min": 450,
        "xp_per_min": 550,
        "hero_damage": 18000,
        "tower_damage": 3000,
        "stuns": 50,
    },
    Role.SOFT_SUPPORT: {
        "kills": 4,
        "deaths": 7,
        "assists": 16,
        "obs_placed": 8,
        "sen_placed": 6,
        "hero_healing": 3000,
        "stuns": 40,
    },
    Role.HARD_SUPPORT: {
        "kills": 3,
        "deaths": 8,
        "assists": 18,
        "obs_placed": 12,
        "sen_placed": 10,
        "hero_healing": 5000,
        "stuns": 35,
    },
}


def _scale_median_by_duration(
    median: float,
    duration_sec: int,
    metric_name: str,
) -> float:
    """Масштабировать медиану пропорционально длительности матча.

    GPM/XPM не масштабируются (они уже нормализованы по минутам).
    Остальные метрики масштабируются от 30-минутного стандарта.
    """
    if metric_name in ("gold_per_min", "xp_per_min"):
        return median
    ratio = duration_sec / 1800  # 1800 = 30 минут
    return median * ratio


def _build_metrics(
    player_data: dict[str, Any],
    role: Role,
    duration_sec: int,
) -> list[RoleMetric]:
    """Собрать список метрик для роли с медианами."""
    role_specific = _ROLE_METRICS.get(role, [])
    medians = _MEDIAN_VALUES.get(role, {})

    metrics: list[RoleMetric] = []
    for metric_key, label_ru in role_specific:
        value = float(player_data.get(metric_key, 0) or 0)
        raw_median = medians.get(metric_key, 0)
        median = _scale_median_by_duration(raw_median, duration_sec, metric_key)

        metrics.append(
            RoleMetric(
                name=metric_key,
                label_ru=label_ru,
                value=value,
                median=round(median, 1),
            )
        )

    return metrics


# ---------------------------------------------------------------------------
# Извлечение данных игрока из матча
# ---------------------------------------------------------------------------


def _find_player_in_match(
    match: MatchDetails,
    account_id: int,
) -> dict[str, Any] | None:
    """Найти данные игрока в списке players матча."""
    for player in match.players:
        if player.get("account_id") == account_id:
            return player
    return None


def _determine_result(
    player_data: dict[str, Any],
    radiant_win: bool,
) -> MatchOutcome:
    """Определить результат матча для игрока."""
    player_slot = player_data.get("player_slot", 0)
    is_radiant = player_slot < 128
    won = is_radiant == radiant_win
    return MatchOutcome.WIN if won else MatchOutcome.LOSS


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


async def analyze_last_match(
    steam_id: int,
    *,
    opendota: OpenDotaClient,
    match_repo: MatchAnalysisRepository | None = None,
    user_id: int | None = None,
    user_role: Role | None = None,
) -> MatchAnalysis:
    """Разобрать последний матч игрока.

    Args:
        steam_id: Steam ID 64-bit игрока.
        opendota: Клиент OpenDota API.
        match_repo: Репозиторий для сохранения (опционально).
        user_id: ID пользователя в БД (для сохранения).
        user_role: Основная роль пользователя (fallback если автоопределение не сработало).

    Returns:
        MatchAnalysis с полным набором метрик по роли.

    Raises:
        ValueError: Если нет матчей или игрок не найден в матче.
    """
    account_id = steam_id_64_to_account_id(steam_id)

    # 1. Получаем последний матч
    recent = await opendota.get_recent_matches(account_id, limit=1)
    if not recent:
        msg = "У игрока нет недавних матчей"
        raise ValueError(msg)

    last = recent[0]
    match_id = last.match_id

    # 2. Получаем детали матча
    match = await opendota.get_match(match_id)

    # 3. Ищем данные нашего игрока
    player_data = _find_player_in_match(match, account_id)
    if player_data is None:
        msg = f"Игрок не найден в матче {match_id}"
        raise ValueError(msg)

    # 4. Определяем роль
    detected_role = _detect_role(player_data)
    role_detected = detected_role is not None
    role = detected_role or user_role or Role.CARRY

    # 5. Определяем результат
    result = _determine_result(player_data, match.radiant_win)

    # 6. Получаем данные героя
    hero_id = player_data.get("hero_id", last.hero_id)
    try:
        hero_data = get_hero_by_id(hero_id)
        hero_name_ru = hero_data.name_ru
        hero_name_en = hero_data.name_en
    except Exception:
        hero_name_ru = f"Герой #{hero_id}"
        hero_name_en = f"Hero #{hero_id}"

    # 7. Собираем метрики по роли
    metrics = _build_metrics(player_data, role, match.duration)

    # 8. Формируем результат
    analysis = MatchAnalysis(
        match_id=match_id,
        hero_id=hero_id,
        hero_name_ru=hero_name_ru,
        hero_name_en=hero_name_en,
        role=role,
        role_detected=role_detected,
        duration_sec=match.duration,
        result=result,
        kills=player_data.get("kills", 0),
        deaths=player_data.get("deaths", 0),
        assists=player_data.get("assists", 0),
        metrics=metrics,
        player_stats=player_data,
    )

    # 9. Сохраняем в БД (если переданы репозиторий и user_id)
    if match_repo is not None and user_id is not None:
        existing = await match_repo.get_by_match_id(user_id, match_id)
        if existing is None:
            stats_dict = {
                m.name: {"value": m.value, "median": m.median}
                for m in metrics
            }
            await match_repo.insert(
                user_id=user_id,
                match_id=match_id,
                hero_id=hero_id,
                role=int(role),
                result=result.value,
                duration_sec=match.duration,
                stats=stats_dict,
            )

    return analysis


# ---------------------------------------------------------------------------
# LLM-совет по матчу (Premium)
# ---------------------------------------------------------------------------


def _build_llm_context(analysis: MatchAnalysis) -> dict[str, Any]:
    """Сформировать контекст для LLM-промпта из анализа матча."""
    role_names = {
        Role.CARRY: "Carry",
        Role.MID: "Mid",
        Role.OFFLANE: "Offlane",
        Role.SOFT_SUPPORT: "Soft Support",
        Role.HARD_SUPPORT: "Hard Support",
    }

    metrics_data: dict[str, Any] = {}
    median_stats: dict[str, Any] = {}
    for m in analysis.metrics:
        metrics_data[m.name] = m.value
        median_stats[m.name] = m.median

    context: dict[str, Any] = {
        "match_id": analysis.match_id,
        "hero": analysis.hero_name_ru,
        "role": int(analysis.role),
        "role_name": role_names.get(analysis.role, str(analysis.role)),
        "result": analysis.result.value,
        "duration": round(analysis.duration_sec / 60, 1),
        "kills": analysis.kills,
        "deaths": analysis.deaths,
        "assists": analysis.assists,
    }

    # Добавляем детальные метрики из player_stats
    ps = analysis.player_stats
    for key in (
        "gold_per_min", "xp_per_min", "last_hits", "denies",
        "hero_damage", "tower_damage", "hero_healing",
        "obs_placed", "sen_placed", "stuns",
    ):
        val = ps.get(key)
        if val is not None:
            context[key] = val

    context["median_stats"] = median_stats

    return context


async def get_llm_advice(
    analysis: MatchAnalysis,
    *,
    llm: LLMClient,
    match_repo: MatchAnalysisRepository | None = None,
    user_id: int | None = None,
) -> str:
    """Получить персональный LLM-совет по матчу.

    Args:
        analysis: Результат анализа матча.
        llm: Клиент LLM API.
        match_repo: Репозиторий для сохранения совета (опционально).
        user_id: ID пользователя в БД (для сохранения).

    Returns:
        Текстовый совет от LLM.
    """
    context = _build_llm_context(analysis)
    advice = await llm.summarize_match(context)

    # Сохраняем совет в БД
    if match_repo is not None and user_id is not None:
        await match_repo.update_llm_summary(
            user_id=user_id,
            match_id=analysis.match_id,
            llm_summary=advice,
        )

    return advice
