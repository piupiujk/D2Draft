"""Хендлер /lastmatch: вывод разбора последнего матча."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards.menu import BTN_MATCH
from clients.llm import LLMClient
from clients.opendota import OpenDotaClient
from core.enums import Role
from core.formatting import format_match_analysis
from repositories.match_analysis import MatchAnalysisRepository
from services.match_analysis import analyze_last_match, get_llm_advice

logger = logging.getLogger(__name__)

router = Router(name="match")

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для использования этой функции нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_NO_STEAM_TEXT = (
    "У тебя не привязан Steam аккаунт.\n"
    "Отправь /start чтобы привязать."
)

_LOADING_TEXT = "⏳ Анализирую последний матч…"

_ERROR_TEXT = "Не удалось получить данные матча. Попробуй позже."

_NO_MATCHES_TEXT = "Не найдено недавних матчей. Сыграй матч и попробуй снова."

_AI_ADVICE_PREMIUM_TEXT = (
    "\n\n💡 <i>Получи персональный совет от AI"
    " — доступно для Premium-подписчиков.</i>"
)

# Callback prefix для кнопки AI-совета
AI_ADVICE_CB_PREFIX = "ai_advice:"


# ---------------------------------------------------------------------------
# /lastmatch — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("lastmatch"))
async def cmd_lastmatch(
    message: Message,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Команда /lastmatch: разбор последнего матча."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await _show_last_match(message, user, is_premium)


@router.message(F.text == BTN_MATCH)
async def btn_match(
    message: Message,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Разбор матча' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await _show_last_match(message, user, is_premium)


# ---------------------------------------------------------------------------
# Callback: AI-совет (заглушка до реализации TASK-028)
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(AI_ADVICE_CB_PREFIX))
async def process_ai_advice(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Обработка кнопки 'Получить совет от AI'."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    if not is_premium:
        await callback.answer(
            "AI-советы доступны только для Premium-подписчиков.",
            show_alert=True,
        )
        return

    # Извлекаем match_id из callback_data
    raw_match_id = callback.data[len(AI_ADVICE_CB_PREFIX):]  # type: ignore[index]
    try:
        match_id = int(raw_match_id)
    except (ValueError, TypeError):
        await callback.answer("Некорректные данные матча.", show_alert=True)
        return

    await callback.answer()

    # Показываем сообщение о загрузке
    msg = callback.message
    if msg is None:
        return

    await msg.edit_text("⏳ Генерирую персональный AI-совет…", reply_markup=None)

    steam_id = user.get("steam_id")
    if not steam_id:
        await msg.edit_text(_NO_STEAM_TEXT)
        return

    try:
        steam_id_int = int(steam_id)
    except (ValueError, TypeError):
        await msg.edit_text(_ERROR_TEXT)
        return

    user_role = _get_user_role(user)
    user_id = user.get("id")

    try:
        async with OpenDotaClient() as opendota:
            match_repo = MatchAnalysisRepository()

            # Заново получаем анализ матча для формирования контекста
            analysis = await analyze_last_match(
                steam_id=steam_id_int,
                opendota=opendota,
                match_repo=match_repo if user_id else None,
                user_id=user_id,
                user_role=user_role,
            )

            # Проверяем что это тот же матч
            if analysis.match_id != match_id:
                await msg.edit_text(
                    "Матч изменился с момента анализа. "
                    "Отправь /lastmatch чтобы разобрать текущий матч."
                )
                return

            # Получаем LLM-совет
            llm = _create_llm_client()
            async with llm:
                advice = await get_llm_advice(
                    analysis,
                    llm=llm,
                    match_repo=match_repo if user_id else None,
                    user_id=user_id,
                )
    except Exception:
        logger.exception("Ошибка при генерации AI-совета для match_id=%s", match_id)
        await msg.edit_text(
            "Не удалось получить AI-совет. Попробуй позже."
        )
        return

    # Формируем итоговый текст: анализ + совет
    base_text = format_match_analysis(analysis)
    full_text = f"{base_text}\n\n💡 <b>Совет от AI:</b>\n{advice}"

    # Обрезаем до лимита Telegram (4096 символов)
    if len(full_text) > 4096:
        full_text = full_text[:4090] + "…"

    await msg.edit_text(full_text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------


async def _show_last_match(
    message: Message,
    user: dict[str, Any],
    is_premium: bool,
) -> None:
    """Получить и вывести разбор последнего матча."""
    steam_id = user.get("steam_id")
    if not steam_id:
        await message.answer(_NO_STEAM_TEXT)
        return

    # Показываем сообщение о загрузке
    loading_msg = await message.answer(_LOADING_TEXT)

    try:
        steam_id_int = int(steam_id)
    except (ValueError, TypeError):
        await loading_msg.edit_text(_ERROR_TEXT)
        return

    # Определяем роль пользователя
    user_role = _get_user_role(user)

    try:
        async with OpenDotaClient() as opendota:
            match_repo = MatchAnalysisRepository()
            user_id = user.get("id")

            analysis = await analyze_last_match(
                steam_id=steam_id_int,
                opendota=opendota,
                match_repo=match_repo if user_id else None,
                user_id=user_id,
                user_role=user_role,
            )
    except ValueError as e:
        error_msg = str(e)
        if "нет недавних матчей" in error_msg.lower():
            await loading_msg.edit_text(_NO_MATCHES_TEXT)
        else:
            logger.warning("Ошибка анализа матча: %s", error_msg)
            await loading_msg.edit_text(_ERROR_TEXT)
        return
    except Exception:
        logger.exception("Ошибка при анализе матча для steam_id=%s", steam_id)
        await loading_msg.edit_text(_ERROR_TEXT)
        return

    # Форматируем результат
    text = format_match_analysis(analysis)

    # Для premium: кнопка AI-совета, для free: текст о подписке
    keyboard = None
    if is_premium:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="💡 Получить совет от AI",
                        callback_data=f"{AI_ADVICE_CB_PREFIX}{analysis.match_id}",
                    )
                ]
            ]
        )
    else:
        text += _AI_ADVICE_PREMIUM_TEXT

    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


def _get_user_role(user: dict[str, Any]) -> Role | None:
    """Извлечь роль пользователя из профиля."""
    role_val = user.get("main_role")
    if role_val is None:
        return None
    try:
        return Role(int(role_val))
    except (ValueError, TypeError):
        return None


def _create_llm_client() -> LLMClient:
    """Создать LLM-клиент из конфигурации."""
    from bot.config import settings

    return LLMClient(
        api_key=settings.LLM_API_KEY,
        provider=settings.LLM_PROVIDER,
    )
