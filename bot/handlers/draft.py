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
from core.error_messages import LLM_DRAFT_FALLBACK, classify_api_error
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

# Callback-префиксы для редактирования драфта
_CB_EDIT_DRAFT = "draft:edit"
_CB_EDIT_SIDE = "draft:side:"
_CB_REMOVE_HERO = "draft:rm:"
_CB_ADD_HERO_START = "draft:add:"
_CB_RECALC = "draft:recalc"
_CB_EDIT_BACK = "draft:edit_back"
_CB_CHANGE_ROLE = "draft:chrole"
_CB_SET_ROLE = "draft:setrole:"


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
        await loading_msg.edit_text(LLM_DRAFT_FALLBACK)
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
        # DEBUG: отправляем распознанный драфт отдельным сообщением (не перезапишется)
        await message.answer(text, parse_mode="HTML")
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
                    mmr=mmr,
                )
            finally:
                if opendota is not None:
                    await opendota.close()

    except Exception as exc:
        logger.exception("Ошибка при получении рекомендаций")
        await progress_msg.edit_text(classify_api_error(exc))
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

    # Формируем вывод с именами героев
    from core.formatting import format_draft_recommendations
    from core.hero_mapping import get_hero_by_id

    allies_names = []
    for hid in allies:
        try:
            allies_names.append(get_hero_by_id(hid).name_en)
        except Exception:
            allies_names.append(f"#{hid}")

    enemies_names = []
    for hid in enemies:
        try:
            enemies_names.append(get_hero_by_id(hid).name_en)
        except Exception:
            enemies_names.append(f"#{hid}")

    text = format_draft_recommendations(
        recommendations, allies_names, enemies_names, role_label=role.label_ru,
    )
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

    # DEBUG: raw LLM response
    if draft.raw_response:
        raw = draft.raw_response[:500]
        lines.append(f"\n🛠 <b>DEBUG LLM:</b> <code>{raw}</code>")

    return "\n".join(lines)




