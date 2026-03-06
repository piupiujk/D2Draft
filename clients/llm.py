"""Унифицированный LLM-клиент: интерфейс для Vision и текстовых запросов."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from core.exceptions import APIRateLimited

# ---------------------------------------------------------------------------
# Модели ответов
# ---------------------------------------------------------------------------

@dataclass
class DraftRecognition:
    """Результат распознавания драфта из скриншота."""

    allies: list[int] = field(default_factory=list)
    enemies: list[int] = field(default_factory=list)
    user_role: int | None = None
    confidence: float = 0.0
    needs_confirmation: bool = False
    raw_response: str = ""


@dataclass
class PickRecommendation:
    """Рекомендация пика для драфта."""

    hero_id: int = 0
    name_ru: str = ""
    reason: str = ""


@dataclass
class LLMResponse:
    """Общий ответ от LLM."""

    text: str = ""
    model: str = ""
    usage_tokens: int = 0


# ---------------------------------------------------------------------------
# Конфигурация провайдеров
# ---------------------------------------------------------------------------

_PROVIDER_CONFIG: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "vision_model": "gpt-4o-mini",
        "auth_header": "Bearer",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-20250514",
        "vision_model": "claude-sonnet-4-20250514",
        "auth_header": "x-api-key",
    },
}

# ---------------------------------------------------------------------------
# Загрузка промптов
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str) -> str:
    """Загрузить промпт из файла prompts/{name}.txt.

    Возвращает пустую строку, если файл не найден.
    """
    path = _PROMPTS_DIR / f"{name}.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    return ""


# ---------------------------------------------------------------------------
# Rate limiter (token bucket)
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Простой token-bucket rate limiter для LLM API."""

    def __init__(self, max_tokens: int = 20, refill_period: float = 60.0) -> None:
        self._max_tokens = max_tokens
        self._refill_period = refill_period
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            self._refill()
            if self._tokens < 1:
                wait = self._refill_period * (1 - self._tokens) / self._max_tokens
                await asyncio.sleep(wait)
                self._refill()
            self._tokens -= 1

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._max_tokens,
            self._tokens + elapsed * (self._max_tokens / self._refill_period),
        )
        self._last_refill = now


# ---------------------------------------------------------------------------
# Retry-конфигурация
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.0
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# Клиент LLM
# ---------------------------------------------------------------------------

