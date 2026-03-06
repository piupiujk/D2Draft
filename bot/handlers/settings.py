"""Хендлер /settings: управление уведомлениями, сменой роли, обновлением MMR."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot.keyboards.menu import BTN_SETTINGS
from bot.states.settings import SettingsStates
from clients.steam import SteamClient
from core.enums import Role
from core.exceptions import SteamProfileClosed
from repositories.user import UserRepository

logger = logging.getLogger(__name__)

router = Router(name="settings")

# ---------------------------------------------------------------------------
# Callback prefixes
# ---------------------------------------------------------------------------

_CB_TOGGLE_NOTIF = "settings:toggle_notif"
_CB_CHANGE_ROLE = "settings:change_role"
_CB_UPDATE_MMR = "settings:update_mmr"
_CB_CHANGE_STEAM = "settings:change_steam"
_CB_SETTINGS_ROLE_PREFIX = "settings_role:"

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для доступа к настройкам нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)


def _settings_menu_text(user: dict[str, Any]) -> str:
    """Текст меню настроек с текущими значениями."""
    notif = user.get("notifications_enabled", True)
    notif_label = "✅ Вкл" if notif else "❌ Выкл"

    role_val = user.get("main_role")
    try:
        role_label = Role(int(role_val)).label_ru if role_val is not None else "—"
    except (ValueError, TypeError):
        role_label = "—"

    mmr = user.get("current_mmr")
    mmr_label = str(mmr) if mmr is not None else "—"

    steam_id = user.get("steam_id") or "—"

    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"🔔 Уведомления: <b>{notif_label}</b>\n"
        f"🎯 Основная роль: <b>{role_label}</b>\n"
        f"📊 MMR: <b>{mmr_label}</b>\n"
        f"🎮 Steam ID: <b>{steam_id}</b>"
    )


def _settings_kb(user: dict[str, Any]) -> InlineKeyboardMarkup:
    """Inline-клавиатура меню настроек."""
    notif = user.get("notifications_enabled", True)
    notif_text = "🔕 Выключить уведомления" if notif else "🔔 Включить уведомления"

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=notif_text, callback_data=_CB_TOGGLE_NOTIF)],
            [InlineKeyboardButton(text="🎯 Сменить роль", callback_data=_CB_CHANGE_ROLE)],
            [InlineKeyboardButton(text="📊 Обновить MMR", callback_data=_CB_UPDATE_MMR)],
            [InlineKeyboardButton(text="🎮 Сменить Steam", callback_data=_CB_CHANGE_STEAM)],
        ]
    )


def _role_selection_kb() -> InlineKeyboardMarkup:
    """Inline-клавиатура выбора роли для настроек."""
    buttons = [
        [
            InlineKeyboardButton(
                text=role.label_ru,
                callback_data=f"{_CB_SETTINGS_ROLE_PREFIX}{role.value}",
            )
        ]
        for role in Role
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ---------------------------------------------------------------------------
# /settings — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Команда /settings: показ inline-меню настроек."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await state.clear()
    await message.answer(
        _settings_menu_text(user),
        reply_markup=_settings_kb(user),
        parse_mode="HTML",
    )


@router.message(F.text == BTN_SETTINGS)
async def btn_settings(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Настройки' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    await state.clear()
    await message.answer(
        _settings_menu_text(user),
        reply_markup=_settings_kb(user),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Переключение уведомлений
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_TOGGLE_NOTIF)
async def toggle_notifications(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Переключение уведомлений."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    current = user.get("notifications_enabled", True)
    new_value = not current

    try:
        user_repo = UserRepository()
        await user_repo.update(
            int(user["telegram_id"]),
            notifications_enabled=new_value,
        )
        user["notifications_enabled"] = new_value

        status = "включены" if new_value else "выключены"
        await callback.answer(f"Уведомления {status}.")

        await callback.message.edit_text(
            _settings_menu_text(user),
            reply_markup=_settings_kb(user),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Ошибка переключения уведомлений")
        await callback.answer("Не удалось изменить настройку.", show_alert=True)


# ---------------------------------------------------------------------------
# Смена роли
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_CHANGE_ROLE)
async def change_role_menu(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Показ клавиатуры выбора новой роли."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "Выбери новую основную роль:",
        reply_markup=_role_selection_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith(_CB_SETTINGS_ROLE_PREFIX))
async def process_role_change(
    callback: CallbackQuery,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка выбора новой роли."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    raw = callback.data[len(_CB_SETTINGS_ROLE_PREFIX):]
    try:
        role = Role(int(raw))
    except (ValueError, TypeError):
        await callback.answer("Некорректный выбор роли.", show_alert=True)
        return

    try:
        user_repo = UserRepository()
        await user_repo.update(
            int(user["telegram_id"]),
            main_role=role.value,
        )
        user["main_role"] = role.value

        await callback.answer(f"Роль изменена: {role.label_ru}")

        await callback.message.edit_text(
            _settings_menu_text(user),
            reply_markup=_settings_kb(user),
            parse_mode="HTML",
        )
    except Exception:
        logger.exception("Ошибка смены роли")
        await callback.answer("Не удалось сменить роль.", show_alert=True)


# ---------------------------------------------------------------------------
# Обновление MMR
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_UPDATE_MMR)
async def update_mmr_settings(
    callback: CallbackQuery,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Запрос ввода нового MMR."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "Введи новый MMR (число от 0 до 15000):",
        parse_mode="HTML",
    )
    await state.set_state(SettingsStates.waiting_new_mmr)


@router.message(SettingsStates.waiting_new_mmr)
async def process_new_mmr(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка ввода нового MMR."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        await state.clear()
        return

    raw = (message.text or "").strip()

    try:
        mmr = int(raw)
    except ValueError:
        await message.answer("MMR должен быть числом от 0 до 15000. Попробуй ещё раз.")
        return

    if mmr < 0 or mmr > 15000:
        await message.answer("MMR должен быть числом от 0 до 15000. Попробуй ещё раз.")
        return

    try:
        user_repo = UserRepository()
        await user_repo.update_mmr(int(user["telegram_id"]), mmr)
        user["current_mmr"] = mmr
    except Exception:
        logger.exception("Ошибка обновления MMR")
        await message.answer("Не удалось обновить MMR. Попробуй позже.")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        _settings_menu_text(user),
        reply_markup=_settings_kb(user),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Смена Steam аккаунта
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_CHANGE_STEAM)
async def change_steam_menu(
    callback: CallbackQuery,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Запрос нового Steam ID."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "Отправь новый Steam ID или ссылку на профиль\n"
        "(steamcommunity.com/id/... или steamcommunity.com/profiles/...):",
        parse_mode="HTML",
    )
    await state.set_state(SettingsStates.waiting_new_steam)


@router.message(SettingsStates.waiting_new_steam)
async def process_new_steam(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Обработка ввода нового Steam ID."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        await state.clear()
        return

    raw_input = (message.text or "").strip()
    if not raw_input:
        await message.answer("Отправь Steam ID или ссылку на профиль текстом.")
        return

    steam_client = SteamClient(steam_api_key=_get_steam_api_key())

    try:
        async with steam_client:
            steam_id_64, persona_name = await steam_client.resolve_and_validate(raw_input)
    except SteamProfileClosed:
        await message.answer(
            "Steam-профиль закрыт. Открой его в настройках Steam и попробуй снова."
        )
        return
    except ValueError as e:
        await message.answer(f"Не удалось распознать Steam ID.\nОшибка: {e}")
        return
    except Exception:
        logger.exception("Ошибка при валидации Steam ID: %s", raw_input)
        await message.answer("Произошла ошибка при проверке Steam-профиля. Попробуй позже.")
        await state.clear()
        return

    try:
        user_repo = UserRepository()
        await user_repo.update(
            int(user["telegram_id"]),
            steam_id=str(steam_id_64),
            username=persona_name,
        )
        user["steam_id"] = str(steam_id_64)
        user["username"] = persona_name
    except Exception:
        logger.exception("Ошибка обновления Steam ID")
        await message.answer("Не удалось обновить Steam аккаунт. Попробуй позже.")
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"✅ Steam аккаунт обновлён!\nНикнейм: <b>{persona_name}</b>\n\n"
        + _settings_menu_text(user),
        reply_markup=_settings_kb(user),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------


def _get_steam_api_key() -> str | None:
    """Получить Steam API Key из конфигурации."""
    try:
        from bot.config import settings
        key = settings.STEAM_API_KEY
        return key if key else None
    except Exception:
        return None
