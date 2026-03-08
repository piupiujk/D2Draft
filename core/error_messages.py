"""Пользовательские сообщения об ошибках для graceful degradation."""

from __future__ import annotations

import httpx

from core.exceptions import APIRateLimited, ExternalAPIError


def classify_api_error(exc: Exception) -> str:
    """Определить тип ошибки API и вернуть сообщение для пользователя.

    Возвращает информативное сообщение на русском языке, различающее
    типы ошибок: таймаут, rate limit, недоступность сервиса, общая ошибка.
    """
    if isinstance(exc, APIRateLimited):
        if exc.retry_after:
            return (
                f"Слишком много запросов к {exc.service}. "
                f"Попробуй через {exc.retry_after:.0f} сек."
            )
        return "Слишком много запросов. Подожди немного и попробуй снова."

    if isinstance(exc, httpx.TimeoutException):
        return "Сервер данных не отвечает. Попробуй через пару минут."

    if isinstance(exc, httpx.ConnectError):
        return "Не удалось подключиться к серверу данных. Попробуй позже."

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return "Слишком много запросов. Подожди немного и попробуй снова."
        if status >= 500:
            return "Сервер данных временно недоступен. Попробуй позже."
        return "Ошибка при получении данных. Попробуй позже."

    if isinstance(exc, ExternalAPIError):
        return f"Сервис {exc.service} временно недоступен. Попробуй позже."

    return "Произошла непредвиденная ошибка. Попробуй позже."


# Специализированные сообщения для конкретных фич

STRATZ_UNAVAILABLE = "Данные меты временно недоступны. Попробуй позже."
OPENDOTA_UNAVAILABLE = "Не удалось получить данные матча. Попробуй позже."
LLM_UNAVAILABLE = "AI-сервис временно недоступен. Попробуй позже."
LLM_DRAFT_FALLBACK = (
    "AI-сервис временно недоступен для распознавания скриншота.\n"
    "Попробуй позже или введи героев вручную через /draft."
)
