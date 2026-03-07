"""Тесты для scheduler/jobs/ — все джобы планировщика."""

from unittest.mock import AsyncMock, MagicMock, patch

from scheduler.jobs.expire_subscriptions import expire_subscriptions_job
from scheduler.jobs.patch_monitor import _format_patch_alert, patch_monitor_job
from scheduler.jobs.update_mmr import update_mmr_job
from scheduler.jobs.weekly_report import _format_weekly_report, weekly_report_job

# ---------------------------------------------------------------------------
# update_mmr_job
# ---------------------------------------------------------------------------


class TestUpdateMmrJob:
    """Тесты ежедневного обновления MMR."""

    async def test_updates_mmr_when_changed(self):
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_all_with_steam.return_value = [
            {"id": 1, "telegram_id": 111, "steam_id": "76561198000000001", "current_mmr": 3000},
        ]

        profile = MagicMock()
        profile.mmr_estimate = 3100
        opendota.get_player.return_value = profile

        result = await update_mmr_job(
            user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
        )

        assert result == 1
        user_repo.update_mmr.assert_called_once_with(111, 3100)
        mmr_repo.insert.assert_called_once_with(1, 3100)

    async def test_skips_when_mmr_unchanged(self):
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_all_with_steam.return_value = [
            {"id": 1, "telegram_id": 111, "steam_id": "76561198000000001", "current_mmr": 3000},
        ]

        profile = MagicMock()
        profile.mmr_estimate = 3000
        opendota.get_player.return_value = profile

        result = await update_mmr_job(
            user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
        )

        assert result == 0
        user_repo.update_mmr.assert_not_called()

    async def test_skips_when_mmr_none(self):
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_all_with_steam.return_value = [
            {"id": 1, "telegram_id": 111, "steam_id": "76561198000000001", "current_mmr": 3000},
        ]

        profile = MagicMock()
        profile.mmr_estimate = None
        opendota.get_player.return_value = profile

        result = await update_mmr_job(
            user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
        )

        assert result == 0

    async def test_handles_no_users(self):
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_all_with_steam.return_value = []

        result = await update_mmr_job(
            user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
        )

        assert result == 0

    async def test_continues_on_single_user_error(self):
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_all_with_steam.return_value = [
            {"id": 1, "telegram_id": 111, "steam_id": "76561198000000001", "current_mmr": 3000},
            {"id": 2, "telegram_id": 222, "steam_id": "76561198000000002", "current_mmr": 4000},
        ]

        profile_ok = MagicMock()
        profile_ok.mmr_estimate = 4100
        opendota.get_player.side_effect = [Exception("API error"), profile_ok]

        result = await update_mmr_job(
            user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
        )

        assert result == 1
        user_repo.update_mmr.assert_called_once_with(222, 4100)


# ---------------------------------------------------------------------------
# expire_subscriptions_job
# ---------------------------------------------------------------------------


