"""Джоб: ежедневное обновление MMR для всех активных пользователей."""

from __future__ import annotations

import logging

from clients.opendota import OpenDotaClient
from clients.steam import steam_id_64_to_account_id
from repositories.mmr_history import MmrHistoryRepository
from repositories.user import UserRepository

logger = logging.getLogger(__name__)


async def update_mmr_job(
    *,
    user_repo: UserRepository | None = None,
    mmr_repo: MmrHistoryRepository | None = None,
    opendota: OpenDotaClient | None = None,
) -> int:
    """Обновить MMR всех пользователей с привязанным Steam.

    Для каждого пользователя:
    1. Получает mmr_estimate из OpenDota API.
    2. Если MMR изменился — обновляет users и добавляет запись в mmr_history.

    Returns:
        Количество обновлённых пользователей.
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
        users = await user_repo.get_all_with_steam()
        logger.info("Обновление MMR: найдено %d пользователей с Steam", len(users))

        updated = 0
        for user in users:
            try:
                steam_id = user.get("steam_id")
                if not steam_id:
                    continue

                account_id = steam_id_64_to_account_id(int(steam_id))
                profile = await opendota.get_player(account_id)

                new_mmr = profile.mmr_estimate
                if new_mmr is None:
                    continue

                old_mmr = user.get("current_mmr")
                if old_mmr == new_mmr:
                    continue

                telegram_id = user["telegram_id"]
                await user_repo.update_mmr(telegram_id, new_mmr)
                await mmr_repo.insert(user["id"], new_mmr)
                updated += 1
                logger.info(
                    "MMR обновлён: user_id=%s, %s -> %s",
                    user["id"], old_mmr, new_mmr,
                )
            except Exception:
                logger.exception("Ошибка обновления MMR для user_id=%s", user.get("id"))

        logger.info("Обновление MMR завершено: обновлено %d из %d", updated, len(users))
        return updated
    finally:
        if close_opendota:
            await opendota.close()
