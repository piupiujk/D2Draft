"""Хендлер /draft: приём скриншота, распознавание драфта, рекомендация пиков."""

from __future__ import annotations

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

from bot.keyboards.menu import BTN_DRAFT
from bot.states.draft import DraftStates
from clients.llm import LLMClient
from clients.opendota import OpenDotaClient
from clients.stratz import StratzClient
from core.enums import Role
from core.logging import get_logger
from core.validators import validate_image_size
from repositories.draft_analysis import DraftAnalysisRepository
from services.build import get_hero_build, get_situational_build
from services.draft import ValidatedDraft, recognize_draft, recommend_picks
from services.meta import mmr_to_bracket

logger = get_logger(__name__)

router = Router(name="draft")

# ---------------------------------------------------------------------------
# Тексты
# ---------------------------------------------------------------------------

_NOT_REGISTERED_TEXT = (
    "Для использования этой функции нужно зарегистрироваться.\n"
    "Отправь /start для начала."
)

_PREMIUM_REQUIRED_TEXT = (
    "🔮 <b>Анализ драфта</b>\n\n"
    "Эта функция доступна только для Premium-подписчиков.\n"
    "Оформи подписку, чтобы получить доступ к анализу драфта и рекомендациям пиков."
)

_ASK_SCREENSHOT_TEXT = (
    "🔮 <b>Анализ драфта</b>\n\n"
    "Отправь скриншот экрана драфта.\n"
    "Я распознаю героев и порекомендую лучший пик."
)

_RECOGNIZING_TEXT = "⏳ Распознаю героев на скриншоте…"

_RECOMMENDING_TEXT = "⏳ Подбираю лучших героев…"

_RECOGNITION_FAILED_TEXT = (
    "Не удалось распознать драфт. Попробуй отправить более чёткий скриншот."
)

_ERROR_TEXT = "Произошла ошибка. Попробуй позже."

_NOT_PHOTO_TEXT = "Отправь скриншот как фото, а не как файл."

# Callback-префиксы
_CB_CONFIRM_DRAFT = "draft:confirm"
_CB_RETRY_DRAFT = "draft:retry"
_CB_DRAFT_PICK = "draft_pick:"


# ---------------------------------------------------------------------------
# /draft — точка входа
# ---------------------------------------------------------------------------


