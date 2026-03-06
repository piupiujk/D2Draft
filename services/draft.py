"""Сервис распознавания драфта: LLM Vision парсинг скриншота."""

from __future__ import annotations

from dataclasses import dataclass, field

from clients.llm import DraftRecognition, LLMClient
from core.constants import HERO_BY_ID
from core.hero_mapping import get_hero_by_id

# ---------------------------------------------------------------------------
# Порог уверенности
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------


@dataclass
class ValidatedDraft:
    """Результат распознавания драфта с валидацией hero_id."""

    allies: list[int] = field(default_factory=list)
    enemies: list[int] = field(default_factory=list)
    allies_names: list[str] = field(default_factory=list)
    enemies_names: list[str] = field(default_factory=list)
    user_role: int | None = None
    confidence: float = 0.0
    needs_confirmation: bool = False
    raw_response: str = ""
    invalid_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


async def recognize_draft(
    image_bytes: bytes,
    llm_client: LLMClient,
) -> ValidatedDraft:
    """Распознать драфт из скриншота через LLM Vision.

    Аргументы:
        image_bytes: байты изображения (PNG/JPEG).
        llm_client: экземпляр LLMClient для Vision-запроса.

    Возвращает ValidatedDraft с валидированными hero_id и именами на русском.
    При confidence < CONFIDENCE_THRESHOLD выставляет needs_confirmation=True.
    """
    recognition: DraftRecognition = await llm_client.recognize_draft(image_bytes)

    return _validate_recognition(recognition)


def _validate_recognition(recognition: DraftRecognition) -> ValidatedDraft:
    """Валидирует распознанные hero_id и обогащает русскими именами."""
    result = ValidatedDraft(
        raw_response=recognition.raw_response,
        confidence=recognition.confidence,
        user_role=(
            recognition.user_role
            if recognition.user_role and recognition.user_role > 0
            else None
        ),
    )

    invalid_ids: list[int] = []

    # Валидация союзников
    for hid in recognition.allies:
        if hid in HERO_BY_ID:
            result.allies.append(hid)
            hero = get_hero_by_id(hid)
            result.allies_names.append(hero.name_ru)
        else:
            invalid_ids.append(hid)

    # Валидация противников
    for hid in recognition.enemies:
        if hid in HERO_BY_ID:
            result.enemies.append(hid)
            hero = get_hero_by_id(hid)
            result.enemies_names.append(hero.name_ru)
        else:
            invalid_ids.append(hid)

    result.invalid_ids = invalid_ids

    # Пересчёт уверенности при невалидных ID
    if invalid_ids:
        total = len(recognition.allies) + len(recognition.enemies)
        valid = len(result.allies) + len(result.enemies)
        if total > 0:
            result.confidence = result.confidence * (valid / total)

    # Порог уверенности
    if result.confidence < CONFIDENCE_THRESHOLD:
        result.needs_confirmation = True

    # Также помечаем как needs_confirmation, если пришло от парсера
    if recognition.needs_confirmation:
        result.needs_confirmation = True

    # Пустой драфт — низкая уверенность
    if not result.allies and not result.enemies:
        result.needs_confirmation = True
        result.confidence = 0.0

    return result
