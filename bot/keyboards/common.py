"""Общие inline-кнопки: Назад, Отмена, Подтвердить."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Callback-данные для общих кнопок
CB_BACK = "common:back"
CB_CANCEL = "common:cancel"
CB_CONFIRM = "common:confirm"


def back_button() -> InlineKeyboardButton:
    """Кнопка 'Назад'."""
    return InlineKeyboardButton(text="« Назад", callback_data=CB_BACK)


def cancel_button() -> InlineKeyboardButton:
    """Кнопка 'Отмена'."""
    return InlineKeyboardButton(text="✕ Отмена", callback_data=CB_CANCEL)


def confirm_button() -> InlineKeyboardButton:
    """Кнопка 'Подтвердить'."""
    return InlineKeyboardButton(text="✓ Подтвердить", callback_data=CB_CONFIRM)


def confirm_cancel_kb() -> InlineKeyboardMarkup:
    """Inline-клавиатура с кнопками Подтвердить и Отмена."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[confirm_button(), cancel_button()]]
    )


def back_kb() -> InlineKeyboardMarkup:
    """Inline-клавиатура с одной кнопкой Назад."""
    return InlineKeyboardMarkup(inline_keyboard=[[back_button()]])
