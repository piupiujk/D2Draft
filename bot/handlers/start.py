"""Хендлер /start: онбординг нового пользователя (FSM-диалог)."""

from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards.common import CB_CANCEL, CB_CONFIRM, confirm_cancel_kb
from bot.keyboards.menu import main_menu_kb
from bot.keyboards.roles import ROLE_CB_PREFIX, parse_role_callback, role_selection_kb
from bot.states.onboarding import OnboardingStates
from clients.steam import SteamClient
from core.exceptions import SteamProfileClosed
from repositories.user import DuplicateUserError, UserRepository

logger = logging.getLogger(__name__)

router = Router(name="start")

# ---------------------------------------------------------------------------
# Тексты сообщений
# ---------------------------------------------------------------------------

_WELCOME_TEXT = (
    "Привет! Я — D2Draft, твой помощник по Dota 2.\n\n"
    "Для начала мне нужно привязать твой Steam-аккаунт.\n"
    "Отправь мне свой Steam ID, ссылку на профиль "
    "(steamcommunity.com/id/... или steamcommunity.com/profiles/...) "
    "или числовой Steam ID."
)

_STEAM_ERROR_FORMAT = (
    "Не удалось распознать Steam ID.\n"
    "Отправь ссылку на свой Steam-профиль "
    "(steamcommunity.com/id/... или steamcommunity.com/profiles/...) "
    "или числовой Steam ID.\n\n"
    "Ошибка: {error}"
)

_PROFILE_CLOSED_TEXT = (
    "Твой Steam-профиль закрыт. Для работы бота профиль должен быть открытым.\n\n"
    "Как открыть:\n"
    "1. Зайди в Steam → Профиль → Редактировать профиль\n"
    "2. Настройки приватности → Профиль: Открытый\n"
    "3. Подожди 5-10 минут и попробуй снова."
)

_CONFIRM_NICKNAME_TEXT = "Это твой профиль?\n\nНикнейм: <b>{nickname}</b>"

_ASK_MMR_TEXT = (
    "Введи свой текущий MMR (число от 0 до 15000).\n"
    "Если не знаешь точный MMR, введи приблизительный."
)

_MMR_INVALID_TEXT = "MMR должен быть числом от 0 до 15000. Попробуй ещё раз."

_ASK_ROLE_TEXT = "Выбери свою основную роль:"

_ONBOARDING_DONE_TEXT = (
    "Отлично! Профиль создан.\n\n"
    "Никнейм: <b>{nickname}</b>\n"
    "MMR: <b>{mmr}</b>\n"
    "Роль: <b>{role}</b>\n\n"
    "Используй меню ниже для навигации."
)

_ALREADY_REGISTERED_TEXT = (
    "С возвращением, <b>{nickname}</b>!\n"
    "Используй меню для навигации."
)

_ONBOARDING_CANCELLED_TEXT = "Онбординг отменён. Отправь /start чтобы начать заново."


# ---------------------------------------------------------------------------
# /start — точка входа
# ---------------------------------------------------------------------------

