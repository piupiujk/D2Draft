"""Джоб: мониторинг новых патчей Dota 2 через OpenDota API."""

from __future__ import annotations

from typing import Any

import httpx
from aiogram import Bot

from core.cache import invalidate_all_caches
from core.logging import get_logger
from repositories.user import UserRepository
from services.notification import compose_patch_alert

logger = get_logger(__name__)

# Храним последний известный патч в памяти
_last_known_patch: str | None = None


async def _fetch_latest_patch(client: httpx.AsyncClient | None = None) -> dict[str, Any] | None:
    """Получить последний патч из OpenDota /constants/patch."""
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=30.0)
        close_client = True

    try:
        resp = await client.get("https://api.opendota.com/api/constants/patch")
        if resp.status_code != 200:
            logger.warning("Не удалось получить патчи: HTTP %d", resp.status_code)
            return None

        patches = resp.json()
        if not patches:
            return None

        # OpenDota возвращает список словарей [{name, date}, ...]
        if isinstance(patches, list):
            return patches[-1] if patches else None

        # Если вернулся dict {patch_name: {date, ...}, ...}
        if isinstance(patches, dict):
            keys = sorted(patches.keys())
            if keys:
                last_key = keys[-1]
                patch_data = patches[last_key]
                if isinstance(patch_data, dict):
                    patch_data["name"] = last_key
                    return patch_data
                return {"name": last_key}

        return None
    except Exception:
        logger.exception("Ошибка при запросе патчей OpenDota")
        return None
    finally:
        if close_client:
            await client.aclose()


async def patch_monitor_job(
    *,
    bot: Bot,
    user_repo: UserRepository | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> bool:
    """Проверить наличие нового патча и уведомить пользователей.

    Returns:
        True если обнаружен новый патч, False если нет.
    """
    global _last_known_patch  # noqa: PLW0603

    if user_repo is None:
        user_repo = UserRepository()

    latest = await _fetch_latest_patch(http_client)
    if latest is None:
        logger.warning("Не удалось определить текущий патч")
        return False

    patch_name = latest.get("name", "")
    if not patch_name:
        return False

    # При первом запуске просто запоминаем патч
    if _last_known_patch is None:
        _last_known_patch = patch_name
        logger.info("Текущий патч: %s (первичная инициализация)", patch_name)
        return False

    if patch_name == _last_known_patch:
        logger.debug("Патч не изменился: %s", patch_name)
        return False

    # Обнаружен новый патч
    logger.info("Обнаружен новый патч: %s (был: %s)", patch_name, _last_known_patch)
    _last_known_patch = patch_name

    # Сбрасываем все кэши — мета и билды изменились
    invalidate_all_caches()

    # Уведомляем пользователей с включёнными уведомлениями
    users = await user_repo.get_with_notifications()
    text = compose_patch_alert(patch_name)

    sent = 0
    for user in users:
        try:
            await bot.send_message(
                chat_id=user["telegram_id"],
                text=text,
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            logger.exception(
                "Ошибка отправки уведомления о патче user_id=%s", user.get("id"),
            )

    logger.info("Уведомления о патче %s отправлены: %d/%d", patch_name, sent, len(users))
    return True
