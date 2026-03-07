"""Тесты для bot/handlers/subscription.py — хендлер подписок."""

from unittest.mock import AsyncMock, patch

import pytest

from bot.handlers.subscription import (
    _subscription_kb,
    _subscription_status_text,
    activate_subscription,
    cancel_deactivate,
    cmd_subscribe,
    confirm_deactivate,
    deactivate_prompt,
)

# ---------------------------------------------------------------------------
# Вспомогательные функции форматирования
# ---------------------------------------------------------------------------


class TestSubscriptionStatusText:
    """Тесты текста статуса подписки."""

    def test_premium_active(self):
        user = {"premium_expires_at": "2026-04-07T00:00:00+00:00"}
        text = _subscription_status_text(user, is_premium=True)
        assert "Активна" in text
        assert "2026-04-07" in text

    def test_free_plan(self):
        user = {}
        text = _subscription_status_text(user, is_premium=False)
        assert "Бесплатный план" in text
        assert "Premium-функции" in text


class TestSubscriptionKb:
    """Тесты клавиатуры подписки."""

    def test_free_user_sees_activation_buttons(self):
        kb = _subscription_kb(is_premium=False)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("30 дней" in t for t in texts)
        assert any("365 дней" in t for t in texts)

    def test_premium_user_sees_deactivate(self):
        kb = _subscription_kb(is_premium=True)
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert any("Отменить" in t for t in texts)


# ---------------------------------------------------------------------------
# /subscribe
# ---------------------------------------------------------------------------


class TestCmdSubscribe:
    """Тесты команды /subscribe."""

    @pytest.fixture
    def message(self):
        msg = AsyncMock()
        msg.answer = AsyncMock(return_value=AsyncMock())
        return msg

    async def test_unregistered_user(self, message):
        await cmd_subscribe(message, user=None)
        assert "зарегистрироваться" in message.answer.call_args[0][0]

    async def test_free_user(self, message):
        user = {"id": 1, "telegram_id": 100}
        await cmd_subscribe(message, user=user, is_premium=False)
        text = message.answer.call_args[0][0]
        assert "Бесплатный план" in text

    async def test_premium_user(self, message):
        user = {"id": 1, "telegram_id": 100, "premium_expires_at": "2026-05-01T00:00:00+00:00"}
        await cmd_subscribe(message, user=user, is_premium=True)
        text = message.answer.call_args[0][0]
        assert "Активна" in text


# ---------------------------------------------------------------------------
# Активация
# ---------------------------------------------------------------------------


class TestActivateSubscription:
    """Тесты активации подписки через callback."""

    @pytest.fixture
    def callback(self):
        cb = AsyncMock()
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        cb.message.edit_text = AsyncMock()
        cb.data = "sub:activate:30"
        return cb

    @patch("bot.handlers.subscription.activate_premium", new_callable=AsyncMock)
    async def test_activates_30_days(self, mock_activate, callback):
        mock_activate.return_value = {
            "id": 1,
            "expires_at": "2026-04-07T00:00:00+00:00",
        }
        user = {"id": 1, "telegram_id": 100}

        await activate_subscription(callback, user=user)

        mock_activate.assert_called_once_with(
            user_id=1,
            telegram_id=100,
            duration_days=30,
        )
        callback.answer.assert_called_once()
        assert "30 дней" in callback.answer.call_args[1].get(
            "text", callback.answer.call_args[0][0] if callback.answer.call_args[0] else ""
        ) or "30 дней" in str(callback.answer.call_args)

    @patch("bot.handlers.subscription.activate_premium", new_callable=AsyncMock)
    async def test_activates_365_days(self, mock_activate, callback):
        callback.data = "sub:activate:365"
        mock_activate.return_value = {"id": 2, "expires_at": "2027-03-07T00:00:00+00:00"}
        user = {"id": 1, "telegram_id": 100}

        await activate_subscription(callback, user=user)

        mock_activate.assert_called_once_with(
            user_id=1,
            telegram_id=100,
            duration_days=365,
        )

    async def test_unregistered(self, callback):
        await activate_subscription(callback, user=None)
        callback.answer.assert_called_once()
        assert "зарегистрироваться" in str(callback.answer.call_args)


# ---------------------------------------------------------------------------
# Деактивация
# ---------------------------------------------------------------------------


class TestDeactivatePrompt:
    """Тесты запроса подтверждения деактивации."""

    @pytest.fixture
    def callback(self):
        cb = AsyncMock()
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        cb.message.edit_text = AsyncMock()
        return cb

    async def test_shows_confirmation(self, callback):
        user = {"id": 1, "telegram_id": 100}
        await deactivate_prompt(callback, user=user, is_premium=True)
        text = callback.message.edit_text.call_args[0][0]
        assert "Отмена подписки" in text

    async def test_no_subscription(self, callback):
        user = {"id": 1, "telegram_id": 100}
        await deactivate_prompt(callback, user=user, is_premium=False)
        assert "нет активной" in str(callback.answer.call_args).lower()


class TestConfirmDeactivate:
    """Тесты подтверждения деактивации."""

    @pytest.fixture
    def callback(self):
        cb = AsyncMock()
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        cb.message.edit_text = AsyncMock()
        return cb

    @patch("bot.handlers.subscription.deactivate", new_callable=AsyncMock)
    @patch("bot.handlers.subscription.SubscriptionRepository")
    async def test_deactivates_successfully(self, mock_repo_cls, mock_deactivate, callback):
        mock_repo = AsyncMock()
        mock_repo.get_active.return_value = {"id": 5, "status": "active"}
        mock_repo_cls.return_value = mock_repo
        mock_deactivate.return_value = {"id": 5, "status": "cancelled"}

        user = {"id": 1, "telegram_id": 100}
        await confirm_deactivate(callback, user=user)

        mock_deactivate.assert_called_once_with(
            subscription_id=5,
            telegram_id=100,
        )

    @patch("bot.handlers.subscription.SubscriptionRepository")
    async def test_no_active_sub(self, mock_repo_cls, callback):
        mock_repo = AsyncMock()
        mock_repo.get_active.return_value = None
        mock_repo_cls.return_value = mock_repo

        user = {"id": 1, "telegram_id": 100}
        await confirm_deactivate(callback, user=user)
        assert "не найдена" in str(callback.answer.call_args).lower()


# ---------------------------------------------------------------------------
# Отмена
# ---------------------------------------------------------------------------


class TestCancelDeactivate:
    """Тесты отмены деактивации."""

    async def test_returns_to_menu(self):
        cb = AsyncMock()
        cb.answer = AsyncMock()
        cb.message = AsyncMock()
        cb.message.edit_text = AsyncMock()

        user = {"id": 1, "telegram_id": 100}
        await cancel_deactivate(cb, user=user, is_premium=True)
        text = cb.message.edit_text.call_args[0][0]
        assert "Активна" in text
