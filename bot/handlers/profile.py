"""Хендлер /profile: вывод профиля и статистики пользователя."""

from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.keyboards.menu import BTN_PROFILE
from clients.opendota import OpenDotaClient
from core.formatting import format_profile
from core.logging import get_logger
from repositories.mmr_history import MmrHistoryRepository
from repositories.user import UserRepository
from services.profile import get_user_profile

logger = get_logger(__name__)

router = Router(name="profile")

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для просмотра профиля нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_LOADING_TEXT = "⏳ Загружаю профиль…"

_ERROR_TEXT = "Не удалось загрузить профиль. Попробуй позже."

_MMR_UPDATED_TEXT = "✅ MMR обновлён!"

_MMR_UPDATE_ERROR_TEXT = "Не удалось обновить MMR. Попробуй позже."

_NO_STEAM_FOR_MMR_TEXT = "Нет привязанного Steam аккаунта для обновления MMR."

# Callback prefix для кнопки обновления MMR
UPDATE_MMR_CB = "update_mmr"


# ---------------------------------------------------------------------------
# /profile — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("profile"))
async def cmd_profile(
    message: Message,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Команда /profile: вывод профиля."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await _show_profile(message, user)


@router.message(F.text == BTN_PROFILE)
async def btn_profile(
    message: Message,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Мой профиль' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await _show_profile(message, user)


# ---------------------------------------------------------------------------
# Callback: обновление MMR
# ---------------------------------------------------------------------------


@router.callback_query(F.data == UPDATE_MMR_CB)
async def process_update_mmr(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка кнопки 'Обновить MMR'."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    steam_id = user.get("steam_id")
    if not steam_id:
        await callback.answer(_NO_STEAM_FOR_MMR_TEXT, show_alert=True)
        return

    try:
        from clients.steam import steam_id_64_to_account_id

        account_id = steam_id_64_to_account_id(int(steam_id))

        async with OpenDotaClient() as opendota:
            player = await opendota.get_player(account_id)

        new_mmr = player.mmr_estimate
        if new_mmr and new_mmr > 0:
            telegram_id = user.get("telegram_id")
            if telegram_id:
                user_repo = UserRepository()
                await user_repo.update_mmr(int(telegram_id), new_mmr)
                user["current_mmr"] = new_mmr

            await callback.answer(_MMR_UPDATED_TEXT, show_alert=False)

            # Обновляем сообщение с новым профилем
            if callback.message is not None:
                await _show_profile_edit(callback.message, user)
        else:
            await callback.answer(
                "MMR не удалось определить (возможно, профиль скрыт).",
                show_alert=True,
            )
    except Exception:
        logger.exception("Ошибка обновления MMR для user=%s", user.get("telegram_id"))
        await callback.answer(_MMR_UPDATE_ERROR_TEXT, show_alert=True)


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------


async def _show_profile(message: Message, user: dict[str, Any]) -> None:
    """Получить и вывести профиль пользователя (новое сообщение)."""
    loading_msg = await message.answer(_LOADING_TEXT)

    text, keyboard = await _build_profile_response(user)

    await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _show_profile_edit(message: Message, user: dict[str, Any]) -> None:
    """Обновить существующее сообщение с профилем."""
    text, keyboard = await _build_profile_response(user)

    await message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


async def _build_profile_response(
    user: dict[str, Any],
) -> tuple[str, InlineKeyboardMarkup]:
    """Собрать текст профиля и клавиатуру."""
    try:
        async with OpenDotaClient() as opendota:
            mmr_repo = MmrHistoryRepository()
            profile = await get_user_profile(
                user,
                opendota=opendota,
                mmr_repo=mmr_repo,
            )
        text = format_profile(profile)
    except Exception:
        logger.exception("Ошибка загрузки профиля для user=%s", user.get("telegram_id"))
        text = _ERROR_TEXT

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить MMR",
                    callback_data=UPDATE_MMR_CB,
                )
            ]
        ]
    )

    return text, keyboard
