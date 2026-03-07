"""Хендлер подписок: просмотр статуса, активация и деактивация Premium."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from core.logging import get_logger
from repositories.subscription import SubscriptionRepository
from services.subscription import activate_premium, deactivate

logger = get_logger(__name__)

router = Router(name="subscription")

# ---------------------------------------------------------------------------
# Callback prefixes
# ---------------------------------------------------------------------------

_CB_SUB_STATUS = "sub:status"
_CB_SUB_ACTIVATE_30 = "sub:activate:30"
_CB_SUB_ACTIVATE_365 = "sub:activate:365"
_CB_SUB_DEACTIVATE = "sub:deactivate"
_CB_SUB_CONFIRM_DEACTIVATE = "sub:confirm_deactivate"
_CB_SUB_CANCEL = "sub:cancel"

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для управления подпиской нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_PREMIUM_FEATURES = (
    "🌟 <b>Premium-функции:</b>\n"
    "• Анализ драфта с AI-распознаванием скриншотов\n"
    "• Рекомендации пиков на основе контрпиков и синергии\n"
    "• AI-советы по матчам от нейросети\n"
    "• Ситуативная адаптация билдов под вражеский состав"
)


def _subscription_status_text(user: dict[str, Any], is_premium: bool) -> str:
    """Текст со статусом подписки пользователя."""
    if is_premium:
        expires = user.get("premium_expires_at", "—")
        if isinstance(expires, str) and "T" in expires:
            expires = expires.split("T")[0]
        return (
            "⭐ <b>Подписка Premium</b>\n\n"
            f"Статус: <b>Активна</b>\n"
            f"Действует до: <b>{expires}</b>\n\n"
            f"{_PREMIUM_FEATURES}"
        )
    return (
        "📋 <b>Подписка</b>\n\n"
        "Статус: <b>Бесплатный план</b>\n\n"
        f"{_PREMIUM_FEATURES}\n\n"
        "Оформи подписку, чтобы получить доступ ко всем функциям!"
    )


def _subscription_kb(is_premium: bool) -> InlineKeyboardMarkup:
    """Inline-клавиатура для управления подпиской."""
    if is_premium:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="📊 Статус подписки",
                    callback_data=_CB_SUB_STATUS,
                )],
                [InlineKeyboardButton(
                    text="❌ Отменить подписку",
                    callback_data=_CB_SUB_DEACTIVATE,
                )],
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🌟 Premium на 30 дней",
                callback_data=_CB_SUB_ACTIVATE_30,
            )],
            [InlineKeyboardButton(
                text="🌟 Premium на 365 дней",
                callback_data=_CB_SUB_ACTIVATE_365,
            )],
        ]
    )


# ---------------------------------------------------------------------------
# /subscribe — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("subscribe"))
async def cmd_subscribe(
    message: Message,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Команда /subscribe: управление подпиской."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await message.answer(
        _subscription_status_text(user, is_premium),
        reply_markup=_subscription_kb(is_premium),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Статус подписки
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_SUB_STATUS)
async def sub_status(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Показ текущего статуса подписки."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        _subscription_status_text(user, is_premium),
        reply_markup=_subscription_kb(is_premium),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Активация Premium (заглушка оплаты)
# ---------------------------------------------------------------------------


@router.callback_query(F.data.in_({_CB_SUB_ACTIVATE_30, _CB_SUB_ACTIVATE_365}))
async def activate_subscription(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Активация Premium-подписки (заглушка для оплаты)."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    days = 30 if callback.data == _CB_SUB_ACTIVATE_30 else 365
    plan_label = "30 дней" if days == 30 else "365 дней"

    try:
        subscription = await activate_premium(
            user_id=user["id"],
            telegram_id=int(user["telegram_id"]),
            duration_days=days,
        )
        user["is_premium"] = True
        user["premium_expires_at"] = subscription.get("expires_at")

        await callback.answer(f"Premium активирован на {plan_label}!", show_alert=True)
        await callback.message.edit_text(
            _subscription_status_text(user, is_premium=True),
            reply_markup=_subscription_kb(is_premium=True),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Ошибка активации подписки")
        await callback.answer(
            "Не удалось активировать подписку. Попробуй позже.",
            show_alert=True,
        )


# ---------------------------------------------------------------------------
# Деактивация Premium
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_SUB_DEACTIVATE)
async def deactivate_prompt(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Запрос подтверждения деактивации подписки."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    if not is_premium:
        await callback.answer("У тебя нет активной подписки.", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "⚠️ <b>Отмена подписки</b>\n\n"
        "Ты уверен? Premium-функции станут недоступны сразу после отмены.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text="✅ Да, отменить",
                    callback_data=_CB_SUB_CONFIRM_DEACTIVATE,
                )],
                [InlineKeyboardButton(
                    text="↩️ Назад",
                    callback_data=_CB_SUB_CANCEL,
                )],
            ]
        ),
        parse_mode="HTML",
    )


@router.callback_query(F.data == _CB_SUB_CONFIRM_DEACTIVATE)
async def confirm_deactivate(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Подтверждение деактивации подписки."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    try:
        sub_repo = SubscriptionRepository()
        active_sub = await sub_repo.get_active(user["id"])

        if active_sub is None:
            await callback.answer("Активная подписка не найдена.", show_alert=True)
            return

        await deactivate(
            subscription_id=active_sub["id"],
            telegram_id=int(user["telegram_id"]),
        )
        user["is_premium"] = False
        user["premium_expires_at"] = None

        await callback.answer("Подписка отменена.", show_alert=True)
        await callback.message.edit_text(
            _subscription_status_text(user, is_premium=False),
            reply_markup=_subscription_kb(is_premium=False),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Ошибка деактивации подписки")
        await callback.answer(
            "Не удалось отменить подписку. Попробуй позже.",
            show_alert=True,
        )


@router.callback_query(F.data == _CB_SUB_CANCEL)
async def cancel_deactivate(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Отмена деактивации — возврат к меню подписки."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        _subscription_status_text(user, is_premium),
        reply_markup=_subscription_kb(is_premium),
        parse_mode="HTML",
    )
