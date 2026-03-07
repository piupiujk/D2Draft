"""Джоб: еженедельная отправка персональной статистики пользователям."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import Bot

from clients.opendota import OpenDotaClient
from repositories.mmr_history import MmrHistoryRepository
from repositories.user import UserRepository
from services.profile import get_user_profile

logger = logging.getLogger(__name__)


def _format_weekly_report(user: dict[str, Any], profile: Any) -> str:
    """Сформировать текст еженедельного отчёта."""
    lines = ["📊 <b>Еженедельный отчёт</b>\n"]

    name = user.get("username") or "Игрок"
    lines.append(f"Привет, <b>{name}</b>!\n")

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

    if profile.winrate_7d is not None:
        lines.append(f"🎯 Винрейт за 7 дней: <b>{profile.winrate_7d:.1f}%</b>")

    if profile.total_matches:
        lines.append(f"🎮 Всего матчей: <b>{profile.total_matches}</b>")

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

    lines.append("\nУдачных катков! 🎮")
    return "\n".join(lines)


async def weekly_report_job(
    *,
    bot: Bot,
    user_repo: UserRepository | None = None,
    mmr_repo: MmrHistoryRepository | None = None,
    opendota: OpenDotaClient | None = None,
) -> int:
    """Отправить еженедельные отчёты пользователям с включёнными уведомлениями.

    Returns:
        Количество отправленных отчётов.
    """
    if user_repo is None:
        user_repo = UserRepository()
    if mmr_repo is None:
        mmr_repo = MmrHistoryRepository()

    close_opendota = False
    if opendota is None:
        opendota = OpenDotaClient()
        close_opendota = True

    try:
        users = await user_repo.get_with_notifications()
        logger.info("Еженедельный отчёт: найдено %d пользователей", len(users))

        sent = 0
        for user in users:
            try:
                steam_id = user.get("steam_id")
                if not steam_id:
                    continue

                profile = await get_user_profile(
                    user, opendota=opendota, mmr_repo=mmr_repo,
                )
                text = _format_weekly_report(user, profile)

                await bot.send_message(
                    chat_id=user["telegram_id"],
                    text=text,
                    parse_mode="HTML",
                )
                sent += 1
            except Exception:
                logger.exception(
                    "Ошибка отправки отчёта для user_id=%s", user.get("id"),
                )

        logger.info("Еженедельный отчёт: отправлено %d из %d", sent, len(users))
        return sent
    finally:
        if close_opendota:
            await opendota.close()
