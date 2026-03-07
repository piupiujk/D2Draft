"""Сервис уведомлений: формирование сообщений о патчах и еженедельных отчётов."""

from __future__ import annotations

from typing import Any

from core.logging import get_logger
from services.profile import UserProfile

logger = get_logger(__name__)


def compose_patch_alert(patch_name: str, hero_changes: list[str] | None = None) -> str:
    """Сформировать текст уведомления о новом патче.

    Args:
        patch_name: Версия патча (например, "7.36b").
        hero_changes: Список ключевых изменений героев (опционально).

    Returns:
        HTML-строка для отправки через Telegram.
    """
    lines = [
        "🔄 <b>Новый патч Dota 2!</b>\n",
        f"Версия: <b>{patch_name}</b>\n",
    ]

    if hero_changes:
        lines.append("<b>Ключевые изменения:</b>")
        for change in hero_changes[:10]:
            lines.append(f"  • {change}")
        lines.append("")

    lines.append("Мета-герои и билды могли измениться.")
    lines.append("Используй /meta и /build для актуальных данных!")

    return "\n".join(lines)


def compose_weekly_report(user: dict[str, Any], profile: UserProfile) -> str:
    """Сформировать текст еженедельного отчёта.

    Args:
        user: Данные пользователя из Supabase.
        profile: Агрегированный профиль пользователя.

    Returns:
        HTML-строка для отправки через Telegram.
    """
    lines = ["📊 <b>Еженедельный отчёт</b>\n"]

    name = user.get("username") or "Игрок"
    lines.append(f"Привет, <b>{name}</b>!\n")

    # MMR
    if profile.current_mmr is not None:
        lines.append(f"🏆 MMR: <b>{profile.current_mmr}</b>")

    # Динамика MMR за неделю
    if profile.mmr_history and len(profile.mmr_history) >= 2:
        latest = profile.mmr_history[0].mmr
        oldest = profile.mmr_history[-1].mmr
        diff = latest - oldest
        arrow = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
        sign = "+" if diff > 0 else ""
        lines.append(f"{arrow} Динамика за неделю: <b>{sign}{diff}</b>")

    # Винрейт за 7 дней
    if profile.winrate_7d is not None:
        lines.append(f"🎯 Винрейт за 7 дней: <b>{profile.winrate_7d:.1f}%</b>")

    # Винрейт за 30 дней
    if profile.winrate_30d is not None:
        lines.append(f"📅 Винрейт за 30 дней: <b>{profile.winrate_30d:.1f}%</b>")

    # Всего матчей
    if profile.total_matches:
        lines.append(f"🎮 Всего матчей: <b>{profile.total_matches}</b>")

    # Лучший герой
    if profile.top_heroes:
        best = profile.top_heroes[0]
        best_wr = best.winrate * 100
        lines.append(
            f"⭐ Лучший герой: <b>{best.name_ru}</b>"
            f" — {best.games} игр, {best_wr:.0f}% WR"
        )

    # Худший герой (по винрейту, если достаточно игр)
    if len(profile.top_heroes) >= 3:
        worst = min(
            (h for h in profile.top_heroes if h.games >= 3),
            key=lambda h: h.winrate,
            default=None,
        )
        if worst and worst.hero_id != profile.top_heroes[0].hero_id:
            worst_wr = worst.winrate * 100
            lines.append(
                f"⚠️ Слабый герой: <b>{worst.name_ru}</b>"
                f" — {worst.games} игр, {worst_wr:.0f}% WR"
            )

    # Топ герои
    if profile.top_heroes:
        lines.append("\n<b>Топ герои:</b>")
        for i, hero in enumerate(profile.top_heroes[:3], 1):
            wr = hero.winrate * 100
            lines.append(f"  {i}. {hero.name_ru} — {hero.games} игр, {wr:.0f}% WR")

    # Серии
    if profile.win_streak >= 3:
        lines.append(f"\n🔥 Серия побед: <b>{profile.win_streak}</b>!")
    elif profile.loss_streak >= 3:
        lines.append(f"\n❄️ Серия поражений: <b>{profile.loss_streak}</b>. Не сдавайся!")

    # Совет
    lines.append(_generate_tip(profile))

    lines.append("\nУдачных катков! 🎮")
    return "\n".join(lines)


def _generate_tip(profile: UserProfile) -> str:
    """Сгенерировать короткий совет на основе статистики."""
    if profile.winrate_7d is not None and profile.winrate_7d < 45:
        return "\n💡 Винрейт ниже 45% — попробуй сменить героев или роль."
    if profile.loss_streak >= 3:
        return "\n💡 Длинная серия поражений — сделай перерыв и вернись свежим."
    if profile.winrate_7d is not None and profile.winrate_7d > 60:
        return "\n💡 Отличный винрейт! Продолжай в том же духе."
    return "\n💡 Стабильная игра — используй /meta для поиска сильных героев."
