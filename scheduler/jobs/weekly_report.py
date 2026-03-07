"""Джоб: еженедельная отправка персональной статистики пользователям."""

from __future__ import annotations

from aiogram import Bot

from clients.opendota import OpenDotaClient
from core.logging import get_logger
from repositories.mmr_history import MmrHistoryRepository
from repositories.user import UserRepository
from services.notification import compose_weekly_report
from services.profile import get_user_profile

logger = get_logger(__name__)


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
                text = compose_weekly_report(user, profile)

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
