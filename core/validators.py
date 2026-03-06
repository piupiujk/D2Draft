"""Централизованная валидация входных данных.

Все функции возвращают (очищенное_значение, None) при успехе
или (None, сообщение_об_ошибке) при ошибке.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

_MMR_MIN = 0
_MMR_MAX = 15000
_HERO_QUERY_MAX_LEN = 50
_STEAM_INPUT_MAX_LEN = 200
_IMAGE_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Допустимые символы в имени героя: буквы (в т.ч. кириллица), цифры, пробелы, дефисы, апострофы
_RE_HERO_QUERY = re.compile(r"^[\w\s\-']+$", re.UNICODE)

# ---------------------------------------------------------------------------
# Тексты ошибок (русский)
# ---------------------------------------------------------------------------

MSG_MMR_INVALID = "MMR должен быть числом от 0 до 15000. Попробуй ещё раз."
MSG_HERO_QUERY_EMPTY = "Отправь имя героя текстом."
MSG_HERO_QUERY_TOO_LONG = "Слишком длинный запрос. Максимум 50 символов."
MSG_HERO_QUERY_BAD_CHARS = (
    "Имя героя может содержать только буквы, цифры, пробелы и дефисы."
)
MSG_STEAM_INPUT_EMPTY = "Отправь Steam ID или ссылку на профиль текстом."
MSG_STEAM_INPUT_TOO_LONG = "Слишком длинный ввод. Отправь Steam ID или ссылку."
MSG_IMAGE_TOO_LARGE = "Изображение слишком большое. Максимальный размер — 10 МБ."


# ---------------------------------------------------------------------------
# Валидаторы
# ---------------------------------------------------------------------------


def validate_mmr(raw: str) -> tuple[int | None, str | None]:
    """Валидация MMR: целое число от 0 до 15000.

    Возвращает ``(mmr, None)`` при успехе или ``(None, сообщение)`` при ошибке.
    """
    text = raw.strip()
    try:
        mmr = int(text)
    except (ValueError, TypeError):
        return None, MSG_MMR_INVALID

    if mmr < _MMR_MIN or mmr > _MMR_MAX:
        return None, MSG_MMR_INVALID

    return mmr, None


def validate_hero_query(raw: str) -> tuple[str | None, str | None]:
    """Валидация запроса имени героя.

    Проверяет:
    - Не пустой
    - Длина <= 50 символов
    - Только допустимые символы (буквы, цифры, пробелы, дефисы, апострофы)

    Возвращает ``(очищенная_строка, None)`` при успехе.
    """
    text = raw.strip()
    if not text:
        return None, MSG_HERO_QUERY_EMPTY

    if len(text) > _HERO_QUERY_MAX_LEN:
        return None, MSG_HERO_QUERY_TOO_LONG

    if not _RE_HERO_QUERY.match(text):
        return None, MSG_HERO_QUERY_BAD_CHARS

    return text, None


def validate_steam_input(raw: str) -> tuple[str | None, str | None]:
    """Валидация raw-ввода Steam ID / URL.

    Проверяет:
    - Не пустой
    - Длина <= 200 символов

    Дальнейшая валидация формата делается в ``clients/steam.py``.
    """
    text = raw.strip()
    if not text:
        return None, MSG_STEAM_INPUT_EMPTY

    if len(text) > _STEAM_INPUT_MAX_LEN:
        return None, MSG_STEAM_INPUT_TOO_LONG

    return text, None


def validate_image_size(file_size: int | None) -> str | None:
    """Проверка размера изображения.

    Возвращает ``None`` если размер допустим, иначе — сообщение об ошибке.
    """
    if file_size is not None and file_size > _IMAGE_MAX_BYTES:
        return MSG_IMAGE_TOO_LARGE
    return None