class TestExpireSubscriptionsJob:
    """Тесты деактивации просроченных подписок."""

    async def test_deactivates_expired(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()

        sub_repo.get_expired_active.return_value = [
            {
                "id": 10,
                "user_id": 1,
                "status": "active",
                "users": {"telegram_id": 111},
            },
        ]
        sub_repo.deactivate.return_value = {"id": 10, "status": "cancelled"}
        user_repo.update.return_value = {"id": 1, "is_premium": False}

        result = await expire_subscriptions_job(sub_repo=sub_repo, user_repo=user_repo)

        assert result == 1
        sub_repo.deactivate.assert_called_once_with(10)
        user_repo.update.assert_called_once_with(
            111, is_premium=False, premium_expires_at=None,
        )

    async def test_no_expired(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()

        sub_repo.get_expired_active.return_value = []

        result = await expire_subscriptions_job(sub_repo=sub_repo, user_repo=user_repo)

        assert result == 0
        sub_repo.deactivate.assert_not_called()

    async def test_handles_missing_telegram_id(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()

        sub_repo.get_expired_active.return_value = [
            {"id": 10, "user_id": 1, "status": "active", "users": {}},
        ]
        sub_repo.deactivate.return_value = {"id": 10, "status": "cancelled"}

        result = await expire_subscriptions_job(sub_repo=sub_repo, user_repo=user_repo)

        assert result == 1
        sub_repo.deactivate.assert_called_once_with(10)
        user_repo.update.assert_not_called()

    async def test_continues_on_error(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()

        sub_repo.get_expired_active.return_value = [
            {"id": 10, "user_id": 1, "status": "active", "users": {"telegram_id": 111}},
            {"id": 11, "user_id": 2, "status": "active", "users": {"telegram_id": 222}},
        ]
        sub_repo.deactivate.side_effect = [Exception("DB error"), {"id": 11, "status": "cancelled"}]
        user_repo.update.return_value = {}

        result = await expire_subscriptions_job(sub_repo=sub_repo, user_repo=user_repo)

        assert result == 1


# ---------------------------------------------------------------------------
# weekly_report_job
# ---------------------------------------------------------------------------


class TestWeeklyReportJob:
    """Тесты еженедельного отчёта."""

    async def test_sends_reports(self):
        bot = AsyncMock()
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_with_notifications.return_value = [
            {"id": 1, "telegram_id": 111, "steam_id": "76561198000000001", "username": "Player1"},
        ]

        profile = MagicMock()
        profile.current_mmr = 3000
        profile.mmr_history = []
        profile.winrate_7d = 55.0
        profile.total_matches = 100
        profile.top_heroes = []
        profile.win_streak = 0
        profile.loss_streak = 0

        with patch("scheduler.jobs.weekly_report.get_user_profile", return_value=profile):
            result = await weekly_report_job(
                bot=bot, user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
            )

        assert result == 1
        bot.send_message.assert_called_once()
        call_kwargs = bot.send_message.call_args
        assert call_kwargs.kwargs["chat_id"] == 111
        assert "Player1" in call_kwargs.kwargs["text"]

    async def test_skips_users_without_steam(self):
        bot = AsyncMock()
        user_repo = AsyncMock()
        mmr_repo = AsyncMock()
        opendota = AsyncMock()

        user_repo.get_with_notifications.return_value = [
            {"id": 1, "telegram_id": 111, "steam_id": None, "username": "NoSteam"},
        ]

        result = await weekly_report_job(
            bot=bot, user_repo=user_repo, mmr_repo=mmr_repo, opendota=opendota,
        )

        assert result == 0
        bot.send_message.assert_not_called()

    async def test_no_users(self):
        bot = AsyncMock()
        user_repo = AsyncMock()

        user_repo.get_with_notifications.return_value = []

        result = await weekly_report_job(bot=bot, user_repo=user_repo)

        assert result == 0


class TestFormatWeeklyReport:
    """Тесты форматирования еженедельного отчёта."""

    def test_basic_report(self):
        user = {"username": "TestPlayer"}
        profile = MagicMock()
        profile.current_mmr = 3000
        profile.mmr_history = []
        profile.winrate_7d = 55.5
        profile.total_matches = 42
        profile.top_heroes = []
        profile.win_streak = 0
        profile.loss_streak = 0

        text = _format_weekly_report(user, profile)

        assert "TestPlayer" in text
        assert "3000" in text
        assert "55.5%" in text
        assert "42" in text

    def test_report_with_win_streak(self):
        user = {"username": "Streaker"}
        profile = MagicMock()
        profile.current_mmr = 5000
        profile.mmr_history = []
        profile.winrate_7d = 70.0
        profile.total_matches = 10
        profile.top_heroes = []
        profile.win_streak = 5
        profile.loss_streak = 0

        text = _format_weekly_report(user, profile)

        assert "5" in text
        assert "🔥" in text


# ---------------------------------------------------------------------------
# patch_monitor_job
# ---------------------------------------------------------------------------


class TestPatchMonitorJob:
    """Тесты мониторинга патчей."""

    async def test_first_run_initializes_patch(self):
        import scheduler.jobs.patch_monitor as pm

        pm._last_known_patch = None

        bot = AsyncMock()
        user_repo = AsyncMock()
        http_client = AsyncMock()

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [{"name": "7.37", "date": "2026-01-01"}]
        http_client.get.return_value = response

        result = await patch_monitor_job(bot=bot, user_repo=user_repo, http_client=http_client)

        assert result is False
        assert pm._last_known_patch == "7.37"
        bot.send_message.assert_not_called()

    async def test_same_patch_no_notification(self):
        import scheduler.jobs.patch_monitor as pm

        pm._last_known_patch = "7.37"

        bot = AsyncMock()
        user_repo = AsyncMock()
        http_client = AsyncMock()

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [{"name": "7.37", "date": "2026-01-01"}]
        http_client.get.return_value = response

        result = await patch_monitor_job(bot=bot, user_repo=user_repo, http_client=http_client)

        assert result is False
        bot.send_message.assert_not_called()

    async def test_new_patch_sends_notifications(self):
        import scheduler.jobs.patch_monitor as pm

        pm._last_known_patch = "7.37"

        bot = AsyncMock()
        user_repo = AsyncMock()
        http_client = AsyncMock()

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [
            {"name": "7.37", "date": "2026-01-01"},
            {"name": "7.38", "date": "2026-03-01"},
        ]
        http_client.get.return_value = response

        user_repo.get_with_notifications.return_value = [
            {"id": 1, "telegram_id": 111},
            {"id": 2, "telegram_id": 222},
        ]

        result = await patch_monitor_job(bot=bot, user_repo=user_repo, http_client=http_client)

        assert result is True
        assert pm._last_known_patch == "7.38"
        assert bot.send_message.call_count == 2

    async def test_api_error_returns_false(self):
        import scheduler.jobs.patch_monitor as pm

        pm._last_known_patch = "7.37"

        bot = AsyncMock()
        user_repo = AsyncMock()
        http_client = AsyncMock()

        response = MagicMock()
        response.status_code = 500
        http_client.get.return_value = response

        result = await patch_monitor_job(bot=bot, user_repo=user_repo, http_client=http_client)

        assert result is False


class TestFormatPatchAlert:
    """Тесты форматирования уведомления о патче."""

    def test_contains_patch_name(self):
        text = _format_patch_alert("7.38")

        assert "7.38" in text
        assert "Новый патч" in text
        assert "/meta" in text


# ---------------------------------------------------------------------------
# create_scheduler
# ---------------------------------------------------------------------------


class TestCreateScheduler:
    """Тесты создания планировщика."""

    def test_creates_scheduler_with_all_jobs(self):
        from scheduler.setup import create_scheduler

        bot = MagicMock()
        scheduler = create_scheduler(bot)

        job_ids = {job.id for job in scheduler.get_jobs()}
        assert "update_mmr" in job_ids
        assert "weekly_report" in job_ids
        assert "patch_monitor" in job_ids
        assert "expire_subscriptions" in job_ids
        assert len(job_ids) == 4
