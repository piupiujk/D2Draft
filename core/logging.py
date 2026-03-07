"""Структурированный логгер с маскированием PII (telegram_id, steam_id)."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Маскирование PII
# ---------------------------------------------------------------------------

# Паттерны для обнаружения PII в аргументах логирования
_STEAM_ID_RE = re.compile(r"\b(765611\d{11})\b")
_TG_ID_RE = re.compile(r"\b(\d{6,12})\b")

# Ключи, содержащие PII (для фильтрации dict-аргументов)
_PII_KEYS = frozenset({
    "telegram_id",
    "tg_id",
    "steam_id",
    "steam_id_64",
    "account_id",
})


def mask_value(value: int | str, *, last_n: int = 4) -> str:
    """Маскирует значение, оставляя только последние N символов.

    Пример: 76561198012345678 → '***5678'
    """
    s = str(value)
    if len(s) <= last_n:
        return "***"
    return f"***{s[-last_n:]}"


def mask_hash(value: int | str) -> str:
    """Возвращает короткий SHA-256 хеш для идентификации без раскрытия ID."""
    h = hashlib.sha256(str(value).encode()).hexdigest()[:8]
    return f"id:{h}"


def _mask_string(text: str) -> str:
    """Маскирует Steam ID (76561198...) в произвольной строке."""
    return _STEAM_ID_RE.sub(lambda m: mask_value(m.group(1)), text)


def _mask_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Маскирует PII-ключи в словаре (неглубокая копия)."""
    result = {}
    for key, val in d.items():
        if key in _PII_KEYS and val is not None:
            result[key] = mask_value(val)
        elif isinstance(val, str):
            result[key] = _mask_string(val)
        else:
            result[key] = val
    return result


# ---------------------------------------------------------------------------
# JSON-форматтер
# ---------------------------------------------------------------------------

class JsonFormatter(logging.Formatter):
    """Форматирует логи как JSON с маскированием PII."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "msg": self._mask_message(record),
        }

        if record.exc_info and record.exc_info[0] is not None:
            entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(entry, ensure_ascii=False, default=str)

    @staticmethod
    def _mask_message(record: logging.LogRecord) -> str:
        """Форматирует сообщение с маскированием PII в аргументах."""
        if record.args:
            if isinstance(record.args, dict):
                masked_args = _mask_dict(record.args)
                msg = str(record.msg) % masked_args
            elif isinstance(record.args, tuple):
                masked = tuple(
                    mask_value(a)
                    if isinstance(a, int) and len(str(a)) >= 6
                    else (_mask_string(a) if isinstance(a, str) else a)
                    for a in record.args
                )
                msg = str(record.msg) % masked
            else:
                msg = str(record.msg) % record.args
        else:
            msg = str(record.msg)

        return _mask_string(msg)


# ---------------------------------------------------------------------------
# PII-фильтр (работает с любым форматтером)
# ---------------------------------------------------------------------------

class PiiFilter(logging.Filter):
    """Фильтр, маскирующий PII в записях лога."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            if isinstance(record.args, dict):
                record.args = _mask_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_value(a)
                    if isinstance(a, int) and len(str(a)) >= 6
                    else (_mask_string(a) if isinstance(a, str) else a)
                    for a in record.args
                )
        return True


# ---------------------------------------------------------------------------
# Настройка логирования
# ---------------------------------------------------------------------------

def setup_logging(
    level: int = logging.INFO,
    json_format: bool = True,
) -> None:
    """Настраивает корневой логгер проекта.

    Args:
        level: Уровень логирования (по умолчанию INFO).
        json_format: Если True — JSON-формат, иначе key=value.
    """
    root = logging.getLogger()
    root.setLevel(level)

    # Удаляем все существующие обработчики
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s level=%(levelname)s logger=%(name)s msg=%(message)s"
            )
        )
        handler.addFilter(PiiFilter())

    root.addHandler(handler)

    # Понижаем шум библиотечных логгеров
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер с указанным именем."""
    return logging.getLogger(name)