@router.message(Command("draft"))
async def cmd_draft(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Команда /draft: запуск анализа драфта (Premium)."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    if not is_premium:
        await message.answer(_PREMIUM_REQUIRED_TEXT, parse_mode="HTML")
        return

    await state.clear()
    await message.answer(_ASK_SCREENSHOT_TEXT, parse_mode="HTML")
    await state.set_state(DraftStates.waiting_screenshot)


@router.message(F.text == BTN_DRAFT)
async def btn_draft(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Кнопка 'Анализ драфта' из главного меню."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        return

    if not is_premium:
        await message.answer(_PREMIUM_REQUIRED_TEXT, parse_mode="HTML")
        return

    await state.clear()
    await message.answer(_ASK_SCREENSHOT_TEXT, parse_mode="HTML")
    await state.set_state(DraftStates.waiting_screenshot)


# ---------------------------------------------------------------------------
# FSM: приём скриншота
# ---------------------------------------------------------------------------


@router.message(DraftStates.waiting_screenshot, F.photo)
async def process_screenshot(
    message: Message,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Обработка присланного скриншота драфта."""
    if user is None:
        await message.answer(_NOT_REGISTERED_TEXT)
        await state.clear()
        return

    if not is_premium:
        await message.answer(_PREMIUM_REQUIRED_TEXT, parse_mode="HTML")
        await state.clear()
        return

    # Берём фото максимального разрешения
    photo = message.photo[-1]

    # Валидация размера
    size_err = validate_image_size(photo.file_size)
    if size_err:
        await message.answer(size_err)
        return

    loading_msg = await message.answer(_RECOGNIZING_TEXT)

    try:
        # Скачиваем файл
        bot = message.bot
        file = await bot.get_file(photo.file_id)
        from io import BytesIO

        buf = BytesIO()
        await bot.download_file(file.file_path, buf)
        image_bytes = buf.getvalue()

        # Распознаём через LLM Vision
        llm = _create_llm_client()
        draft = await recognize_draft(image_bytes, llm)

    except Exception:
        logger.exception("Ошибка при распознавании драфта")
        await loading_msg.edit_text(_RECOGNITION_FAILED_TEXT)
        await state.clear()
        return

    # Пустой драфт
    if not draft.allies and not draft.enemies:
        await loading_msg.edit_text(_RECOGNITION_FAILED_TEXT)
        await state.clear()
        return

    # Сохраняем распознанный драфт в FSM для подтверждения
    await state.update_data(
        allies=draft.allies,
        enemies=draft.enemies,
        user_role=draft.user_role,
        confidence=draft.confidence,
    )

    # Формируем сообщение с результатом распознавания
    text = _format_recognition(draft)

    if draft.needs_confirmation:
        # Показываем с кнопками подтверждения / повтора
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✓ Подтвердить", callback_data=_CB_CONFIRM_DRAFT
                    ),
                    InlineKeyboardButton(
                        text="📷 Отправить другой", callback_data=_CB_RETRY_DRAFT
                    ),
                ]
            ]
        )
        await loading_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await state.set_state(DraftStates.confirming_heroes)
    else:
        # Высокая уверенность — сразу к рекомендациям
        await loading_msg.edit_text(text, parse_mode="HTML")
        await _show_recommendations(message, state, user, loading_msg)


@router.message(DraftStates.waiting_screenshot)
async def process_non_photo(
    message: Message,
    **_kwargs: Any,
) -> None:
    """Обработка текста вместо фото в состоянии ожидания скриншота."""
    await message.answer(_NOT_PHOTO_TEXT)


# ---------------------------------------------------------------------------
# Callback: подтверждение / повтор
# ---------------------------------------------------------------------------


@router.callback_query(F.data == _CB_CONFIRM_DRAFT)
async def confirm_draft(
    callback: CallbackQuery,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Подтверждение распознанного драфта — переход к рекомендациям."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await _show_recommendations(callback.message, state, user)


@router.callback_query(F.data == _CB_RETRY_DRAFT)
async def retry_draft(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Повторная отправка скриншота."""
    await callback.answer()
    await state.set_state(DraftStates.waiting_screenshot)
    await callback.message.edit_text(_ASK_SCREENSHOT_TEXT, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Callback: выбор героя из рекомендаций — показ билда
# ---------------------------------------------------------------------------


@router.callback_query(F.data.startswith(_CB_DRAFT_PICK))
async def pick_hero_build(
    callback: CallbackQuery,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Показ билда выбранного героя из рекомендаций."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    try:
        hero_id = int(callback.data[len(_CB_DRAFT_PICK):])
    except (ValueError, IndexError):
        await callback.answer("Некорректный выбор.")
        return

    await callback.answer()

    # Извлекаем вражеских героев из FSM state для ситуативного билда
    data = await state.get_data()
    enemy_heroes = data.get("enemies_for_build", [])
    await state.clear()

    await _show_hero_build(
        callback.message, user, hero_id,
        enemy_heroes=enemy_heroes if is_premium else None,
    )


# ---------------------------------------------------------------------------
# Вспомогательные
# ---------------------------------------------------------------------------


async def _show_recommendations(
    message: Message,
    state: FSMContext,
    user: dict[str, Any],
    loading_msg: Message | None = None,
) -> None:
    """Получить и вывести рекомендации пиков."""
    data = await state.get_data()
    allies = data.get("allies", [])
    enemies = data.get("enemies", [])
    user_role_val = data.get("user_role") or user.get("main_role")

    if not user_role_val:
        user_role_val = 1  # fallback на carry

    try:
        role = Role(int(user_role_val))
    except (ValueError, TypeError):
        role = Role.CARRY

    mmr = user.get("current_mmr", 0) or 0
    bracket = mmr_to_bracket(mmr)

    steam_id = user.get("steam_id")
    account_id = _steam_to_account_id(steam_id)

    # Показываем прогресс
    progress_msg = loading_msg
    if progress_msg is None:
        progress_msg = await message.answer(_RECOMMENDING_TEXT)
    else:
        try:
            await progress_msg.edit_text(_RECOMMENDING_TEXT)
        except Exception:
            progress_msg = await message.answer(_RECOMMENDING_TEXT)

    try:
        stratz_token = _get_stratz_token()
        llm = _create_llm_client()

        async with StratzClient(token=stratz_token) as stratz:
            opendota = None
            if account_id is not None:
                opendota = OpenDotaClient()

            try:
                recommendations = await recommend_picks(
                    allies=allies,
                    enemies=enemies,
                    user_role=role,
                    bracket=bracket,
                    stratz=stratz,
                    opendota=opendota,
                    llm_client=llm,
                    account_id=account_id,
                )
            finally:
                if opendota is not None:
                    await opendota.close()

    except Exception:
        logger.exception("Ошибка при получении рекомендаций")
        await progress_msg.edit_text(_ERROR_TEXT)
        await state.clear()
        return

    # Сохраняем в БД
    user_id = user.get("id")
    if user_id and recommendations:
        try:
            repo = DraftAnalysisRepository()
            await repo.insert(
                user_id=user_id,
                ally_hero_ids=allies,
                enemy_hero_ids=enemies,
                recommended_ids=[r.hero_id for r in recommendations],
                user_role=int(role),
                confidence=data.get("confidence"),
            )
        except Exception:
            logger.warning("Не удалось сохранить анализ драфта в БД", exc_info=True)

    if not recommendations:
        await state.clear()
        await progress_msg.edit_text(
            "Не удалось подобрать рекомендации. Попробуй позже."
        )
        return

    # Сохраняем enemies в state для ситуативного билда при выборе героя
    await state.update_data(enemies_for_build=enemies)

    # Формируем вывод
    from core.formatting import format_draft_recommendations

    text = format_draft_recommendations(recommendations)
    kb = _recommendations_keyboard(recommendations)
    await progress_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)


def _format_recognition(draft: ValidatedDraft) -> str:
    """Форматировать результат распознавания драфта."""
    lines: list[str] = ["🔮 <b>Распознанный драфт</b>", ""]

    if draft.allies_names:
        allies_str = ", ".join(draft.allies_names)
        lines.append(f"🟢 <b>Союзники:</b> {allies_str}")

    if draft.enemies_names:
        enemies_str = ", ".join(draft.enemies_names)
        lines.append(f"🔴 <b>Противники:</b> {enemies_str}")

    conf_pct = f"{draft.confidence * 100:.0f}%"
    lines.append(f"\n📊 Уверенность: {conf_pct}")

    if draft.needs_confirmation:
        lines.append("\n⚠️ Проверь, правильно ли распознаны герои.")

    return "\n".join(lines)




def _recommendations_keyboard(recommendations: list) -> InlineKeyboardMarkup:
    """Создать inline-клавиатуру из рекомендованных героев."""
    rows: list[list[InlineKeyboardButton]] = []
    for rec in recommendations:
        rows.append([
            InlineKeyboardButton(
                text=f"🛡 Билд: {rec.name_ru}",
                callback_data=f"{_CB_DRAFT_PICK}{rec.hero_id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_hero_build(
    message: Message,
    user: dict[str, Any],
    hero_id: int,
    enemy_heroes: list[int] | None = None,
) -> None:
    """Показать билд выбранного героя. Для Premium — с ситуативной адаптацией."""
    from core.formatting import format_build
    from core.hero_mapping import get_hero_by_id

    try:
        get_hero_by_id(hero_id)
    except Exception:
        await message.answer("Герой не найден.")
        return

    mmr = user.get("current_mmr", 0) or 0
    bracket = mmr_to_bracket(mmr)
    role_val = user.get("main_role")

    try:
        stratz_token = _get_stratz_token()

        if enemy_heroes:
            # Premium: ситуативный билд с адаптацией под врагов
            llm = _create_llm_client()
            async with StratzClient(token=stratz_token) as stratz:
                sit_build = await get_situational_build(
                    hero_id=hero_id,
                    role=role_val,
                    bracket=bracket,
                    enemy_heroes=enemy_heroes,
                    stratz=stratz,
                    llm_client=llm,
                )
            text = format_build(sit_build.base_build)
            # Добавляем блок с ситуативной адаптацией
            adaptation = sit_build.adaptation_text.strip()
            if adaptation:
                text += "\n\n⚔️ <b>Адаптация под вражеский состав:</b>\n" + adaptation
            # Обрезаем до лимита Telegram
            if len(text) > 4096:
                text = text[:4090] + "\n..."
        else:
            async with StratzClient(token=stratz_token) as stratz:
                build = await get_hero_build(
                    hero_id=hero_id,
                    role=role_val,
                    bracket=bracket,
                    stratz=stratz,
                )
            text = format_build(build)
    except Exception:
        logger.exception("Ошибка при получении билда: hero_id=%s", hero_id)
        await message.answer("Не удалось получить билд. Попробуй позже.")
        return

    await message.answer(text, parse_mode="HTML")


def _steam_to_account_id(steam_id: str | None) -> int | None:
    """Конвертировать Steam ID 64-bit в 32-bit account_id."""
    if not steam_id:
        return None
    try:
        sid = int(steam_id)
        return sid - 76561197960265728
    except (ValueError, TypeError):
        return None


def _get_stratz_token() -> str:
    """Получить Stratz API token из конфигурации."""
    from bot.config import settings

    return settings.STRATZ_TOKEN


def _create_llm_client() -> LLMClient:
    """Создать LLM-клиент из конфигурации."""
    from bot.config import settings

    return LLMClient(
        api_key=settings.LLM_API_KEY,
        provider=settings.LLM_PROVIDER,
    )
