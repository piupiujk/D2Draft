"""Тесты для clients/llm.py — LLMClient."""

import asyncio
import json
import os
from unittest.mock import AsyncMock

import httpx

from clients.llm import (
    DraftRecognition,
    LLMClient,
    LLMResponse,
    PickRecommendation,
    _parse_draft_recognition,
    _parse_pick_recommendations,
    _RateLimiter,
    load_prompt,
)
from core.exceptions import APIRateLimited

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

def _json_response(data: object, status_code: int = 200) -> httpx.Response:
    """Создать мок-ответ httpx."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("POST", "https://api.example.com/test"),
    )


OPENAI_CHAT_RESPONSE = {
    "choices": [{"message": {"content": "Тестовый ответ от OpenAI"}}],
    "model": "gpt-4o-mini",
    "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
}

ANTHROPIC_MESSAGES_RESPONSE = {
    "content": [{"type": "text", "text": "Тестовый ответ от Anthropic"}],
    "model": "claude-sonnet-4-20250514",
    "usage": {"input_tokens": 15, "output_tokens": 25},
}


# ---------------------------------------------------------------------------
# Тесты RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_acquire_does_not_block_when_tokens_available(self) -> None:
        limiter = _RateLimiter(max_tokens=10, refill_period=60.0)
        for _ in range(10):
            asyncio.run(limiter.acquire())


# ---------------------------------------------------------------------------
# Тесты load_prompt
# ---------------------------------------------------------------------------

class TestLoadPrompt:
    def test_returns_empty_string_for_missing_file(self) -> None:
        result = load_prompt("nonexistent_prompt_12345")
        assert result == ""

    def test_loads_existing_prompt(self) -> None:
        # Создаём временный файл промпта
        from clients.llm import _PROMPTS_DIR
        os.makedirs(_PROMPTS_DIR, exist_ok=True)
        test_file = _PROMPTS_DIR / "test_prompt_xyz.txt"
        try:
            test_file.write_text("Тестовый промпт", encoding="utf-8")
            result = load_prompt("test_prompt_xyz")
            assert result == "Тестовый промпт"
        finally:
            test_file.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Тесты конструктора LLMClient
# ---------------------------------------------------------------------------

class TestLLMClientInit:
    def test_creates_with_openai_provider(self) -> None:
        client = LLMClient(api_key="test-key", provider="openai")
        assert client._provider == "openai"

    def test_creates_with_anthropic_provider(self) -> None:
        client = LLMClient(api_key="test-key", provider="anthropic")
        assert client._provider == "anthropic"

    def test_provider_case_insensitive(self) -> None:
        client = LLMClient(api_key="test-key", provider="OpenAI")
        assert client._provider == "openai"

    def test_raises_for_unknown_provider(self) -> None:
        import pytest
        with pytest.raises(ValueError, match="Неизвестный LLM-провайдер"):
            LLMClient(api_key="test-key", provider="gemini")

    def test_accepts_external_client(self) -> None:
        mock_client = AsyncMock(spec=httpx.AsyncClient)
        llm = LLMClient(api_key="test-key", client=mock_client)
        assert llm._external_client is True

    def test_creates_own_client_if_none_provided(self) -> None:
        llm = LLMClient(api_key="test-key")
        assert llm._external_client is False


# ---------------------------------------------------------------------------
# Тесты context manager
# ---------------------------------------------------------------------------

class TestLLMClientContextManager:
    def test_enter_returns_self(self) -> None:
        client = LLMClient(api_key="test-key")
        result = asyncio.run(client.__aenter__())
        assert result is client

    def test_exit_closes_own_client(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        client = LLMClient(api_key="test-key")
        client._client = mock_http
        asyncio.run(client.__aexit__(None, None, None))
        mock_http.aclose.assert_awaited_once()

    def test_exit_does_not_close_external_client(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        client = LLMClient(api_key="test-key", client=mock_http)
        asyncio.run(client.__aexit__(None, None, None))
        mock_http.aclose.assert_not_awaited()


# ---------------------------------------------------------------------------
# Тесты OpenAI complete
# ---------------------------------------------------------------------------

class TestOpenAIComplete:
    def test_returns_llm_response(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.complete("Привет"))

        assert isinstance(result, LLMResponse)
        assert result.text == "Тестовый ответ от OpenAI"
        assert result.model == "gpt-4o-mini"
        assert result.usage_tokens == 30

    def test_sends_system_message(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        asyncio.run(client.complete("Привет", system="Ты помощник"))

        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        messages = body["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Ты помощник"

    def test_uses_bearer_auth(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="sk-test-123", provider="openai", client=mock_http)
        asyncio.run(client.complete("Тест"))

        call_kwargs = mock_http.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["Authorization"] == "Bearer sk-test-123"

    def test_custom_model(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        asyncio.run(client.complete("Тест", model="gpt-4o"))

        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["model"] == "gpt-4o"

    def test_without_system_message(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        asyncio.run(client.complete("Привет"))

        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        messages = body["messages"]
        # Без system — только user
        assert len(messages) == 1
        assert messages[0]["role"] == "user"


# ---------------------------------------------------------------------------
# Тесты Anthropic complete
# ---------------------------------------------------------------------------

class TestAnthropicComplete:
    def test_returns_llm_response(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            return_value=_json_response(ANTHROPIC_MESSAGES_RESPONSE)
        )

        client = LLMClient(api_key="test-key", provider="anthropic", client=mock_http)
        result = asyncio.run(client.complete("Привет"))

        assert isinstance(result, LLMResponse)
        assert result.text == "Тестовый ответ от Anthropic"
        assert result.model == "claude-sonnet-4-20250514"
        assert result.usage_tokens == 40  # 15 + 25

    def test_uses_x_api_key_header(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            return_value=_json_response(ANTHROPIC_MESSAGES_RESPONSE)
        )

        client = LLMClient(api_key="sk-ant-123", provider="anthropic", client=mock_http)
        asyncio.run(client.complete("Тест"))

        call_kwargs = mock_http.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
        assert headers["x-api-key"] == "sk-ant-123"
        assert headers["anthropic-version"] == "2023-06-01"

    def test_system_in_body_not_messages(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            return_value=_json_response(ANTHROPIC_MESSAGES_RESPONSE)
        )

        client = LLMClient(api_key="test-key", provider="anthropic", client=mock_http)
        asyncio.run(client.complete("Привет", system="Ты аналитик"))

        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert body["system"] == "Ты аналитик"
        # system НЕ в messages
        for msg in body["messages"]:
            assert msg["role"] != "system"

    def test_no_system_key_when_empty(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            return_value=_json_response(ANTHROPIC_MESSAGES_RESPONSE)
        )

        client = LLMClient(api_key="test-key", provider="anthropic", client=mock_http)
        asyncio.run(client.complete("Привет"))

        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert "system" not in body


# ---------------------------------------------------------------------------
# Тесты OpenAI Vision
# ---------------------------------------------------------------------------

class TestOpenAIVision:
    def test_sends_base64_image(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.vision(b"\x89PNG\r\n", "Опиши изображение"))

        assert isinstance(result, LLMResponse)
        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        user_msg = body["messages"][-1]
        assert user_msg["role"] == "user"
        assert user_msg["content"][0]["type"] == "image_url"
        assert "base64" in user_msg["content"][0]["image_url"]["url"]


# ---------------------------------------------------------------------------
# Тесты Anthropic Vision
# ---------------------------------------------------------------------------

class TestAnthropicVision:
    def test_sends_base64_image(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            return_value=_json_response(ANTHROPIC_MESSAGES_RESPONSE)
        )

        client = LLMClient(api_key="test-key", provider="anthropic", client=mock_http)
        result = asyncio.run(client.vision(b"\x89PNG\r\n", "Опиши"))

        assert isinstance(result, LLMResponse)
        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        user_msg = body["messages"][0]
        assert user_msg["content"][0]["type"] == "image"
        assert user_msg["content"][0]["source"]["type"] == "base64"


# ---------------------------------------------------------------------------
# Тесты retry и обработки ошибок
# ---------------------------------------------------------------------------

class TestRetryLogic:
    def test_retries_on_500(self) -> None:
        error_resp = _json_response({"error": "server"}, status_code=500)
        ok_resp = _json_response(OPENAI_CHAT_RESPONSE)
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(side_effect=[error_resp, ok_resp])

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.complete("Тест"))

        assert result.text == "Тестовый ответ от OpenAI"
        assert mock_http.post.call_count == 2

    def test_raises_api_rate_limited_on_429(self) -> None:
        error_resp = httpx.Response(
            status_code=429,
            content=b'{"error": "rate limited"}',
            headers={"content-type": "application/json", "retry-after": "1"},
            request=httpx.Request("POST", "https://api.example.com/test"),
        )
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=error_resp)

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)

        import pytest
        with pytest.raises(APIRateLimited, match="LLM"):
            asyncio.run(client.complete("Тест"))

    def test_retries_on_network_error(self) -> None:
        ok_resp = _json_response(OPENAI_CHAT_RESPONSE)
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            side_effect=[httpx.ConnectError("Нет соединения"), ok_resp]
        )

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.complete("Тест"))

        assert result.text == "Тестовый ответ от OpenAI"

    def test_raises_on_4xx_without_retry(self) -> None:
        error_resp = _json_response({"error": "bad request"}, status_code=400)
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=error_resp)

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)

        import pytest
        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(client.complete("Тест"))

        # Без retry — только 1 вызов
        assert mock_http.post.call_count == 1


# ---------------------------------------------------------------------------
# Тесты summarize_match
# ---------------------------------------------------------------------------

class TestSummarizeMatch:
    def test_returns_string(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.summarize_match({"hero": "Anti-Mage", "kda": "10/3/5"}))

        assert isinstance(result, str)
        assert len(result) > 0

    def test_sends_stats_in_prompt(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        asyncio.run(client.summarize_match({"hero": "Pudge"}))

        call_kwargs = mock_http.post.call_args
        body = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        user_msg = body["messages"][-1]["content"]
        assert "Pudge" in user_msg


# ---------------------------------------------------------------------------
# Тесты recommend_picks
# ---------------------------------------------------------------------------

class TestRecommendPicks:
    def test_returns_list_of_recommendations(self) -> None:
        response_text = "1|Anti-Mage|Контрит мана-зависимых\n2|Axe|Хорош против мили\n"
        resp_data = {
            "choices": [{"message": {"content": response_text}}],
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 50},
        }
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(resp_data))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.recommend_picks({"allies": [1, 2], "enemies": [3, 4]}))

        assert len(result) == 2
        assert isinstance(result[0], PickRecommendation)
        assert result[0].hero_id == 1
        assert result[0].name_ru == "Anti-Mage"
        assert result[0].reason == "Контрит мана-зависимых"

    def test_empty_when_bad_format(self) -> None:
        resp_data = {
            "choices": [{"message": {"content": "Извините, не могу помочь"}}],
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 10},
        }
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(resp_data))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.recommend_picks({"allies": [], "enemies": []}))

        assert result == []


# ---------------------------------------------------------------------------
# Тесты recognize_draft
# ---------------------------------------------------------------------------

class TestRecognizeDraft:
    def test_returns_draft_recognition(self) -> None:
        response_text = "allies:1,2,3,4,5|enemies:6,7,8,9,10|role:1|confidence:0.9"
        resp_data = {
            "choices": [{"message": {"content": response_text}}],
            "model": "gpt-4o-mini",
            "usage": {"total_tokens": 100},
        }
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(resp_data))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        result = asyncio.run(client.recognize_draft(b"\x89PNG\r\n"))

        assert isinstance(result, DraftRecognition)
        assert result.allies == [1, 2, 3, 4, 5]
        assert result.enemies == [6, 7, 8, 9, 10]
        assert result.user_role == 1
        assert result.confidence == 0.9
        assert result.needs_confirmation is False


# ---------------------------------------------------------------------------
# Тесты парсеров
# ---------------------------------------------------------------------------

class TestParseDraftRecognition:
    def test_parses_valid_format(self) -> None:
        text = "allies:1,2,3|enemies:4,5,6|role:2|confidence:0.85"
        result = _parse_draft_recognition(text)
        assert result.allies == [1, 2, 3]
        assert result.enemies == [4, 5, 6]
        assert result.user_role == 2
        assert result.confidence == 0.85
        assert result.needs_confirmation is False

    def test_low_confidence_needs_confirmation(self) -> None:
        text = "allies:1,2|enemies:3,4|role:1|confidence:0.5"
        result = _parse_draft_recognition(text)
        assert result.needs_confirmation is True

    def test_invalid_format_needs_confirmation(self) -> None:
        text = "Не могу распознать драфт на этом скриншоте"
        result = _parse_draft_recognition(text)
        assert result.needs_confirmation is True
        assert result.confidence == 0.0

    def test_partial_data(self) -> None:
        text = "allies:1,2,3|enemies:4,5"
        result = _parse_draft_recognition(text)
        assert result.allies == [1, 2, 3]
        assert result.enemies == [4, 5]
        assert result.user_role is None

    def test_empty_allies(self) -> None:
        text = "allies:|enemies:1,2,3|role:1|confidence:0.8"
        result = _parse_draft_recognition(text)
        assert result.allies == []
        assert result.enemies == [1, 2, 3]

    def test_raw_response_preserved(self) -> None:
        text = "allies:1|enemies:2|confidence:0.9"
        result = _parse_draft_recognition(text)
        assert result.raw_response == text


class TestParsePickRecommendations:
    def test_parses_valid_lines(self) -> None:
        text = "1|Антимаг|Контрит мана-зависимых\n2|Акс|Хорош в оффлейне"
        result = _parse_pick_recommendations(text)
        assert len(result) == 2
        assert result[0].hero_id == 1
        assert result[0].name_ru == "Антимаг"
        assert result[1].hero_id == 2

    def test_skips_invalid_lines(self) -> None:
        text = "# Рекомендации\nне парсится\n1|Антимаг|Причина"
        result = _parse_pick_recommendations(text)
        assert len(result) == 1
        assert result[0].hero_id == 1

    def test_skips_empty_lines(self) -> None:
        text = "\n\n1|Антимаг|Причина\n\n"
        result = _parse_pick_recommendations(text)
        assert len(result) == 1

    def test_empty_input(self) -> None:
        result = _parse_pick_recommendations("")
        assert result == []

    def test_non_numeric_hero_id_skipped(self) -> None:
        text = "abc|Антимаг|Причина\n1|Акс|Причина"
        result = _parse_pick_recommendations(text)
        assert len(result) == 1
        assert result[0].hero_id == 1


# ---------------------------------------------------------------------------
# Тесты переключения провайдера
# ---------------------------------------------------------------------------

class TestProviderSwitching:
    def test_openai_uses_chat_completions_url(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(return_value=_json_response(OPENAI_CHAT_RESPONSE))

        client = LLMClient(api_key="test-key", provider="openai", client=mock_http)
        asyncio.run(client.complete("Тест"))

        url = mock_http.post.call_args.args[0] if mock_http.post.call_args.args else \
            mock_http.post.call_args.kwargs.get("url", "")
        assert "/chat/completions" in url

    def test_anthropic_uses_messages_url(self) -> None:
        mock_http = AsyncMock(spec=httpx.AsyncClient)
        mock_http.post = AsyncMock(
            return_value=_json_response(ANTHROPIC_MESSAGES_RESPONSE)
        )

        client = LLMClient(api_key="test-key", provider="anthropic", client=mock_http)
        asyncio.run(client.complete("Тест"))

        url = mock_http.post.call_args.args[0] if mock_http.post.call_args.args else \
            mock_http.post.call_args.kwargs.get("url", "")
        assert "/messages" in url
