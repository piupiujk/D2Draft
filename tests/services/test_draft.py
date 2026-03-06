"""Тесты для services/draft.py — сервис распознавания драфта."""

from unittest.mock import AsyncMock

from clients.llm import DraftRecognition, LLMClient
from services.draft import (
    ValidatedDraft,
    _validate_recognition,
    recognize_draft,
)

# ---------------------------------------------------------------------------
# _validate_recognition
# ---------------------------------------------------------------------------


class TestValidateRecognition:
    def test_valid_full_draft(self):
        """Полный драфт с валидными hero_id."""
        rec = DraftRecognition(
            allies=[1, 14, 22, 86, 30],
            enemies=[8, 97, 39, 50, 26],
            user_role=1,
            confidence=0.95,
            raw_response="allies:1,14,22,86,30|enemies:8,97,39,50,26|role:1|confidence:0.95",
        )
        result = _validate_recognition(rec)

        assert result.allies == [1, 14, 22, 86, 30]
        assert result.enemies == [8, 97, 39, 50, 26]
        assert result.user_role == 1
        assert result.confidence == 0.95
        assert not result.needs_confirmation
        assert len(result.allies_names) == 5
        assert len(result.enemies_names) == 5
        assert result.allies_names[0] == "Анти-Маг"

    def test_partial_draft(self):
        """Неполный драфт (3 vs 2)."""
        rec = DraftRecognition(
            allies=[44, 5, 29],
            enemies=[74, 87],
            user_role=0,
            confidence=0.8,
            raw_response="allies:44,5,29|enemies:74,87|role:0|confidence:0.8",
        )
        result = _validate_recognition(rec)

        assert len(result.allies) == 3
        assert len(result.enemies) == 2
        assert result.user_role is None  # role=0 -> None
        assert result.confidence == 0.8
        assert not result.needs_confirmation

    def test_invalid_hero_ids(self):
        """Невалидные hero_id отфильтровываются, уверенность снижается."""
        rec = DraftRecognition(
            allies=[1, 9999],  # 9999 невалидный
            enemies=[8, 7777],  # 7777 невалидный
            confidence=0.9,
            raw_response="allies:1,9999|enemies:8,7777|role:0|confidence:0.9",
        )
        result = _validate_recognition(rec)

        assert result.allies == [1]
        assert result.enemies == [8]
        assert result.invalid_ids == [9999, 7777]
        # Уверенность пересчитана: 0.9 * (2/4) = 0.45
        assert abs(result.confidence - 0.45) < 0.01
        assert result.needs_confirmation  # < порога

    def test_empty_draft(self):
        """Пустой драфт — confidence=0, needs_confirmation."""
        rec = DraftRecognition(
            allies=[],
            enemies=[],
            confidence=0.0,
            raw_response="allies:|enemies:|role:0|confidence:0.0",
        )
        result = _validate_recognition(rec)

        assert result.allies == []
        assert result.enemies == []
        assert result.confidence == 0.0
        assert result.needs_confirmation

    def test_low_confidence_triggers_confirmation(self):
        """confidence < порога -> needs_confirmation=True."""
        rec = DraftRecognition(
            allies=[1],
            enemies=[8],
            confidence=0.5,
            raw_response="allies:1|enemies:8|role:0|confidence:0.5",
        )
        result = _validate_recognition(rec)

        assert result.needs_confirmation

    def test_parser_needs_confirmation_propagated(self):
        """needs_confirmation от парсера сохраняется."""
        rec = DraftRecognition(
            allies=[1, 2],
            enemies=[3, 4],
            confidence=0.9,
            needs_confirmation=True,
            raw_response="test",
        )
        result = _validate_recognition(rec)

        assert result.needs_confirmation

    def test_role_zero_becomes_none(self):
        """user_role=0 преобразуется в None."""
        rec = DraftRecognition(
            allies=[1],
            enemies=[2],
            user_role=0,
            confidence=0.8,
            raw_response="test",
        )
        result = _validate_recognition(rec)

        assert result.user_role is None


# ---------------------------------------------------------------------------
# recognize_draft (интеграция с LLMClient)
# ---------------------------------------------------------------------------


class TestRecognizeDraft:
    async def test_calls_llm_and_validates(self):
        """recognize_draft вызывает llm_client.recognize_draft и валидирует."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recognize_draft.return_value = DraftRecognition(
            allies=[1, 14, 22],
            enemies=[8, 97],
            user_role=2,
            confidence=0.85,
            raw_response="allies:1,14,22|enemies:8,97|role:2|confidence:0.85",
        )

        result = await recognize_draft(b"fake_image_data", mock_llm)

        mock_llm.recognize_draft.assert_awaited_once_with(b"fake_image_data")
        assert isinstance(result, ValidatedDraft)
        assert result.allies == [1, 14, 22]
        assert result.enemies == [8, 97]
        assert result.user_role == 2
        assert not result.needs_confirmation

    async def test_blurry_image_low_confidence(self):
        """Размытое изображение — низкая уверенность, needs_confirmation."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recognize_draft.return_value = DraftRecognition(
            allies=[1],
            enemies=[],
            user_role=0,
            confidence=0.3,
            raw_response="allies:1|enemies:|role:0|confidence:0.3",
        )

        result = await recognize_draft(b"blurry_image", mock_llm)

        assert result.needs_confirmation
        assert result.confidence == 0.3

    async def test_unreadable_image(self):
        """Нечитаемое изображение — пустой результат."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recognize_draft.return_value = DraftRecognition(
            allies=[],
            enemies=[],
            user_role=0,
            confidence=0.0,
            needs_confirmation=True,
            raw_response="allies:|enemies:|role:0|confidence:0.0",
        )

        result = await recognize_draft(b"bad_image", mock_llm)

        assert result.needs_confirmation
        assert result.confidence == 0.0
        assert result.allies == []
        assert result.enemies == []
