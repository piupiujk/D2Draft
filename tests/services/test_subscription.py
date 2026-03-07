"""Тесты для services/subscription.py — сервис подписок."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

from services.subscription import activate_premium, check_premium, deactivate

# ---------------------------------------------------------------------------
# activate_premium
# ---------------------------------------------------------------------------


class TestActivatePremium:
    """Тесты активации Premium-подписки."""

    async def test_creates_subscription_and_updates_user(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()

        sub_repo.create.return_value = {
            "id": 1,
            "user_id": 42,
            "plan": "premium",
            "status": "active",
            "expires_at": "2026-04-07T00:00:00+00:00",
        }
        user_repo.update.return_value = {"id": 42, "is_premium": True}

        result = await activate_premium(
            user_id=42,
            telegram_id=123456,
            duration_days=30,
            sub_repo=sub_repo,
            user_repo=user_repo,
        )

        assert result["id"] == 1
        assert result["status"] == "active"
        sub_repo.create.assert_called_once()
        user_repo.update.assert_called_once()

        # Проверяем аргументы update
        call_args = user_repo.update.call_args
        assert call_args[0][0] == 123456  # telegram_id
        assert call_args[1]["is_premium"] is True
        assert "premium_expires_at" in call_args[1]

    async def test_duration_365_days(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()
        sub_repo.create.return_value = {"id": 2, "plan": "premium", "status": "active"}
        user_repo.update.return_value = {}

        await activate_premium(
            user_id=1,
            telegram_id=100,
            duration_days=365,
            sub_repo=sub_repo,
            user_repo=user_repo,
        )

        # Проверяем что expires_at передан в create
        create_kwargs = sub_repo.create.call_args[1]
        assert create_kwargs["expires_at"] is not None


# ---------------------------------------------------------------------------
# check_premium
# ---------------------------------------------------------------------------


class TestCheckPremium:
    """Тесты проверки Premium-статуса."""

    async def test_no_active_subscription(self):
        sub_repo = AsyncMock()
        sub_repo.get_active.return_value = None

        result = await check_premium(user_id=1, sub_repo=sub_repo)
        assert result is False

    async def test_active_subscription_not_expired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        sub_repo = AsyncMock()
        sub_repo.get_active.return_value = {
            "id": 1,
            "status": "active",
            "expires_at": future,
        }

        result = await check_premium(user_id=1, sub_repo=sub_repo)
        assert result is True

    async def test_active_subscription_expired(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        sub_repo = AsyncMock()
        sub_repo.get_active.return_value = {
            "id": 1,
            "status": "active",
            "expires_at": past,
        }

        result = await check_premium(user_id=1, sub_repo=sub_repo)
        assert result is False

    async def test_no_expires_at_returns_true(self):
        sub_repo = AsyncMock()
        sub_repo.get_active.return_value = {
            "id": 1,
            "status": "active",
            "expires_at": None,
        }

        result = await check_premium(user_id=1, sub_repo=sub_repo)
        assert result is True

    async def test_invalid_expires_at_format(self):
        sub_repo = AsyncMock()
        sub_repo.get_active.return_value = {
            "id": 1,
            "status": "active",
            "expires_at": "invalid-date",
        }

        result = await check_premium(user_id=1, sub_repo=sub_repo)
        assert result is False


# ---------------------------------------------------------------------------
# deactivate
# ---------------------------------------------------------------------------


class TestDeactivate:
    """Тесты деактивации подписки."""

    async def test_deactivates_subscription_and_updates_user(self):
        sub_repo = AsyncMock()
        user_repo = AsyncMock()

        sub_repo.deactivate.return_value = {
            "id": 5,
            "status": "cancelled",
        }
        user_repo.update.return_value = {"id": 42, "is_premium": False}

        result = await deactivate(
            subscription_id=5,
            telegram_id=123456,
            sub_repo=sub_repo,
            user_repo=user_repo,
        )

        assert result["status"] == "cancelled"
        sub_repo.deactivate.assert_called_once_with(5)

        call_args = user_repo.update.call_args
        assert call_args[0][0] == 123456
        assert call_args[1]["is_premium"] is False
        assert call_args[1]["premium_expires_at"] is None
