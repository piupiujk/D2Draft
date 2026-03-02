"""Сервис профиля: агрегация статистики пользователя."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from clients.opendota import OpenDotaClient, PlayerHeroStats, RecentMatch
from clients.steam import steam_id_64_to_account_id
from core.enums import RankBracket, Role
from core.hero_mapping import get_hero_by_id
from repositories.mmr_history import MmrHistoryRepository
from services.meta import mmr_to_bracket

# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------


@dataclass
class TopHero:
    """Топ-герой пользователя."""

    hero_id: int
    name_ru: str
    name_en: str
    games: int
    winrate: float  # 0.0 — 1.0


@dataclass
class MmrPoint:
    """Точка динамики MMR."""

    mmr: int
    recorded_at: str  # ISO-строка


@dataclass
class UserProfile:
    """Агрегированный профиль пользователя."""

    current_mmr: int | None
    rank_bracket: RankBracket | None
    main_role: Role | None
    overall_winrate: float | None  # 0.0 — 100.0
    top_heroes: list[TopHero] = field(default_factory=list)
    winrate_7d: float | None = None  # 0.0 — 100.0
    winrate_30d: float | None = None  # 0.0 — 100.0
    win_streak: int = 0  # Положительное = серия побед, 0 = нет серии
    loss_streak: int = 0  # Положительное = серия поражений, 0 = нет серии
    mmr_history: list[MmrPoint] = field(default_factory=list)
    total_matches: int = 0
    personaname: str | None = None


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


async def get_user_profile(
    user: dict[str, Any],
    *,
    opendota: OpenDotaClient,
    mmr_repo: MmrHistoryRepository | None = None,
) -> UserProfile:
    """Собрать агрегированный профиль пользователя.

    Args:
        user: Данные пользователя из Supabase (dict с полями steam_id, current_mmr и т.д.).
        opendota: Клиент OpenDota API.
        mmr_repo: Репозиторий истории MMR (опционально).

    Returns:
        Заполненный UserProfile.
    """
    steam_id = user.get("steam_id")
    current_mmr = user.get("current_mmr")
    main_role_raw = user.get("main_role")
    user_id = user.get("id")

    # Ранговый брекет
    rank_bracket = mmr_to_bracket(current_mmr) if current_mmr else None

    # Основная роль
    main_role: Role | None = None
    if main_role_raw is not None:
        try:
            main_role = Role(int(main_role_raw))
        except (ValueError, KeyError):
            pass

    # Если нет steam_id — возвращаем минимальный профиль
    if not steam_id:
        return UserProfile(
            current_mmr=current_mmr,
            rank_bracket=rank_bracket,
            main_role=main_role,
            overall_winrate=None,
            personaname=user.get("username"),
        )

    account_id = steam_id_64_to_account_id(int(steam_id))

    # Параллельные запросы к OpenDota
    hero_stats = await opendota.get_player_heroes(account_id)
    recent_matches = await opendota.get_recent_matches(account_id, limit=100)

    # Общий винрейт
    overall_winrate = _calc_overall_winrate(hero_stats)

    # Топ-5 героев
    top_heroes = _build_top_heroes(hero_stats, top_n=5)

    # Винрейт за 7 и 30 дней
    winrate_7d = _calc_recent_winrate(recent_matches, days=7)
    winrate_30d = _calc_recent_winrate(recent_matches, days=30)

    # Серия побед/поражений
    win_streak, loss_streak = _calc_streaks(recent_matches)

    # Кол-во матчей
    total_matches = sum(h.games for h in hero_stats)

    # Динамика MMR из репозитория
    mmr_history: list[MmrPoint] = []
    if mmr_repo is not None and user_id is not None:
        raw_history = await mmr_repo.get_history(user_id, days=30)
        mmr_history = [
            MmrPoint(mmr=row["mmr"], recorded_at=row["recorded_at"])
            for row in raw_history
        ]

    return UserProfile(
        current_mmr=current_mmr,
        rank_bracket=rank_bracket,
        main_role=main_role,
        overall_winrate=overall_winrate,
        top_heroes=top_heroes,
        winrate_7d=winrate_7d,
        winrate_30d=winrate_30d,
        win_streak=win_streak,
        loss_streak=loss_streak,
        mmr_history=mmr_history,
        total_matches=total_matches,
        personaname=user.get("username"),
    )


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


def _calc_overall_winrate(hero_stats: list[PlayerHeroStats]) -> float | None:
    """Рассчитать общий винрейт по статистике героев (0.0 — 100.0)."""
    total_games = sum(h.games for h in hero_stats)
    if total_games == 0:
        return None
    total_wins = sum(h.win for h in hero_stats)
    return round(total_wins / total_games * 100, 1)


def _build_top_heroes(
    hero_stats: list[PlayerHeroStats], top_n: int = 5
) -> list[TopHero]:
    """Построить топ героев по кол-ву игр."""
    # Фильтруем героев с 0 игр
    played = [h for h in hero_stats if h.games > 0]
    # Сортируем по кол-ву игр (убывание)
    played.sort(key=lambda h: h.games, reverse=True)

    result: list[TopHero] = []
    for h in played[:top_n]:
        try:
            hero_data = get_hero_by_id(h.hero_id)
            name_ru = hero_data.name_ru
            name_en = hero_data.name_en
        except Exception:
            name_ru = f"Герой #{h.hero_id}"
            name_en = f"Hero #{h.hero_id}"

        result.append(
            TopHero(
                hero_id=h.hero_id,
                name_ru=name_ru,
                name_en=name_en,
                games=h.games,
                winrate=h.winrate,
            )
        )
    return result


def _calc_recent_winrate(
    matches: list[RecentMatch], days: int
) -> float | None:
    """Рассчитать винрейт за последние N дней (0.0 — 100.0)."""
    import time

    now = int(time.time())
    cutoff = now - days * 86400

    recent = [m for m in matches if m.start_time >= cutoff]
    if not recent:
        return None

    wins = sum(1 for m in recent if m.is_win)
    return round(wins / len(recent) * 100, 1)


def _calc_streaks(matches: list[RecentMatch]) -> tuple[int, int]:
    """Определить текущую серию побед/поражений.

    Матчи должны быть отсортированы по дате (новые первыми).

    Returns:
        (win_streak, loss_streak) — только одно из значений > 0.
    """
    if not matches:
        return 0, 0

    # Определяем текущую серию по первому матчу
    first_win = matches[0].is_win
    streak = 0
    for m in matches:
        if m.is_win == first_win:
            streak += 1
        else:
            break

    if first_win:
        return streak, 0
    return 0, streak
