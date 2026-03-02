"""Функции форматирования сообщений для Telegram (HTML parse_mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.build import HeroBuild
    from services.meta import MetaHero


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

        line = f"{i}. <b>{h.name_ru}</b> ({h.name_en})"
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
        f"🛡 <b>Билд: {build.name_ru}</b> ({build.name_en})",
    ]

    if build.guide_winrate > 0:
        lines.append(f"Винрейт гайда: {build.guide_winrate * 100:.1f}%")

    lines.append("")

    # Стартовые предметы
    if build.starting_items:
        lines.append("🟢 <b>Стартовые предметы</b>")
        items_text = ", ".join(it.name_ru for it in build.starting_items)
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
            parts = [f"{i}. {it.name_ru}"]
            if wr:
                parts.append(wr)
            if time_str:
                parts.append(time_str)
            lines.append(" | ".join(parts))
        lines.append("")

    # Ситуативные предметы
    if build.situational_items:
        lines.append("🟡 <b>Ситуативные предметы</b>")
        sit_names = ", ".join(it.name_ru for it in build.situational_items)
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
