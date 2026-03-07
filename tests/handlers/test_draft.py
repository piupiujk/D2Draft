"""Тесты для bot/handlers/draft.py — хендлер анализа драфта."""

from unittest.mock import AsyncMock

import pytest

from bot.handlers.draft import (
    _CB_DRAFT_PICK,
    _format_recognition,
    _format_recommendations,
    _recommendations_keyboard,
    _steam_to_account_id,
)
from clients.llm import PickRecommendation
from services.draft import ValidatedDraft

# ---------------------------------------------------------------------------
# Утилиты форматирования
# ---------------------------------------------------------------------------


class TestFormatRecognition:
    """Тесты форматирования результата распознавания."""

    def test_full_draft(self):
        draft = ValidatedDraft(
            allies=[1, 2],
            enemies=[3, 4],
            allies_names=["Анти-Маг", "Axe"],
            enemies_names=["Bane", "Bloodseeker"],
            confidence=0.9,
            needs_confirmation=False,
        )
        text = _format_recognition(draft)
        assert "Союзники" in text
        assert "Противники" in text
        assert "Анти-Маг" in text
        assert "90%" in text

    def test_needs_confirmation(self):
        draft = ValidatedDraft(
            allies=[1],
            enemies=[],
            allies_names=["Анти-Маг"],
            enemies_names=[],
            confidence=0.5,
            needs_confirmation=True,
        )
        text = _format_recognition(draft)
        assert "Проверь" in text

    def test_empty_enemies(self):
        draft = ValidatedDraft(
            allies=[1, 2],
            enemies=[],
            allies_names=["Анти-Маг", "Axe"],
            enemies_names=[],
            confidence=0.8,
            needs_confirmation=False,
        )
        text = _format_recognition(draft)
        assert "Союзники" in text
        assert "Противники" not in text


class TestFormatRecommendations:
    """Тесты форматирования рекомендаций пиков."""

    def test_basic(self):
        recs = [
            PickRecommendation(hero_id=1, name_ru="Анти-Маг", reason="Хороший контрпик"),
            PickRecommendation(hero_id=2, name_ru="Axe", reason="Сильный в мете"),
        ]
        text = _format_recommendations(recs)
        assert "Анти-Маг" in text
        assert "Axe" in text
        assert "Хороший контрпик" in text
        assert "Рекомендации пиков" in text

    def test_empty_reason(self):
        recs = [PickRecommendation(hero_id=1, name_ru="Анти-Маг", reason="")]
        text = _format_recommendations(recs)
        assert "Анти-Маг" in text

    def test_truncates_long_text(self):
        recs = [
            PickRecommendation(hero_id=i, name_ru=f"Герой {i}", reason="x" * 1000)
            for i in range(10)
        ]
        text = _format_recommendations(recs)
        assert len(text) <= 4096


class TestRecommendationsKeyboard:
    """Тесты создания клавиатуры рекомендаций."""

    def test_creates_buttons(self):
        recs = [
            PickRecommendation(hero_id=1, name_ru="Анти-Маг", reason="тест"),
            PickRecommendation(hero_id=2, name_ru="Axe", reason="тест"),
        ]
        kb = _recommendations_keyboard(recs)
        assert len(kb.inline_keyboard) == 2
        assert kb.inline_keyboard[0][0].callback_data == f"{_CB_DRAFT_PICK}1"
        assert kb.inline_keyboard[1][0].callback_data == f"{_CB_DRAFT_PICK}2"
        assert "Анти-Маг" in kb.inline_keyboard[0][0].text


# ---------------------------------------------------------------------------
# Утилита steam_to_account_id
# ---------------------------------------------------------------------------


class TestSteamToAccountId:
    def test_valid_steam_id(self):
        assert _steam_to_account_id("76561198000000001") == 76561198000000001 - 76561197960265728

    def test_none(self):
        assert _steam_to_account_id(None) is None

    def test_empty_string(self):
        assert _steam_to_account_id("") is None

    def test_invalid(self):
        assert _steam_to_account_id("notanumber") is None


# ---------------------------------------------------------------------------
# Хендлеры — проверка premium-гейта и регистрации
# ---------------------------------------------------------------------------


