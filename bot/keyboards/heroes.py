"""Inline-клавиатура списка героев с пагинацией."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Количество героев на одной странице
PAGE_SIZE = 8

# Префикс для callback_data выбора героя
HERO_CB_PREFIX = "hero:"
HERO_PAGE_CB_PREFIX = "hero_page:"


@dataclass(frozen=True, slots=True)
class HeroButton:
    """Данные для одной кнопки героя."""

    hero_id: int
    name: str


def hero_list_kb(
    heroes: list[HeroButton],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """Создать inline-клавиатуру со списком героев и пагинацией.

    Args:
        heroes: список героев для отображения.
        page: номер текущей страницы (начиная с 0).

    Returns:
        InlineKeyboardMarkup с кнопками героев и навигацией.
    """
    total_pages = max(1, (len(heroes) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_heroes = heroes[start:end]

    # Кнопки героев — по 2 в ряд
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(page_heroes), 2):
        row = [
            InlineKeyboardButton(
                text=h.name,
                callback_data=f"{HERO_CB_PREFIX}{h.hero_id}",
            )
            for h in page_heroes[i : i + 2]
        ]
        rows.append(row)

    # Навигация
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="« Назад",
                callback_data=f"{HERO_PAGE_CB_PREFIX}{page - 1}",
            )
        )
    if page < total_pages - 1:
        nav_row.append(
            InlineKeyboardButton(
                text="Далее »",
                callback_data=f"{HERO_PAGE_CB_PREFIX}{page + 1}",
            )
        )
    if nav_row:
        rows.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def parse_hero_callback(callback_data: str) -> int | None:
    """Извлечь hero_id из callback_data. Возвращает None если невалидный формат."""
    if not callback_data.startswith(HERO_CB_PREFIX):
        return None
    try:
        return int(callback_data[len(HERO_CB_PREFIX) :])
    except ValueError:
        return None


def parse_hero_page_callback(callback_data: str) -> int | None:
    """Извлечь номер страницы из callback_data. Возвращает None если невалидный формат."""
    if not callback_data.startswith(HERO_PAGE_CB_PREFIX):
        return None
    try:
        return int(callback_data[len(HERO_PAGE_CB_PREFIX) :])
    except ValueError:
        return None
