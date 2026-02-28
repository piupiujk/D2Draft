"""Главное меню бота — reply-клавиатура 3x2."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

# Тексты кнопок главного меню (используются для роутинга в хендлерах)
BTN_DRAFT = "Анализ драфта"
BTN_META = "Герои меты"
BTN_MATCH = "Разбор матча"
BTN_BUILD = "Билд героя"
BTN_PROFILE = "Мой профиль"
BTN_SETTINGS = "Настройки"

ALL_MENU_BUTTONS = (BTN_DRAFT, BTN_META, BTN_MATCH, BTN_BUILD, BTN_PROFILE, BTN_SETTINGS)


def main_menu_kb() -> ReplyKeyboardMarkup:
    """Создать reply-клавиатуру главного меню 3x2."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_DRAFT), KeyboardButton(text=BTN_META)],
            [KeyboardButton(text=BTN_MATCH), KeyboardButton(text=BTN_BUILD)],
            [KeyboardButton(text=BTN_PROFILE), KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие",
    )
