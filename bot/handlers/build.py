"""Хендлер /build: ввод героя текстом, вывод полного билда."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.heroes import HERO_CB_PREFIX, parse_hero_callback
from bot.keyboards.menu import BTN_BUILD
from bot.states.build import BuildStates
from clients.stratz import StratzClient
from core.exceptions import HeroNotFound
from core.formatting import format_build
from core.hero_mapping import find_hero, get_hero_by_id
from core.logging import get_logger
from core.validators import validate_hero_query
from services.build import get_hero_build
from services.meta import mmr_to_bracket

logger = get_logger(__name__)

router = Router(name="build")

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для использования этой функции нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_ASK_HERO_TEXT = (
    "Введи имя героя на русском или английском.\n"
    "Можно использовать сокращения (am, qop, инвок и т.д.)."
)

_HERO_NOT_FOUND_TEXT = (
    'Герой «{query}» не найден.\n'
    "Попробуй другое имя или сокращение."
)

_ERROR_TEXT = "Не удалось получить билд. Попробуй позже."


# ---------------------------------------------------------------------------
# /build — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("build"))
async def cmd_build(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Команда /build [герой]: если герой указан — сразу билд, иначе — запрос ввода."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    raw_text = (message.text or "").strip()
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1:
        hero_query, err = validate_hero_query(parts[1])
        if err:
            await message.answer(err)
            return
        await _resolve_and_show_build(message, state, user, hero_query)
        return

    await message.answer(_ASK_HERO_TEXT)
    await state.set_state(BuildStates.waiting_hero_name)


@router.message(F.text == BTN_BUILD)
async def btn_build(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Билд героя' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await message.answer(_ASK_HERO_TEXT)
    await state.set_state(BuildStates.waiting_hero_name)


# ---------------------------------------------------------------------------
# FSM: ввод имени героя
# ---------------------------------------------------------------------------


@router.message(BuildStates.waiting_hero_name)
async def process_hero_name(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка текстового ввода имени героя."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        await state.clear()
        return

    hero_query, err = validate_hero_query(message.text or "")
    if err:
        await message.answer(err)
        return

    await _resolve_and_show_build(message, state, user, hero_query)


# ---------------------------------------------------------------------------
# Callback: выбор героя из inline-кнопок (например, из /meta)
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(HERO_CB_PREFIX))
async def process_hero_callback(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка inline-кнопки выбора героя — показ билда."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    hero_id = parse_hero_callback(callback.data)
    if hero_id is None:
        await callback.answer("Некорректный выбор героя.")
        return

    await callback.answer()

    try:
        hero_data = get_hero_by_id(hero_id)
    except HeroNotFound:
        await callback.message.answer("Герой не найден.")
        return

    await _show_build(callback.message, user, hero_id, hero_data.name_ru)


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------


async def _resolve_and_show_build(
    message: Message,
    state: FSMContext,
    user: dict[str, Any],
    hero_query: str,
) -> None:
    """Найти героя по запросу и показать билд."""
    try:
        hero_data = find_hero(hero_query)
    except HeroNotFound:
        await message.answer(_HERO_NOT_FOUND_TEXT.format(query=hero_query))
        return

    await state.clear()
    await _show_build(message, user, hero_data.hero_id, hero_data.name_ru)


async def _show_build(
    message: Message,
    user: dict[str, Any],
    hero_id: int,
    hero_name_ru: str,
) -> None:
    """Получить и вывести билд героя."""
    mmr = user.get("current_mmr", 0) or 0
    bracket = mmr_to_bracket(mmr)
    role_val = user.get("main_role")

    try:
        stratz_token = _get_stratz_token()
        async with StratzClient(token=stratz_token) as stratz:
            build = await get_hero_build(
                hero_id=hero_id,
                role=role_val,
                bracket=bracket,
                stratz=stratz,
            )
    except Exception:
        logger.exception(
            "Ошибка при получении билда: hero_id=%s", hero_id,
        )
        await message.answer(_ERROR_TEXT)
        return

    text = format_build(build)
    await message.answer(text, parse_mode="HTML")


def _get_stratz_token() -> str:
    """Получить Stratz API token из конфигурации."""
    from bot.config import settings

    return settings.STRATZ_TOKEN
