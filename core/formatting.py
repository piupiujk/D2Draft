"""Функции форматирования сообщений для Telegram (HTML parse_mode)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
