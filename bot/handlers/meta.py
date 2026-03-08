"""Хендлер /meta: выбор роли и вывод списка мета-героев."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.keyboards.heroes import HeroButton, hero_list_kb
from bot.keyboards.menu import BTN_META
from clients.opendota import OpenDotaClient
from clients.steam import steam_id_64_to_account_id
from clients.stratz import StratzClient
from core.enums import Role
from core.error_messages import classify_api_error
from core.formatting import format_meta_heroes
from core.logging import get_logger
from services.meta import get_meta_heroes, mmr_to_bracket

logger = get_logger(__name__)

router = Router(name="meta")

# Префикс для callback_data выбора роли именно в контексте /meta
META_ROLE_CB_PREFIX = "meta_role:"

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для использования этой функции нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_CHOOSE_ROLE_TEXT = "Выбери роль, чтобы увидеть мета-героев:"

_ERROR_TEXT = "Не удалось получить данные о мета-героях. Попробуй позже."

# Маппинг текстовых аргументов на роли
_ROLE_ALIASES: dict[str, Role] = {
    "carry": Role.CARRY,
    "керри": Role.CARRY,
    "1": Role.CARRY,
    "mid": Role.MID,
    "мид": Role.MID,
    "мидер": Role.MID,
    "2": Role.MID,
    "offlane": Role.OFFLANE,
    "офф": Role.OFFLANE,
    "оффлейн": Role.OFFLANE,
    "оффлейнер": Role.OFFLANE,
    "3": Role.OFFLANE,
    "soft": Role.SOFT_SUPPORT,
    "софт": Role.SOFT_SUPPORT,
    "4": Role.SOFT_SUPPORT,
    "hard": Role.HARD_SUPPORT,
    "хард": Role.HARD_SUPPORT,
    "5": Role.HARD_SUPPORT,
    "support": Role.HARD_SUPPORT,
    "саппорт": Role.HARD_SUPPORT,
}


def _meta_role_selection_kb():
    """Inline-клавиатура выбора роли для /meta (с отдельным prefix)."""
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

    buttons = [
        [
            InlineKeyboardButton(
                text=role.label_ru,
                callback_data=f"{META_ROLE_CB_PREFIX}{role.value}",
            )
        ]
        for role in Role
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _parse_meta_role_callback(callback_data: str) -> Role | None:
    """Извлечь Role из meta_role callback_data."""
    if not callback_data.startswith(META_ROLE_CB_PREFIX):
        return None
    try:
        return Role(int(callback_data[len(META_ROLE_CB_PREFIX) :]))
    except (ValueError, KeyError):
        return None


def _parse_role_from_text(text: str) -> Role | None:
    """Попробовать распознать роль из текстового аргумента."""
    cleaned = text.strip().lower()
    return _ROLE_ALIASES.get(cleaned)


# ---------------------------------------------------------------------------
# /meta — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("meta"))
async def cmd_meta(
    message: Message,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Команда /meta [роль]: показ мета-героев. Если роль указана — сразу выдача."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    # Проверяем, передана ли роль как аргумент
    raw_text = (message.text or "").strip()
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1:
        role = _parse_role_from_text(parts[1])
        if role is not None:
            await _show_meta_heroes(message, user, role)
            return

    await message.answer(_CHOOSE_ROLE_TEXT, reply_markup=_meta_role_selection_kb())


@router.message(F.text == BTN_META)
async def btn_meta(
    message: Message,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Герои меты' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await message.answer(_CHOOSE_ROLE_TEXT, reply_markup=_meta_role_selection_kb())


# ---------------------------------------------------------------------------
# Callback: выбор роли
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(META_ROLE_CB_PREFIX))
async def process_meta_role(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка выбора роли — вывод мета-героев."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    role = _parse_meta_role_callback(callback.data)
    if role is None:
        await callback.answer("Некорректный выбор роли.")
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await _show_meta_heroes(callback.message, user, role)


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------


async def _show_meta_heroes(
    message: Message,
    user: dict[str, Any],
    role: Role,
) -> None:
    """Получить и вывести мета-героев для роли."""
    mmr = user.get("current_mmr", 0) or 0
    bracket = mmr_to_bracket(mmr)
    steam_id = user.get("steam_id")

    account_id = None
    if steam_id:
        try:
            account_id = steam_id_64_to_account_id(int(steam_id))
        except (ValueError, TypeError):
            pass

    try:
        stratz_token = _get_stratz_token()
        async with StratzClient(token=stratz_token) as stratz:
            opendota = None
            if account_id is not None:
                opendota = OpenDotaClient()

            if opendota is not None:
                async with opendota:
                    heroes = await get_meta_heroes(
                        role=role,
                        bracket=bracket,
                        stratz=stratz,
                        opendota=opendota,
                        account_id=account_id,
                    )
            else:
                heroes = await get_meta_heroes(
                    role=role,
                    bracket=bracket,
                    stratz=stratz,
                )
    except Exception as exc:
        logger.exception("Ошибка при получении мета-героев: role=%s", role.name)
        await message.answer(classify_api_error(exc))
        return

    # Форматируем и отправляем текст
    text = format_meta_heroes(heroes, role.label_ru)

    # Генерируем inline-кнопки героев для перехода к билду
    hero_buttons = [HeroButton(hero_id=h.hero_id, name=h.name_ru) for h in heroes]
    kb = hero_list_kb(hero_buttons) if hero_buttons else None

    await message.answer(text, reply_markup=kb, parse_mode="HTML")


def _get_stratz_token() -> str:
    """Получить Stratz API token из конфигурации."""
    from bot.config import settings

    return settings.STRATZ_TOKEN