class TestCmdDraft:
    """Тесты для команды /draft."""

    @pytest.fixture
    def message(self):
        msg = AsyncMock()
        msg.answer = AsyncMock(return_value=AsyncMock())
        msg.text = "/draft"
        return msg

    @pytest.fixture
    def state(self):
        s = AsyncMock()
        s.clear = AsyncMock()
        s.set_state = AsyncMock()
        return s

    async def test_unregistered_user(self, message, state):
        from bot.handlers.draft import cmd_draft

        await cmd_draft(message, state, user=None)
        message.answer.assert_called_once()
        assert "зарегистрироваться" in message.answer.call_args[0][0]

    async def test_non_premium_user(self, message, state):
        from bot.handlers.draft import cmd_draft

        await cmd_draft(message, state, user={"id": 1}, is_premium=False)
        message.answer.assert_called_once()
        args = message.answer.call_args
        assert "Premium" in args[0][0]

    async def test_premium_user_enters_fsm(self, message, state):
        from bot.handlers.draft import cmd_draft
        from bot.states.draft import DraftStates

        await cmd_draft(message, state, user={"id": 1}, is_premium=True)
        state.clear.assert_called_once()
        state.set_state.assert_called_once_with(DraftStates.waiting_screenshot)


class TestBtnDraft:
    """Тесты для кнопки 'Анализ драфта'."""

    @pytest.fixture
    def message(self):
        msg = AsyncMock()
        msg.answer = AsyncMock(return_value=AsyncMock())
        msg.text = "Анализ драфта"
        return msg

    @pytest.fixture
    def state(self):
        s = AsyncMock()
        s.clear = AsyncMock()
        s.set_state = AsyncMock()
        return s

    async def test_unregistered(self, message, state):
        from bot.handlers.draft import btn_draft

        await btn_draft(message, state, user=None)
        assert "зарегистрироваться" in message.answer.call_args[0][0]

    async def test_non_premium(self, message, state):
        from bot.handlers.draft import btn_draft

        await btn_draft(message, state, user={"id": 1}, is_premium=False)
        assert "Premium" in message.answer.call_args[0][0]


class TestProcessNonPhoto:
    """Тесты для обработки не-фото в состоянии ожидания."""

    async def test_sends_hint(self):
        from bot.handlers.draft import process_non_photo

        msg = AsyncMock()
        msg.answer = AsyncMock()
        await process_non_photo(msg)
        assert "фото" in msg.answer.call_args[0][0].lower()


class TestRetryDraft:
    """Тесты для кнопки повтора."""

    async def test_retry_sets_state(self):
        from bot.handlers.draft import retry_draft
        from bot.states.draft import DraftStates

        callback = AsyncMock()
        callback.answer = AsyncMock()
        callback.message = AsyncMock()
        callback.message.edit_text = AsyncMock()

        state = AsyncMock()
        state.set_state = AsyncMock()

        await retry_draft(callback, state)
        callback.answer.assert_called_once()
        state.set_state.assert_called_once_with(DraftStates.waiting_screenshot)


class TestConfirmDraft:
    """Тесты для подтверждения драфта."""

    async def test_unregistered(self):
        from bot.handlers.draft import confirm_draft

        callback = AsyncMock()
        callback.answer = AsyncMock()
        state = AsyncMock()

        await confirm_draft(callback, state, user=None)
        callback.answer.assert_called_once()
        assert callback.answer.call_args[1].get("show_alert") is True


class TestPickHeroBuild:
    """Тесты для выбора героя из рекомендаций."""

    async def test_unregistered(self):
        from bot.handlers.draft import pick_hero_build

        callback = AsyncMock()
        callback.data = f"{_CB_DRAFT_PICK}1"
        callback.answer = AsyncMock()

        await pick_hero_build(callback, user=None)
        callback.answer.assert_called_once()
        assert callback.answer.call_args[1].get("show_alert") is True

    async def test_invalid_data(self):
        from bot.handlers.draft import pick_hero_build

        callback = AsyncMock()
        callback.data = f"{_CB_DRAFT_PICK}abc"
        callback.answer = AsyncMock()

        await pick_hero_build(callback, user={"id": 1})
        callback.answer.assert_called_once()
        assert "Некорректный" in callback.answer.call_args[0][0]
