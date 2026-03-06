"""Функции форматирования сообщений для Telegram (HTML parse_mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.build import HeroBuild
    from services.match_analysis import MatchAnalysis
    from services.meta import MetaHero
    from services.profile import UserProfile


def format_meta_heroes(heroes: list[MetaHero], role_label: str) -> str:
    """Форматировать список мета-героев для Telegram-сообщения.

    Args:
        heroes: список MetaHero для отображения.
        role_label: название роли на русском (для заголовка).

    Returns:
        Строка с HTML-разметкой, длина <= 4096 символов.
    """
    if not heroes:
        return f"Нет данных по мета-героям для роли <b>{role_label}</b>."

    lines: list[str] = [
        f"<b>Мета-герои — {role_label}</b>\n",
    ]

    for i, h in enumerate(heroes, start=1):
        wr_pct = f"{h.winrate * 100:.1f}%"
        pr_pct = f"{h.pick_rate * 100:.1f}%"

        line = f"{i}. <b>{h.name_en}</b>"
        line += f"\n   Винрейт: {wr_pct} | Пикрейт: {pr_pct} | Матчей: {h.match_count}"

        if h.personal_winrate is not None and h.personal_games is not None:
            p_wr = f"{h.personal_winrate * 100:.1f}%"
            line += f"\n   Личный: {p_wr} ({h.personal_games} игр)"

        lines.append(line)

    result = "\n".join(lines)

    # Лимит Telegram — 4096 символов
    if len(result) > 4096:
        result = result[:4090] + "\n..."

    return result


# ---------------------------------------------------------------------------
# format_build — полный билд героя
# ---------------------------------------------------------------------------

# Маппинг слотов скиллов в буквы
_SKILL_SLOT_LABEL = {0: "Q", 1: "W", 2: "E", 3: "R"}


def format_build(build: HeroBuild) -> str:
    """Форматировать полный билд героя для Telegram-сообщения.

    Args:
        build: HeroBuild из services/build.py.

    Returns:
        Строка с HTML-разметкой, длина <= 4096 символов.
    """
    lines: list[str] = [
        f"🛡 <b>Билд: {build.name_en}</b>",
    ]

    if build.guide_winrate > 0:
        lines.append(f"Винрейт гайда: {build.guide_winrate * 100:.1f}%")

    lines.append("")

    # Стартовые предметы
    if build.starting_items:
        lines.append("🟢 <b>Стартовые предметы</b>")
        items_text = ", ".join(it.name_en for it in build.starting_items)
        lines.append(items_text)
        lines.append("")

    # Основные предметы
    if build.core_items:
        lines.append("🔵 <b>Основные предметы</b>")
        for i, it in enumerate(build.core_items, start=1):
            wr = f"{it.winrate * 100:.1f}%" if it.winrate > 0 else ""
            time_str = ""
            if it.time is not None and it.time > 0:
                minutes = it.time // 60
                time_str = f" ~{minutes} мин"
            parts = [f"{i}. {it.name_en}"]
            if wr:
                parts.append(wr)
            if time_str:
                parts.append(time_str)
            lines.append(" | ".join(parts))
        lines.append("")

    # Ситуативные предметы
    if build.situational_items:
        lines.append("🟡 <b>Ситуативные предметы</b>")
        sit_names = ", ".join(it.name_en for it in build.situational_items)
        lines.append(sit_names)
        lines.append("")

    # Порядок прокачки скиллов
    if build.skill_order:
        lines.append("📘 <b>Прокачка скиллов</b>")
        skill_str = " → ".join(
            _SKILL_SLOT_LABEL.get(s.slot, "?") for s in build.skill_order
        )
        lines.append(skill_str)
        lines.append("")

    # Таланты
    if build.talents:
        lines.append("⭐ <b>Таланты</b>")
        for tc in build.talents:
            wr = f"{tc.winrate * 100:.1f}%" if tc.winrate > 0 else ""
            label = f"Ур. {10 + tc.slot * 5}" if tc.slot < 4 else f"Слот {tc.slot}"
            line = f"  {label}"
            if wr:
                line += f" (ВР: {wr})"
            lines.append(line)

    result = "\n".join(lines)

    # Лимит Telegram — 4096 символов
    if len(result) > 4096:
        result = result[:4090] + "\n..."

    return result


# ---------------------------------------------------------------------------
# format_match_analysis — разбор последнего матча
# ---------------------------------------------------------------------------

# Маппинг MatchOutcome → эмодзи + текст
_RESULT_DISPLAY = {
    "win": ("✅", "Победа"),
    "loss": ("❌", "Поражение"),
}


def format_match_analysis(analysis: MatchAnalysis) -> str:
    """Форматировать анализ матча для Telegram-сообщения.

    Args:
        analysis: MatchAnalysis из services/match_analysis.py.

    Returns:
        Строка с HTML-разметкой, длина <= 4096 символов.
    """
    result_val = (
        analysis.result.value
        if hasattr(analysis.result, "value")
        else str(analysis.result)
    )
    emoji, result_text = _RESULT_DISPLAY.get(result_val, ("❓", str(result_val)))

    # Длительность в минутах:секундах
    minutes = analysis.duration_sec // 60
    seconds = analysis.duration_sec % 60
    duration_str = f"{minutes}:{seconds:02d}"

    # Роль
    role_label = (
        analysis.role.label_ru
        if hasattr(analysis.role, "label_ru")
        else str(analysis.role)
    )

    lines: list[str] = [
        f"⚔️ <b>Разбор матча #{analysis.match_id}</b>",
        "",
        f"{emoji} <b>{result_text}</b> | {duration_str}",
        f"🦸 <b>{analysis.hero_name_en}</b>",
        f"🎯 Роль: {role_label}",
        f"📊 KDA: <b>{analysis.kills}/{analysis.deaths}/{analysis.assists}</b>",
    ]

    # Метрики по роли
    if analysis.metrics:
        lines.append("")
        lines.append("📈 <b>Метрики</b>")
        for m in analysis.metrics:
            val_str = _format_metric_value(m.value)
            med_str = _format_metric_value(m.median)
            diff = m.diff
            # Для deaths — ниже = лучше
            if m.name == "deaths":
                arrow = "🟢" if diff <= 0 else "🔴"
            else:
                arrow = "🟢" if diff >= 0 else "🔴"

            diff_str = f"+{diff:.0f}" if diff >= 0 else f"{diff:.0f}"
            lines.append(
                f"  {arrow} {m.label_ru}: <b>{val_str}</b> (медиана: {med_str}, {diff_str})"
            )

    result_full = "\n".join(lines)

    if len(result_full) > 4096:
        result_full = result_full[:4090] + "\n..."

    return result_full


def _format_metric_value(value: float) -> str:
    """Форматировать числовое значение метрики."""
    if value >= 1000:
        return f"{value:,.0f}".replace(",", " ")
    return f"{value:.0f}"


# ---------------------------------------------------------------------------
# format_profile — профиль пользователя
# ---------------------------------------------------------------------------

# Эмодзи медалей по ранговому брекету
_RANK_MEDAL: dict[str, str] = {
    "HERALD": "🥉 Герольд",
    "GUARDIAN": "🥉 Страж",
    "CRUSADER": "🥈 Рыцарь",
    "ARCHON": "🥈 Архонт",
    "LEGEND": "🥇 Легенда",
    "ANCIENT": "🥇 Титан",
    "DIVINE": "🏆 Божество",
    "IMMORTAL": "👑 Бессмертный",
}


def format_profile(profile: UserProfile) -> str:
    """Форматировать профиль пользователя для Telegram-сообщения.

    Args:
        profile: UserProfile из services/profile.py.

    Returns:
        Строка с HTML-разметкой, длина <= 4096 символов.
    """
    lines: list[str] = []

    # Заголовок
    name = profile.personaname or "Игрок"
    lines.append(f"👤 <b>Профиль: {name}</b>")
    lines.append("")

    # MMR и ранг
    if profile.current_mmr is not None:
        rank_str = ""
        if profile.rank_bracket is not None:
            bracket_name = (
                profile.rank_bracket.value
                if hasattr(profile.rank_bracket, "value")
                else str(profile.rank_bracket)
            )
            rank_str = _RANK_MEDAL.get(bracket_name, bracket_name)
        lines.append(f"🏅 MMR: <b>{profile.current_mmr}</b>")
        if rank_str:
            lines.append(f"   Медаль: {rank_str}")

    # Роль
    if profile.main_role is not None:
        role_label = (
            profile.main_role.label_ru
            if hasattr(profile.main_role, "label_ru")
            else str(profile.main_role)
        )
        lines.append(f"🎯 Роль: {role_label}")

    lines.append("")

    # Общая статистика
    if profile.overall_winrate is not None:
        lines.append("📊 <b>Статистика</b>")
        lines.append(f"   Общий винрейт: <b>{profile.overall_winrate:.1f}%</b>")
        if profile.total_matches > 0:
            lines.append(f"   Всего матчей: {profile.total_matches}")

    # Винрейт за период
    wr_parts: list[str] = []
    if profile.winrate_7d is not None:
        wr_parts.append(f"7д: {profile.winrate_7d:.1f}%")
    if profile.winrate_30d is not None:
        wr_parts.append(f"30д: {profile.winrate_30d:.1f}%")
    if wr_parts:
        lines.append(f"   Винрейт: {' | '.join(wr_parts)}")

    # Серия
    if profile.win_streak > 1:
        lines.append(f"   🔥 Серия побед: {profile.win_streak}")
    elif profile.loss_streak > 1:
        lines.append(f"   💀 Серия поражений: {profile.loss_streak}")

    # Динамика MMR
    if profile.mmr_history:
        lines.append("")
        lines.append("📈 <b>Динамика MMR</b>")
        first_mmr = profile.mmr_history[-1].mmr
        last_mmr = profile.mmr_history[0].mmr
        diff = last_mmr - first_mmr
        arrow = "↑" if diff > 0 else "↓" if diff < 0 else "→"
        sign = "+" if diff > 0 else ""
        lines.append(f"   {arrow} {sign}{diff} за 30 дней ({first_mmr} → {last_mmr})")

    # Топ герои
    if profile.top_heroes:
        lines.append("")
        lines.append("🦸 <b>Топ герои</b>")
        for i, h in enumerate(profile.top_heroes, start=1):
            wr_pct = f"{h.winrate * 100:.1f}%"
            lines.append(f"   {i}. {h.name_en} — {wr_pct} ({h.games} игр)")

    result = "\n".join(lines)

    if len(result) > 4096:
        result = result[:4090] + "\n..."

    return result
