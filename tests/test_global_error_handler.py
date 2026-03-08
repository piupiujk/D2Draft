"""Тесты для глобального обработчика ошибок в bot/__main__.py."""


import httpx

from core.error_messages import classify_api_error
from core.exceptions import APIRateLimited


class TestGlobalErrorHandlerMessages:
    """Тесты что глобальный error handler формирует правильные сообщения."""

    def test_stratz_500_gives_informative_message(self):
        """Stratz 500 → информативное сообщение, не crash."""
        request = httpx.Request("POST", "https://api.stratz.com/graphql")
        response = httpx.Response(500, request=request)
        exc = httpx.HTTPStatusError("Internal Server Error", request=request, response=response)
        msg = classify_api_error(exc)
        assert "недоступен" in msg.lower()
        assert len(msg) < 200

    def test_opendota_timeout_gives_informative_message(self):
        """OpenDota таймаут → информативное сообщение."""
        exc = httpx.ReadTimeout("Connection timed out")
        msg = classify_api_error(exc)
        assert "не отвечает" in msg.lower()
        assert len(msg) < 200

    def test_llm_error_gives_informative_message(self):
        """Ошибка LLM → общее информативное сообщение."""
        exc = RuntimeError("LLM API error")
        msg = classify_api_error(exc)
        assert "ошибка" in msg.lower()
        assert len(msg) < 200

    def test_rate_limit_with_retry_after(self):
        """Rate limit с retry_after → сообщение с временем ожидания."""
        exc = APIRateLimited("Stratz", retry_after=60.0)
        msg = classify_api_error(exc)
        assert "60" in msg
        assert "Stratz" in msg
