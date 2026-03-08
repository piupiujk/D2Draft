"""Тесты graceful degradation: хендлеры корректно обрабатывают ошибки API.

Проверяем что при недоступности Stratz, OpenDota и LLM API
пользователь получает информативное сообщение, а не crash.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from core.exceptions import ExternalAPIError

# ---------------------------------------------------------------------------
# Общие фикстуры
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_user() -> dict:
    """Тестовый пользователь."""
    return {
        "id": "uuid-123",
        "telegram_id": 12345,
        "steam_id": "76561198000000001",
        "current_mmr": 4000,
        "main_role": 1,
        "is_premium": True,
        "premium_expires_at": "2099-01-01T00:00:00",
    }


@pytest.fixture()
def mock_message() -> AsyncMock:
    """Мок Telegram-сообщения."""
    msg = AsyncMock()
    msg.answer = AsyncMock(return_value=AsyncMock())
    msg.from_user = MagicMock(id=12345)
    return msg


# ---------------------------------------------------------------------------
# ТЕСТ 1: Stratz API → 500 — хендлер meta отвечает информативно
# ---------------------------------------------------------------------------


class TestStratz500GracefulDegradation:
    """При ошибке Stratz API (500) бот отвечает информативно."""

    @patch("bot.handlers.meta.StratzClient")
    async def test_meta_handler_stratz_500(
        self, mock_stratz_cls, mock_message, test_user
    ):
        """Замокать Stratz API на 500 — бот отвечает информативно."""
        from bot.handlers.meta import _show_meta_heroes

        # Stratz выбрасывает HTTP 500
        request = httpx.Request("POST", "https://api.stratz.com/graphql")
        response = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("Internal Server Error", request=request, response=response)

        mock_stratz_instance = AsyncMock()
        mock_stratz_instance.__aenter__ = AsyncMock(return_value=mock_stratz_instance)
        mock_stratz_instance.__aexit__ = AsyncMock(return_value=False)
        mock_stratz_cls.return_value = mock_stratz_instance

        with patch("bot.handlers.meta.get_meta_heroes", side_effect=error):
            from core.enums import Role
            await _show_meta_heroes(mock_message, test_user, Role.CARRY)

        # Проверяем что пользователь получил информативное сообщение
        mock_message.answer.assert_called_once()
        msg_text = mock_message.answer.call_args[0][0]
        assert "недоступен" in msg_text.lower() or "ошибка" in msg_text.lower()

    @patch("bot.handlers.build.StratzClient")
    async def test_build_handler_stratz_500(
        self, mock_stratz_cls, mock_message, test_user
    ):
        """Ошибка Stratz при получении билда — информативное сообщение."""
        from bot.handlers.build import _show_build

        # Stratz выбрасывает ExternalAPIError
        error = ExternalAPIError("Stratz", original=RuntimeError("500"))

        mock_stratz_instance = AsyncMock()
        mock_stratz_instance.__aenter__ = AsyncMock(return_value=mock_stratz_instance)
        mock_stratz_instance.__aexit__ = AsyncMock(return_value=False)
        mock_stratz_cls.return_value = mock_stratz_instance

        with patch("bot.handlers.build.get_hero_build", side_effect=error):
            await _show_build(mock_message, test_user, hero_id=1, hero_name_ru="Анти-Маг")

        mock_message.answer.assert_called_once()
        msg_text = mock_message.answer.call_args[0][0]
        assert "Stratz" in msg_text or "недоступен" in msg_text.lower()


# ---------------------------------------------------------------------------
# ТЕСТ 2: OpenDota → timeout — хендлер match отвечает информативно
# ---------------------------------------------------------------------------


class TestOpenDotaTimeoutGracefulDegradation:
    """При таймауте OpenDota API бот отвечает информативно."""

    @patch("bot.handlers.match.MatchAnalysisRepository")
    @patch("bot.handlers.match.OpenDotaClient")
    async def test_match_handler_opendota_timeout(
        self, mock_opendota_cls, mock_repo_cls, mock_message, test_user
    ):
        """Замокать OpenDota на timeout — бот отвечает информативно."""
        from bot.handlers.match import _show_last_match

        # Мокаем loading_msg (message.answer возвращает его)
        loading_msg = AsyncMock()
        loading_msg.edit_text = AsyncMock()
        mock_message.answer = AsyncMock(return_value=loading_msg)

        # OpenDota выбрасывает таймаут
        error = httpx.ReadTimeout("Connection timed out")

        mock_opendota_instance = AsyncMock()
        mock_opendota_instance.__aenter__ = AsyncMock(return_value=mock_opendota_instance)
        mock_opendota_instance.__aexit__ = AsyncMock(return_value=False)
        mock_opendota_cls.return_value = mock_opendota_instance

        with patch("bot.handlers.match.analyze_last_match", side_effect=error):
            await _show_last_match(mock_message, test_user, is_premium=False)

        # Проверяем что edit_text вызван (не answer — т.к. loading_msg)
        loading_msg.edit_text.assert_called()
        msg_text = loading_msg.edit_text.call_args[0][0]
        assert "не отвечает" in msg_text.lower()

    @patch("bot.handlers.match.MatchAnalysisRepository")
    @patch("bot.handlers.match.OpenDotaClient")
    async def test_match_handler_opendota_connect_error(
        self, mock_opendota_cls, mock_repo_cls, mock_message, test_user
    ):
        """OpenDota ConnectError — информативное сообщение."""
        from bot.handlers.match import _show_last_match

        loading_msg = AsyncMock()
        loading_msg.edit_text = AsyncMock()
        mock_message.answer = AsyncMock(return_value=loading_msg)

        error = httpx.ConnectError("Connection refused")

        mock_opendota_instance = AsyncMock()
        mock_opendota_instance.__aenter__ = AsyncMock(return_value=mock_opendota_instance)
        mock_opendota_instance.__aexit__ = AsyncMock(return_value=False)
        mock_opendota_cls.return_value = mock_opendota_instance

        with patch("bot.handlers.match.analyze_last_match", side_effect=error):
            await _show_last_match(mock_message, test_user, is_premium=False)

        loading_msg.edit_text.assert_called()
        msg_text = loading_msg.edit_text.call_args[0][0]
        assert "подключиться" in msg_text.lower()

    @patch("bot.handlers.match.MatchAnalysisRepository")
    @patch("bot.handlers.match.OpenDotaClient")
    async def test_match_handler_no_matches(
        self, mock_opendota_cls, mock_repo_cls, mock_message, test_user
    ):
        """Нет матчей — специализированное сообщение (не crash)."""
        from bot.handlers.match import _show_last_match

        loading_msg = AsyncMock()
        loading_msg.edit_text = AsyncMock()
        mock_message.answer = AsyncMock(return_value=loading_msg)

        error = ValueError("У игрока нет недавних матчей")

        mock_opendota_instance = AsyncMock()
        mock_opendota_instance.__aenter__ = AsyncMock(return_value=mock_opendota_instance)
        mock_opendota_instance.__aexit__ = AsyncMock(return_value=False)
        mock_opendota_cls.return_value = mock_opendota_instance

        with patch("bot.handlers.match.analyze_last_match", side_effect=error):
            await _show_last_match(mock_message, test_user, is_premium=False)

        loading_msg.edit_text.assert_called()
        msg_text = loading_msg.edit_text.call_args[0][0]
        # Должен получить сообщение о отсутствии матчей, а не crash
        assert len(msg_text) > 10


# ---------------------------------------------------------------------------
# ТЕСТ 3: LLM API → ошибка — предложен fallback
# ---------------------------------------------------------------------------


class TestLLMErrorGracefulDegradation:
    """При ошибке LLM API предлагается fallback (текстовый ввод)."""

    def test_llm_draft_fallback_message_suggests_manual_input(self):
        """LLM_DRAFT_FALLBACK содержит предложение ввести героев вручную."""
        from core.error_messages import LLM_DRAFT_FALLBACK

        assert "AI" in LLM_DRAFT_FALLBACK
        assert "/draft" in LLM_DRAFT_FALLBACK
        # Предлагает альтернативу — ввод вручную
        assert "вручную" in LLM_DRAFT_FALLBACK.lower()

    @patch("bot.handlers.match.LLMClient")
    async def test_ai_advice_llm_error(self, mock_llm_cls, mock_message, test_user):
        """Ошибка LLM при AI-совете — информативное сообщение."""
        from bot.handlers.match import process_ai_advice

        error = ExternalAPIError("LLM", original=RuntimeError("API unavailable"))

        mock_callback = AsyncMock()
        mock_callback.data = "ai_advice:12345"
        mock_callback.message = mock_message
        mock_callback.answer = AsyncMock()

        loading_msg = AsyncMock()
        loading_msg.edit_text = AsyncMock()
        mock_message.edit_text = AsyncMock(return_value=loading_msg)
        mock_message.answer = AsyncMock(return_value=loading_msg)

        mock_llm_instance = AsyncMock()
        mock_llm_cls.return_value = mock_llm_instance

        with (
            patch("bot.handlers.match.get_llm_advice", side_effect=error),
            patch("bot.handlers.match.MatchAnalysisRepository") as mock_repo_cls,
        ):
            mock_repo = AsyncMock()
            mock_repo.get_by_match_id = AsyncMock(return_value={
                "match_id": 12345,
                "hero_id": 1,
                "hero_name_ru": "Анти-Маг",
                "role": "carry",
                "duration_minutes": 35.0,
                "result": "win",
                "stats": {},
            })
            mock_repo_cls.return_value = mock_repo

            await process_ai_advice(mock_callback, test_user)

        # Должен ответить информативно (через callback.answer или edit_text)
        # Проверяем что не было необработанного исключения
        assert mock_callback.answer.called or mock_message.edit_text.called


# ---------------------------------------------------------------------------
# ТЕСТ 4: Общий graceful degradation — classify_api_error
# ---------------------------------------------------------------------------


class TestClassifyApiErrorComprehensive:
    """Дополнительные тесты classify_api_error для edge cases."""

    def test_all_error_types_return_string(self):
        """Все типы ошибок возвращают непустую строку (не None)."""
        from core.error_messages import classify_api_error
        from core.exceptions import APIRateLimited, ExternalAPIError

        errors = [
            APIRateLimited("Stratz", retry_after=10.0),
            APIRateLimited("OpenDota"),
            httpx.ReadTimeout("timeout"),
            httpx.ConnectTimeout("timeout"),
            httpx.ConnectError("refused"),
            ExternalAPIError("Stratz"),
            ExternalAPIError("OpenDota", original=RuntimeError("500")),
            ExternalAPIError("LLM"),
            RuntimeError("unexpected"),
            ValueError("bad value"),
            KeyError("missing"),
        ]

        for error in errors:
            msg = classify_api_error(error)
            assert isinstance(msg, str), f"Ожидалась строка для {type(error).__name__}"
            assert len(msg) > 0, f"Пустое сообщение для {type(error).__name__}"
            assert len(msg) < 300, f"Слишком длинное сообщение для {type(error).__name__}"

    def test_http_502_503_gives_unavailable_message(self):
        """HTTP 502/503 → сообщение о недоступности."""
        from core.error_messages import classify_api_error

        for status_code in [502, 503]:
            request = httpx.Request("GET", "https://api.example.com")
            response = httpx.Response(status_code, request=request)
            exc = httpx.HTTPStatusError("error", request=request, response=response)
            msg = classify_api_error(exc)
            assert "недоступен" in msg.lower()

    def test_user_message_is_russian(self):
        """Все сообщения на русском языке."""
        from core.error_messages import classify_api_error

        exc = httpx.ReadTimeout("timeout")
        msg = classify_api_error(exc)
        # Проверяем наличие кириллических символов
        assert any("\u0400" <= c <= "\u04ff" for c in msg)
