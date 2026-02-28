"""Inline-клавиатура выбора роли (5 кнопок)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.enums import Role

# Префикс для callback_data выбора роли
ROLE_CB_PREFIX = "role:"


def role_selection_kb() -> InlineKeyboardMarkup:
    """Создать inline-клавиатуру из 5 кнопок для выбора роли."""
    buttons = [
        [
            InlineKeyboardButton(
                text=role.label_ru,
                callback_data=f"{ROLE_CB_PREFIX}{role.value}",
            )
        ]
        for role in Role
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def parse_role_callback(callback_data: str) -> Role | None:
    """Извлечь Role из callback_data. Возвращает None если формат невалидный."""
    if not callback_data.startswith(ROLE_CB_PREFIX):
        return None
    try:
        return Role(int(callback_data[len(ROLE_CB_PREFIX) :]))
    except (ValueError, KeyError):
        return None
