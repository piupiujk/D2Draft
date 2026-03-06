"""Обработка текстовых кнопок главного меню: роутинг reply-клавиатуры.

Кнопки, для которых уже есть полноценные хендлеры (BTN_META, BTN_BUILD,
BTN_MATCH, BTN_PROFILE), обрабатываются в соответствующих модулях
(meta.py, build.py, match.py, profile.py).

Этот модуль содержит заглушки для ещё не реализованных кнопок:
- «Анализ драфта» (BTN_DRAFT) — будет реализован в TASK-027
- «Настройки» (BTN_SETTINGS) — будет реализован в TASK-021
"""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.types import Message

from bot.keyboards.menu import BTN_DRAFT, BTN_SETTINGS

router = Router(name="menu")

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для использования этой функции нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_DRAFT_STUB_TEXT = (
    "🔮 <b>Анализ драфта</b>\n\n"
    "Эта функция пока в разработке.\n"
    "Скоро ты сможешь отправить скриншот драфта и получить "
    "рекомендации по пикам."
)

_SETTINGS_STUB_TEXT = (
    "⚙️ <b>Настройки</b>\n\n"
    "Эта функция пока в разработке.\n"
    "Скоро здесь можно будет:\n"
    "• Включить/выключить уведомления\n"
    "• Сменить основную роль\n"
    "• Обновить MMR\n"
    "• Сменить Steam аккаунт"
)


# ---------------------------------------------------------------------------
# Кнопка «Анализ драфта» — заглушка (TASK-027)
# ---------------------------------------------------------------------------


@router.message(F.text == BTN_DRAFT)
async def btn_draft(
    message: Message,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Анализ драфта' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await message.answer(_DRAFT_STUB_TEXT, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Кнопка «Настройки» — заглушка (TASK-021)
# ---------------------------------------------------------------------------


@router.message(F.text == BTN_SETTINGS)
async def btn_settings(
    message: Message,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Настройки' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await message.answer(_SETTINGS_STUB_TEXT, parse_mode="HTML")
