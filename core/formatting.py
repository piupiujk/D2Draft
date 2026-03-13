"""Функции форматирования сообщений для Telegram (HTML parse_mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.llm import PickRecommendation
    from services.build import HeroBuild
    from services.match_analysis import MatchAnalysis
    from services.meta import MetaHero
    from services.profile import UserProfile


def _trend_arrow(trend: float) -> str:
    """Стрелка тренда винрейта."""
    if trend > 0.005:
        return "⬆"
    if trend < -0.005:
        return "⬇"
    return "➡"


def _wr_tier_emoji(winrate: float) -> str:
    """Эмодзи уровня винрейта."""
    wr_pct = winrate * 100
    if wr_pct > 53:
        return "🟢"
    if wr_pct < 48:
        return "🔴"
    return "🟡"


def format_meta_heroes(
    heroes: list[MetaHero],
    role_label: str,
    bracket_label: str = "",
) -> str:
    """Форматировать список мета-героев для Telegram-сообщения.

    Args:
        heroes: список MetaHero для отображения.
        role_label: название роли на русском (для заголовка).
        bracket_label: название брекета (для заголовка).

    Returns:
        Строка с HTML-разметкой, длина <= 4096 символов.
    """
    if not heroes:
        return f"Нет данных по мета-героям для роли <b>{role_label}</b>."

    header = f"⚔️ <b>Мета-герои — {role_label}</b>"
    if bracket_label:
        header += f" ({bracket_label})"

    lines: list[str] = [header, ""]

    for i, h in enumerate(heroes, start=1):
        wr_pct = f"{h.winrate * 100:.1f}%"
        pr_pct = f"{h.pick_rate * 100:.1f}%"
        trend = _trend_arrow(h.trend)
        tier = _wr_tier_emoji(h.winrate)

        line = f" {i}. {trend} <b>{h.name_en}</b>"
        line += f"\n    {tier} WR: {wr_pct} | PR: {pr_pct} | {h.match_count} матчей"

        if h.personal_winrate is not None and h.personal_games is not None:
            p_wr = f"{h.personal_winrate * 100:.1f}%"
            line += f"\n    Личный: {p_wr} ({h.personal_games} игр)"

        lines.append(line)

    result = "\n".join(lines)

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
        header_parts = [f"{build.guide_winrate * 100:.1f}% WR"]
        if build.guide_match_count > 0:
            header_parts.append(f"{build.guide_match_count} матчей")
        lines.append(f"Гайд: {' | '.join(header_parts)}")

    lines.append("")

    # Стартовые предметы
    if build.starting_items:
        lines.append("🟢 <b>Стартовые предметы</b>")
        items_text = ", ".join(it.name_en for it in build.starting_items)
        lines.append(items_text)
        lines.append("")

    # Ботинки
    if build.boots:
        lines.append("👟 <b>Ботинки</b>")
        boot_parts = []
        for it in build.boots:
            pct = f"{it.winrate * 100:.0f}% WR" if it.winrate > 0 else ""
            boot_parts.append(f"{it.name_en} ({pct})" if pct else it.name_en)
        lines.append(", ".join(boot_parts))
        lines.append("")

    # Основные предметы
    if build.core_items:
        lines.append("🔵 <b>Основные предметы</b>")
        for i, it in enumerate(build.core_items, start=1):
            pct = f"{it.winrate * 100:.0f}%"
            mc = f"{it.match_count} матч." if it.match_count > 0 else ""
            parts = [f" {i}. {it.name_en}"]
            if pct:
                parts.append(pct)
            if mc:
                parts.append(mc)
            lines.append(" | ".join(parts))
        lines.append("")

    # Ситуативные предметы
    if build.situational_items:
        lines.append("🟡 <b>Ситуативные предметы</b>")
        sit_parts = []
        for it in build.situational_items:
            if it.winrate > 0:
                sit_parts.append(f"{it.name_en} ({it.winrate * 100:.0f}%)")
            else:
                sit_parts.append(it.name_en)
        lines.append(", ".join(sit_parts))
        lines.append("")

    # Порядок прокачки скиллов
    if build.skill_order:
        lines.append("📘 <b>Прокачка скиллов</b>")
        # Маппим abilityId → букву (Q/W/E/R) по порядку первого появления
        ability_id_to_label: dict[int, str] = {}
        labels = ["Q", "W", "E", "R", "D", "F"]
        for s in build.skill_order:
            if s.slot not in ability_id_to_label and len(ability_id_to_label) < len(labels):
                ability_id_to_label[s.slot] = labels[len(ability_id_to_label)]
        skill_str = " → ".join(ability_id_to_label.get(s.slot, "?") for s in build.skill_order)
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
                line += f" ({wr} WR)"
            lines.append(line)
        lines.append("")

    # Контрпики (плохо против)
    if build.worst_against:
        lines.append("⚔️ <b>Контрпики (плохо против)</b>")
        counter_parts = []
        for m in build.worst_against:
            counter_parts.append(f"{m.name_en} ({m.advantage:+.1f}%)")
        lines.append(", ".join(counter_parts))
        lines.append("")

    # Лучшие союзники
    if build.best_with:
        lines.append("🤝 <b>Лучшие союзники</b>")
        ally_parts = []
        for m in build.best_with:
            ally_parts.append(f"{m.name_en} ({m.advantage:+.1f}%)")
        lines.append(", ".join(ally_parts))
        lines.append("")

    # Хорош против
    if build.best_against:
        lines.append("💪 <b>Хорош против</b>")
        good_parts = []
        for m in build.best_against:
            good_parts.append(f"{m.name_en} ({m.advantage:+.1f}%)")
        lines.append(", ".join(good_parts))

    result = "\n".join(lines)

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
        analysis.result.value if hasattr(analysis.result, "value") else str(analysis.result)
    )
    emoji, result_text = _RESULT_DISPLAY.get(result_val, ("❓", str(result_val)))

    # Длительность в минутах:секундах
    minutes = analysis.duration_sec // 60
    seconds = analysis.duration_sec % 60
    duration_str = f"{minutes}:{seconds:02d}"

    # Роль
    role_label = (
        analysis.role.label_ru if hasattr(analysis.role, "label_ru") else str(analysis.role)
    )

    lines: list[str] = [
        f"⚔️ <b>Разбор матча #{analysis.match_id}</b>",
        "",
        f"{emoji} <b>{result_text}</b> | {duration_str}",
        f"🦸 <b>{analysis.hero_name_ru}</b> ({analysis.hero_name_en})",
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


_RANK_TIER_MEDAL: dict[int, str] = {
    1: "🥉 Herald",
    2: "🥉 Guardian",
    3: "🥈 Crusader",
    4: "🥈 Archon",
    5: "🥇 Legend",
    6: "🥇 Ancient",
    7: "🏆 Divine",
    8: "👑 Immortal",
}


def _rank_tier_to_label(rank_tier: int) -> str:
    """Конвертация rank_tier (например 23) в строку 'Guardian 3'."""
    medal = rank_tier // 10
    stars = rank_tier % 10
    medal_name = _RANK_TIER_MEDAL.get(medal, f"Rank {medal}")
    return f"{medal_name} {stars}" if stars > 0 else medal_name


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
    lines.append("🏅 <b>MMR</b>")
    if profile.rank_tier is not None:
        medal_str = _rank_tier_to_label(profile.rank_tier)
        lines.append(f"   Медаль: {medal_str}")
    if profile.rank_mmr is not None:
        lines.append(f"   По медали: ~{profile.rank_mmr}")
    if profile.estimated_mmr is not None:
        lines.append(f"   Оценка OpenDota: ~{profile.estimated_mmr}")
    if profile.current_mmr is not None:
        lines.append(f"   Указан вручную: {profile.current_mmr}")

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


# ---------------------------------------------------------------------------
# format_draft_recommendations — рекомендации пиков
# ---------------------------------------------------------------------------


def format_draft_recommendations(recommendations: list[PickRecommendation]) -> str:
    """Форматировать рекомендации пиков для Telegram-сообщения.

    Args:
        recommendations: список PickRecommendation из clients/llm.py.

    Returns:
        Строка с HTML-разметкой, длина <= 4096 символов.
    """
    if not recommendations:
        return "Нет рекомендаций по пикам."

    lines: list[str] = ["🎯 <b>Рекомендации пиков</b>", ""]

    for i, rec in enumerate(recommendations, start=1):
        lines.append(f"<b>{i}. {rec.name_ru}</b>")
        if rec.reason:
            lines.append(f"   {rec.reason}")
        lines.append("")

    result = "\n".join(lines)

    if len(result) > 4096:
        result = result[:4090] + "\n..."

    return result