@router.message(CommandStart())
async def cmd_start(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Команда /start: если пользователь зарегистрирован — главное меню, иначе — онбординг."""
    if user is not None:
        nickname = user.get("username") or "игрок"
        await message.answer(
            _ALREADY_REGISTERED_TEXT.format(nickname=nickname),
            reply_markup=main_menu_kb(),
            parse_mode="HTML",
        )
        return

    await state.clear()
    await message.answer(_WELCOME_TEXT)
    await state.set_state(OnboardingStates.waiting_steam_id)


# ---------------------------------------------------------------------------
# Шаг 1: Получение Steam ID
# ---------------------------------------------------------------------------

@router.message(OnboardingStates.waiting_steam_id)
async def process_steam_id(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка ввода Steam ID/URL."""
    raw_input = (message.text or "").strip()
    if not raw_input:
        await message.answer("Отправь Steam ID или ссылку на профиль текстом.")
        return

    steam_client = SteamClient(
        steam_api_key=_get_steam_api_key(),
    )

    try:
        async with steam_client:
            steam_id_64, persona_name = await steam_client.resolve_and_validate(
                raw_input
            )
    except SteamProfileClosed:
        await message.answer(_PROFILE_CLOSED_TEXT)
        return
    except ValueError as e:
        await message.answer(_STEAM_ERROR_FORMAT.format(error=e))
        return
    except Exception:
        logger.exception("Ошибка при валидации Steam ID: %s", raw_input)
        await message.answer(
            "Произошла ошибка при проверке Steam-профиля. Попробуй позже."
        )
        return

    await state.update_data(
        steam_id_64=steam_id_64,
        steam_id=str(steam_id_64),
        persona_name=persona_name,
    )
    await message.answer(
        _CONFIRM_NICKNAME_TEXT.format(nickname=persona_name),
        reply_markup=confirm_cancel_kb(),
        parse_mode="HTML",
    )
    await state.set_state(OnboardingStates.confirming_nickname)


# ---------------------------------------------------------------------------
# Шаг 2: Подтверждение никнейма
# ---------------------------------------------------------------------------

@router.callback_query(OnboardingStates.confirming_nickname, F.data == CB_CONFIRM)
async def confirm_nickname(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Пользователь подтвердил никнейм — запрашиваем MMR."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(_ASK_MMR_TEXT)
    await state.set_state(OnboardingStates.waiting_mmr)


@router.callback_query(OnboardingStates.confirming_nickname, F.data == CB_CANCEL)
async def cancel_nickname(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Пользователь отклонил — возвращаемся к вводу Steam ID."""
    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "Хорошо, отправь другой Steam ID или ссылку на профиль."
    )
    await state.set_state(OnboardingStates.waiting_steam_id)


# ---------------------------------------------------------------------------
# Шаг 3: Ввод MMR
# ---------------------------------------------------------------------------

@router.message(OnboardingStates.waiting_mmr)
async def process_mmr(
    message: Message,
    state: FSMContext,
) -> None:
    """Обработка ввода MMR (0-15000)."""
    raw = (message.text or "").strip()

    try:
        mmr = int(raw)
    except ValueError:
        await message.answer(_MMR_INVALID_TEXT)
        return

    if mmr < 0 or mmr > 15000:
        await message.answer(_MMR_INVALID_TEXT)
        return

    await state.update_data(mmr=mmr)
    await message.answer(_ASK_ROLE_TEXT, reply_markup=role_selection_kb())
    await state.set_state(OnboardingStates.waiting_role)


# ---------------------------------------------------------------------------
# Шаг 4: Выбор роли
# ---------------------------------------------------------------------------

@router.callback_query(
    OnboardingStates.waiting_role,
    F.data.startswith(ROLE_CB_PREFIX),
)
async def process_role(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Обработка выбора роли — создание профиля в БД."""
    role = parse_role_callback(callback.data)
    if role is None:
        await callback.answer("Некорректный выбор роли.")
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    steam_id = data.get("steam_id", "")
    persona_name = data.get("persona_name", "")
    mmr = data.get("mmr", 0)
    telegram_id = callback.from_user.id

    user_repo = UserRepository()
    try:
        await user_repo.create(
            telegram_id=telegram_id,
            steam_id=steam_id,
            username=persona_name,
            current_mmr=mmr,
            main_role=role.value,
        )
    except DuplicateUserError:
        await callback.message.answer(
            "Этот аккаунт уже зарегистрирован. Отправь /start для входа.",
            reply_markup=main_menu_kb(),
        )
        await state.clear()
        return
    except Exception:
        logger.exception("Ошибка при создании пользователя: tg=%s", telegram_id)
        await callback.message.answer(
            "Произошла ошибка при создании профиля. Попробуй позже."
        )
        await state.clear()
        return

    await callback.message.answer(
        _ONBOARDING_DONE_TEXT.format(
            nickname=persona_name,
            mmr=mmr,
            role=role.label_ru,
        ),
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )
    await state.clear()

    logger.info(
        "Новый пользователь: tg_id=%s, steam=%s, mmr=%s, role=%s",
        telegram_id,
        steam_id[-4:] if steam_id else "?",
        mmr,
        role.name,
    )


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------

def _get_steam_api_key() -> str | None:
    """Получить Steam API Key из конфигурации (если задан)."""
    try:
        from bot.config import settings
        key = settings.STEAM_API_KEY
        return key if key else None
    except Exception:
        return None
