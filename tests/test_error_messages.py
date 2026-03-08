"""Тесты для модуля graceful degradation: core/error_messages.py."""

import httpx

from core.error_messages import (
    LLM_DRAFT_FALLBACK,
    LLM_UNAVAILABLE,
    OPENDOTA_UNAVAILABLE,
    STRATZ_UNAVAILABLE,
    classify_api_error,
)
from core.exceptions import APIRateLimited, ExternalAPIError


class TestClassifyApiError:
    """Тесты classify_api_error — различение типов ошибок."""

    def test_rate_limited_with_retry(self):
        exc = APIRateLimited("Stratz", retry_after=30.0)
        msg = classify_api_error(exc)
        assert "Stratz" in msg
        assert "30" in msg

    def test_rate_limited_without_retry(self):
        exc = APIRateLimited("OpenDota")
        msg = classify_api_error(exc)
        assert "много запросов" in msg.lower()

    def test_timeout_error(self):
        exc = httpx.ReadTimeout("таймаут")
        msg = classify_api_error(exc)
        assert "не отвечает" in msg.lower()

    def test_connect_error(self):
        exc = httpx.ConnectError("не удалось подключиться")
        msg = classify_api_error(exc)
        assert "подключиться" in msg.lower()

    def test_http_status_429(self):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(429, request=request)
        exc = httpx.HTTPStatusError("rate limited", request=request, response=response)
        msg = classify_api_error(exc)
        assert "много запросов" in msg.lower()

    def test_http_status_500(self):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(500, request=request)
        exc = httpx.HTTPStatusError("server error", request=request, response=response)
        msg = classify_api_error(exc)
        assert "недоступен" in msg.lower()

    def test_http_status_400(self):
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(400, request=request)
        exc = httpx.HTTPStatusError("bad request", request=request, response=response)
        msg = classify_api_error(exc)
        assert "ошибка" in msg.lower()

    def test_external_api_error(self):
        exc = ExternalAPIError("Stratz", original=RuntimeError("test"))
        msg = classify_api_error(exc)
        assert "Stratz" in msg

    def test_generic_exception(self):
        exc = RuntimeError("что-то пошло не так")
        msg = classify_api_error(exc)
        assert "непредвиденная" in msg.lower()


class TestErrorConstants:
    """Тесты что константы содержат осмысленные сообщения."""

    def test_stratz_unavailable(self):
        assert "мет" in STRATZ_UNAVAILABLE.lower()

    def test_opendota_unavailable(self):
        assert "матч" in OPENDOTA_UNAVAILABLE.lower()

    def test_llm_unavailable(self):
        assert "AI" in LLM_UNAVAILABLE

    def test_llm_draft_fallback(self):
        assert "скриншот" in LLM_DRAFT_FALLBACK.lower()


class TestExternalAPIError:
    """Тесты для нового исключения ExternalAPIError."""

    def test_with_original(self):
        original = RuntimeError("connection reset")
        exc = ExternalAPIError("Stratz", original=original)
        assert exc.service == "Stratz"
        assert exc.original is original
        assert "Stratz" in str(exc)

    def test_without_original(self):
        exc = ExternalAPIError("OpenDota")
        assert exc.service == "OpenDota"
        assert exc.original is None
        assert "OpenDota" in str(exc)