def _recommendations_keyboard(recommendations: list) -> InlineKeyboardMarkup:
    """Создать inline-клавиатуру из рекомендованных героев."""
    rows: list[list[InlineKeyboardButton]] = []
    for rec in recommendations:
        rows.append([
            InlineKeyboardButton(
                text=f"🛡 Build: {rec.name_ru}",
                callback_data=f"{_CB_DRAFT_PICK}{rec.hero_id}",
            )
        ])
    # Кнопки редактирования
    rows.append([
        InlineKeyboardButton(
            text="✏️ Изменить героев",
            callback_data=_CB_EDIT_DRAFT,
        ),
        InlineKeyboardButton(
            text="🎮 Изменить позицию",
            callback_data=_CB_CHANGE_ROLE,
        ),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------------------
# Callback: редактирование драфта
# ---------------------------------------------------------------------------


def _hero_names_for_ids(hero_ids: list[int]) -> list[str]:
    """Получить английские имена героев по списку ID."""
    from core.hero_mapping import get_hero_by_id

    names = []
    for hid in hero_ids:
        try:
            names.append(get_hero_by_id(hid).name_en)
        except Exception:
            names.append(f"#{hid}")
    return names


def _edit_sides_keyboard(allies: list[int], enemies: list[int]) -> InlineKeyboardMarkup:
    """Клавиатура выбора стороны для редактирования."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 Союзники ({len(allies)})",
                    callback_data=f"{_CB_EDIT_SIDE}allies",
                ),
                InlineKeyboardButton(
                    text=f"🔴 Противники ({len(enemies)})",
                    callback_data=f"{_CB_EDIT_SIDE}enemies",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Готово — пересчитать",
                    callback_data=_CB_RECALC,
                ),
            ],
            [
                InlineKeyboardButton(text="« Назад", callback_data=_CB_EDIT_BACK),
            ],
        ]
    )


def _edit_heroes_keyboard(
    side: str, hero_ids: list[int], hero_names: list[str],
) -> InlineKeyboardMarkup:
    """Клавиатура списка героев стороны с кнопками удаления и добавления."""
    rows: list[list[InlineKeyboardButton]] = []
    for hid, name in zip(hero_ids, hero_names):
        rows.append([
            InlineKeyboardButton(
                text=f"❌ {name}",
                callback_data=f"{_CB_REMOVE_HERO}{side}:{hid}",
            )
        ])
    if len(hero_ids) < 5:
        rows.append([
            InlineKeyboardButton(
                text="➕ Добавить героя",
                callback_data=f"{_CB_ADD_HERO_START}{side}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="« Назад", callback_data=_CB_EDIT_DRAFT),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _side_label(side: str) -> str:
    return "Союзники" if side == "allies" else "Противники"


@router.callback_query(F.data == _CB_EDIT_DRAFT)
async def edit_draft(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Показать выбор стороны для редактирования."""
    await callback.answer()
    data = await state.get_data()
    allies = data.get("allies", [])
    enemies = data.get("enemies", [])

    allies_names = _hero_names_for_ids(allies)
    enemies_names = _hero_names_for_ids(enemies)

    text = (
        "✏️ <b>Редактирование драфта</b>\n\n"
        f"🟢 <b>Союзники:</b> {', '.join(allies_names) or '—'}\n"
        f"🔴 <b>Противники:</b> {', '.join(enemies_names) or '—'}\n\n"
        "Выбери сторону для редактирования:"
    )
    kb = _edit_sides_keyboard(allies, enemies)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(DraftStates.editing_side)


@router.callback_query(F.data.startswith(_CB_EDIT_SIDE))
async def edit_side(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Показать героев выбранной стороны с кнопками удаления."""
    side = callback.data[len(_CB_EDIT_SIDE):]
    if side not in ("allies", "enemies"):
        await callback.answer("Некорректный выбор.")
        return

    await callback.answer()
    data = await state.get_data()
    hero_ids = data.get(side, [])
    hero_names = _hero_names_for_ids(hero_ids)

    label = _side_label(side)
    text = f"✏️ <b>{label}</b>\n\nНажми на героя, чтобы удалить:"
    kb = _edit_heroes_keyboard(side, hero_ids, hero_names)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(DraftStates.editing_hero)


@router.callback_query(F.data.startswith(_CB_REMOVE_HERO))
async def remove_hero(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Удалить героя из стороны драфта."""
    payload = callback.data[len(_CB_REMOVE_HERO):]
    try:
        side, hero_id_str = payload.split(":")
        hero_id = int(hero_id_str)
    except (ValueError, IndexError):
        await callback.answer("Некорректные данные.")
        return

    if side not in ("allies", "enemies"):
        await callback.answer("Некорректный выбор.")
        return

    data = await state.get_data()
    hero_ids: list[int] = list(data.get(side, []))
    if hero_id in hero_ids:
        hero_ids.remove(hero_id)
        await state.update_data(**{side: hero_ids, "draft_edited": True})

    await callback.answer("Герой удалён")

    # Обновляем сообщение — показываем обновлённый список стороны
    hero_names = _hero_names_for_ids(hero_ids)
    label = _side_label(side)
    text = f"✏️ <b>{label}</b>\n\nНажми на героя, чтобы удалить:"
    kb = _edit_heroes_keyboard(side, hero_ids, hero_names)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)


@router.callback_query(F.data.startswith(_CB_ADD_HERO_START))
async def add_hero_start(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Попросить пользователя ввести имя героя для добавления."""
    side = callback.data[len(_CB_ADD_HERO_START):]
    if side not in ("allies", "enemies"):
        await callback.answer("Некорректный выбор.")
        return

    await callback.answer()
    await state.update_data(adding_side=side)

    label = _side_label(side)
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="« Отмена", callback_data=f"{_CB_EDIT_SIDE}{side}")]
        ]
    )
    await callback.message.edit_text(
        f"➕ <b>Добавить героя ({label})</b>\n\n"
        "Напиши имя героя в чат (EN/RU/сокращение):",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )
    await state.set_state(DraftStates.adding_hero)


@router.message(DraftStates.adding_hero, F.text)
async def add_hero_by_name(
    message: Message,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Обработка текстового ввода имени героя для добавления."""
    from core.exceptions import HeroNotFound
    from core.hero_mapping import find_hero

    data = await state.get_data()
    side = data.get("adding_side", "allies")

    query = message.text.strip()
    try:
        hero = find_hero(query)
    except HeroNotFound:
        await message.answer(
            f"Герой «{query}» не найден. Попробуй ещё раз или напиши /draft для отмены."
        )
        return

    hero_ids: list[int] = list(data.get(side, []))
    if len(hero_ids) >= 5:
        await message.answer("Максимум 5 героев на стороне.")
        return
    if hero.hero_id in hero_ids:
        await message.answer(f"{hero.name_en} уже в списке. Введи другого героя.")
        return

    hero_ids.append(hero.hero_id)
    await state.update_data(**{side: hero_ids, "draft_edited": True})

    # Показываем обновлённый список стороны
    hero_names = _hero_names_for_ids(hero_ids)
    label = _side_label(side)
    text = (
        f"✅ <b>{hero.name_en}</b> добавлен\n\n"
        f"✏️ <b>{label}</b>\n\nНажми на героя, чтобы удалить:"
    )
    kb = _edit_heroes_keyboard(side, hero_ids, hero_names)
    await message.answer(text, parse_mode="HTML", reply_markup=kb)
    await state.set_state(DraftStates.editing_hero)


@router.callback_query(F.data == _CB_CHANGE_ROLE)
async def change_role(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Показать кнопки выбора позиции."""
    await callback.answer()
    data = await state.get_data()
    current_role = data.get("user_role") or 1

    rows: list[list[InlineKeyboardButton]] = []
    for role in Role:
        marker = "• " if role.value == current_role else ""
        rows.append([
            InlineKeyboardButton(
                text=f"{marker}{role.value} — {role.label_ru}",
                callback_data=f"{_CB_SET_ROLE}{role.value}",
            )
        ])
    rows.append([
        InlineKeyboardButton(text="« Назад", callback_data=_CB_EDIT_BACK),
    ])

    await callback.message.edit_text(
        "🎮 <b>Выбери позицию для рекомендаций:</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith(_CB_SET_ROLE))
async def set_role(
    callback: CallbackQuery,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    **_kwargs: Any,
) -> None:
    """Установить позицию и пересчитать рекомендации."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    try:
        role_val = int(callback.data[len(_CB_SET_ROLE):])
        Role(role_val)
    except (ValueError, TypeError):
        await callback.answer("Некорректная позиция.")
        return

    await callback.answer()
    await state.update_data(user_role=role_val, draft_edited=True)
    await _show_recommendations(callback.message, state, user)


@router.callback_query(F.data == _CB_EDIT_BACK)
async def edit_back(
    callback: CallbackQuery,
    state: FSMContext,
    **_kwargs: Any,
) -> None:
    """Вернуться из редактирования к рекомендациям (без пересчёта)."""
    await callback.answer()
    await callback.message.edit_text(
        "Редактирование отменено. Используй /draft для нового анализа."
    )
    await state.clear()


@router.callback_query(F.data == _CB_RECALC)
async def recalc_draft(
    callback: CallbackQuery,
    state: FSMContext,
    user: dict[str, Any] | None = None,
    is_premium: bool = False,
    **_kwargs: Any,
) -> None:
    """Пересчитать рекомендации после редактирования драфта."""
    if user is None:
        await callback.answer(_NOT_REGISTERED_TEXT, show_alert=True)
        return

    await callback.answer()
    await _show_recommendations(callback.message, state, user)


# ---------------------------------------------------------------------------
# Вспомогательные: показ билда
# ---------------------------------------------------------------------------


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
    except Exception as exc:
        logger.exception("Ошибка при получении билда: hero_id=%s", hero_id)
        await message.answer(classify_api_error(exc))
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

    api_key = (
        settings.AGENT_PLATFORM_API
        if settings.LLM_PROVIDER == "agentplatform"
        else settings.LLM_API_KEY
    )
    return LLMClient(api_key=api_key, provider=settings.LLM_PROVIDER)