class LLMClient:
    """Унифицированный async-клиент для LLM API (OpenAI и Anthropic)."""

    def __init__(
        self,
        api_key: str,
        provider: str = "openai",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._provider = provider.lower()
        if self._provider not in _PROVIDER_CONFIG:
            msg = f"Неизвестный LLM-провайдер: {provider}. Доступны: openai, anthropic"
            raise ValueError(msg)
        self._config = _PROVIDER_CONFIG[self._provider]
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=60.0)
        self._limiter = _RateLimiter(max_tokens=20, refill_period=60.0)

    # -- публичные методы ---------------------------------------------------

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Текстовый запрос к LLM."""
        model = model or self._config["default_model"]

        if self._provider == "openai":
            return await self._openai_chat(
                prompt, system=system, model=model,
                max_tokens=max_tokens, temperature=temperature,
            )
        return await self._anthropic_messages(
            prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )

    async def vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        system: str = "",
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> LLMResponse:
        """Запрос с изображением (Vision) к LLM."""
        model = model or self._config["vision_model"]

        if self._provider == "openai":
            return await self._openai_vision(
                image_bytes, prompt, system=system, model=model,
                max_tokens=max_tokens, temperature=temperature,
            )
        return await self._anthropic_vision(
            image_bytes, prompt, system=system, model=model,
            max_tokens=max_tokens, temperature=temperature,
        )

    async def summarize_match(self, stats_dict: dict[str, Any]) -> str:
        """Сгенерировать текстовый разбор матча."""
        system = load_prompt("match_summary")
        if not system:
            system = (
                "Ты — аналитик Dota 2. Проанализируй статистику матча и дай краткие, "
                "конкретные советы по улучшению игры. Отвечай на русском языке."
            )
        import json
        stats_json = json.dumps(stats_dict, ensure_ascii=False, indent=2)
        prompt = f"Статистика матча:\n```json\n{stats_json}\n```"
        response = await self.complete(prompt, system=system)
        return response.text

    async def recommend_picks(self, draft_context: dict[str, Any]) -> list[PickRecommendation]:
        """Рекомендовать пики на основе контекста драфта."""
        system = load_prompt("draft_recommendation")
        if not system:
            system = (
                "Ты — эксперт по драфту Dota 2. На основе текущего драфта "
                "рекомендуй 3-5 героев с пояснениями. Отвечай на русском. "
                "Формат ответа: по одному герою на строку: hero_id|name_ru|reason"
            )
        import json
        prompt = (
            f"Контекст драфта:\n"
            f"```json\n{json.dumps(draft_context, ensure_ascii=False, indent=2)}\n```\n"
            f"Рекомендуй 3-5 героев."
        )
        response = await self.complete(prompt, system=system)
        return _parse_pick_recommendations(response.text)

    async def recognize_draft(self, image_bytes: bytes) -> DraftRecognition:
        """Распознать драфт из скриншота через Vision."""
        system = load_prompt("draft_recognition")
        if not system:
            system = (
                "Ты — система распознавания драфта Dota 2. "
                "По скриншоту определи hero_id каждого героя. "
                "Формат: allies:id1,id2,...|enemies:id1,id2,...|role:N|confidence:0.X"
            )
        prompt = "Распознай героев на скриншоте экрана драфта Dota 2."
        response = await self.vision(image_bytes, prompt, system=system)
        return _parse_draft_recognition(response.text)

    # -- lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        """Закрыть HTTP-клиент (только если создан внутри)."""
        if not self._external_client:
            await self._client.aclose()

    async def __aenter__(self) -> LLMClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- OpenAI реализация --------------------------------------------------

    async def _openai_chat(
        self,
        prompt: str,
        *,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = await self._post_openai("/chat/completions", body)
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text.strip(),
            model=data.get("model", model),
            usage_tokens=usage.get("total_tokens", 0),
        )

    async def _openai_vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import base64
        b64 = base64.b64encode(image_bytes).decode("ascii")

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
                {"type": "text", "text": prompt},
            ],
        })

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        data = await self._post_openai("/chat/completions", body)
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text.strip(),
            model=data.get("model", model),
            usage_tokens=usage.get("total_tokens", 0),
        )

    async def _post_openai(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self._config['base_url']}{path}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        return await self._post_with_retry(url, headers, body)

    # -- Anthropic реализация -----------------------------------------------

    async def _anthropic_messages(
        self,
        prompt: str,
        *,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        messages = [{"role": "user", "content": prompt}]

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system

        data = await self._post_anthropic("/messages", body)
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        usage = data.get("usage", {})
        return LLMResponse(
            text=text.strip(),
            model=data.get("model", model),
            usage_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        )

    async def _anthropic_vision(
        self,
        image_bytes: bytes,
        prompt: str,
        *,
        system: str,
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        import base64
        b64 = base64.b64encode(image_bytes).decode("ascii")

        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }]

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            body["system"] = system

        data = await self._post_anthropic("/messages", body)
        text = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        usage = data.get("usage", {})
        return LLMResponse(
            text=text.strip(),
            model=data.get("model", model),
            usage_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
        )

    async def _post_anthropic(self, path: str, body: dict[str, Any]) -> Any:
        url = f"{self._config['base_url']}{path}"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        return await self._post_with_retry(url, headers, body)

    # -- общая логика HTTP-запросов -----------------------------------------

    async def _post_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
    ) -> Any:
        """POST-запрос с rate limiting и retry."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            await self._limiter.acquire()
            try:
                resp = await self._client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                last_exc = exc
                await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("retry-after", _RETRY_BACKOFF))
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(retry_after)
                    continue
                raise APIRateLimited("LLM", retry_after=retry_after)

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue

            resp.raise_for_status()
            return resp.json()

        if last_exc is not None:
            raise last_exc
        msg = f"Не удалось получить ответ от LLM: {url}"
        raise httpx.HTTPError(msg)


# ---------------------------------------------------------------------------
# Парсеры ответов LLM
# ---------------------------------------------------------------------------

def _parse_draft_recognition(text: str) -> DraftRecognition:
    """Парсинг ответа LLM для распознавания драфта.

    Ожидаемый формат: allies:1,2,3|enemies:4,5,6|role:1|confidence:0.9
    """
    result = DraftRecognition(raw_response=text)
    try:
        parts = text.strip().split("|")
        for part in parts:
            part = part.strip()
            if part.startswith("allies:"):
                ids = part[len("allies:"):].strip()
                if ids:
                    result.allies = [int(x.strip()) for x in ids.split(",") if x.strip()]
            elif part.startswith("enemies:"):
                ids = part[len("enemies:"):].strip()
                if ids:
                    result.enemies = [int(x.strip()) for x in ids.split(",") if x.strip()]
            elif part.startswith("role:"):
                val = part[len("role:"):].strip()
                if val:
                    result.user_role = int(val)
            elif part.startswith("confidence:"):
                val = part[len("confidence:"):].strip()
                if val:
                    result.confidence = float(val)
    except (ValueError, IndexError):
        result.needs_confirmation = True
        result.confidence = 0.0
        return result

    if result.confidence < 0.7:
        result.needs_confirmation = True

    return result


def _parse_pick_recommendations(text: str) -> list[PickRecommendation]:
    """Парсинг ответа LLM для рекомендации пиков.

    Ожидаемый формат: hero_id|name_ru|reason (по одному на строку)
    """
    recommendations: list[PickRecommendation] = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 2)
        if len(parts) >= 3:
            try:
                hero_id = int(parts[0].strip())
                recommendations.append(PickRecommendation(
                    hero_id=hero_id,
                    name_ru=parts[1].strip(),
                    reason=parts[2].strip(),
                ))
            except ValueError:
                continue
    return recommendations
