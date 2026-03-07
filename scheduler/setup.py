"""Инициализация AsyncIOScheduler и регистрация всех джобов."""

from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from scheduler.jobs.expire_subscriptions import expire_subscriptions_job
from scheduler.jobs.patch_monitor import patch_monitor_job
from scheduler.jobs.update_mmr import update_mmr_job
from scheduler.jobs.weekly_report import weekly_report_job

logger = logging.getLogger(__name__)


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Создать и настроить планировщик с джобами.

    Args:
        bot: Экземпляр Telegram-бота (нужен для отправки сообщений).

    Returns:
        Настроенный (но не запущенный) AsyncIOScheduler.
    """
    scheduler = AsyncIOScheduler(timezone="UTC")

    # Ежедневное обновление MMR для всех пользователей (03:00 UTC)
    scheduler.add_job(
        update_mmr_job,
        "cron",
        hour=3,
        minute=0,
        id="update_mmr",
        replace_existing=True,
    )

    # Еженедельная отправка отчётов (понедельник 10:00 UTC)
    scheduler.add_job(
        weekly_report_job,
        "cron",
        day_of_week="mon",
        hour=10,
        minute=0,
        kwargs={"bot": bot},
        id="weekly_report",
        replace_existing=True,
    )

    # Проверка патчей каждые 6 часов
    scheduler.add_job(
        patch_monitor_job,
        "interval",
        hours=6,
        kwargs={"bot": bot},
        id="patch_monitor",
        replace_existing=True,
    )

    # Деактивация просроченных подписок каждый час
    scheduler.add_job(
        expire_subscriptions_job,
        "interval",
        hours=1,
        id="expire_subscriptions",
        replace_existing=True,
    )

    logger.info("Планировщик создан, зарегистрировано %d джобов", len(scheduler.get_jobs()))
    return scheduler
