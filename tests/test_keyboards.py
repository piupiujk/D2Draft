"""Тесты для bot/keyboards/ — menu, roles, common, heroes."""

import sys
from types import ModuleType

# --- Мокаем зависимости aiogram ---

if "aiogram" not in sys.modules:
    _aiogram = ModuleType("aiogram")

    class _BaseMiddleware:
        pass

    _aiogram.BaseMiddleware = _BaseMiddleware  # type: ignore[attr-defined]
    sys.modules["aiogram"] = _aiogram

if "aiogram.types" not in sys.modules:
    _aiogram_types = ModuleType("aiogram.types")

    class _KeyboardButton:
        def __init__(self, text: str, **kwargs):
            self.text = text

    class _ReplyKeyboardMarkup:
        def __init__(self, keyboard=None, resize_keyboard=False, **kwargs):
            self.keyboard = keyboard or []
            self.resize_keyboard = resize_keyboard
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _InlineKeyboardButton:
        def __init__(self, text: str, callback_data: str | None = None, **kwargs):
            self.text = text
            self.callback_data = callback_data

    class _InlineKeyboardMarkup:
        def __init__(self, inline_keyboard=None, **kwargs):
            self.inline_keyboard = inline_keyboard or []

    class _TelegramObject:
        pass

    class _Update(_TelegramObject):
        def __init__(self):
            self.message = None
            self.callback_query = None
            self.inline_query = None

    _aiogram_types.KeyboardButton = _KeyboardButton  # type: ignore[attr-defined]
    _aiogram_types.ReplyKeyboardMarkup = _ReplyKeyboardMarkup  # type: ignore[attr-defined]
    _aiogram_types.InlineKeyboardButton = _InlineKeyboardButton  # type: ignore[attr-defined]
    _aiogram_types.InlineKeyboardMarkup = _InlineKeyboardMarkup  # type: ignore[attr-defined]
    _aiogram_types.TelegramObject = _TelegramObject  # type: ignore[attr-defined]
    _aiogram_types.Update = _Update  # type: ignore[attr-defined]
    sys.modules["aiogram.types"] = _aiogram_types


from bot.keyboards.common import (  # noqa: E402
    CB_BACK,
    CB_CANCEL,
    CB_CONFIRM,
    back_button,
    back_kb,
    cancel_button,
    confirm_button,
    confirm_cancel_kb,
)
from bot.keyboards.heroes import (  # noqa: E402
    HERO_CB_PREFIX,
    HERO_PAGE_CB_PREFIX,
    PAGE_SIZE,
    HeroButton,
    hero_list_kb,
    parse_hero_callback,
    parse_hero_page_callback,
)
from bot.keyboards.menu import (  # noqa: E402
    ALL_MENU_BUTTONS,
    BTN_BUILD,
    BTN_DRAFT,
    BTN_MATCH,
    BTN_META,
    BTN_PROFILE,
    BTN_SETTINGS,
    main_menu_kb,
)
from bot.keyboards.roles import (  # noqa: E402
    parse_role_callback,
    role_selection_kb,
)

# ===== Тесты menu.py =====


class TestMainMenu:
    def test_main_menu_has_6_buttons(self):
        kb = main_menu_kb()
        all_buttons = [btn for row in kb.keyboard for btn in row]
        assert len(all_buttons) == 6

    def test_main_menu_3_rows(self):
        kb = main_menu_kb()
        assert len(kb.keyboard) == 3

    def test_main_menu_2_buttons_per_row(self):
        kb = main_menu_kb()
        for row in kb.keyboard:
            assert len(row) == 2

    def test_main_menu_button_texts(self):
        kb = main_menu_kb()
        texts = [btn.text for row in kb.keyboard for btn in row]
        assert texts == [BTN_DRAFT, BTN_META, BTN_MATCH, BTN_BUILD, BTN_PROFILE, BTN_SETTINGS]

    def test_main_menu_resize_keyboard(self):
        kb = main_menu_kb()
        assert kb.resize_keyboard is True

    def test_all_menu_buttons_tuple(self):
        assert len(ALL_MENU_BUTTONS) == 6
        assert BTN_DRAFT in ALL_MENU_BUTTONS
        assert BTN_SETTINGS in ALL_MENU_BUTTONS


# ===== Тесты roles.py =====


class TestRoleSelection:
    def test_role_selection_has_5_buttons(self):
        kb = role_selection_kb()
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        assert len(all_buttons) == 5

    def test_role_selection_callback_data(self):
        kb = role_selection_kb()
        callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
        assert callbacks == [
            "role:1",
            "role:2",
            "role:3",
            "role:4",
            "role:5",
        ]

    def test_role_selection_labels_ru(self):
        kb = role_selection_kb()
        texts = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "Керри" in texts
        assert "Мидер" in texts
        assert "Хард-саппорт" in texts

    def test_parse_role_callback_valid(self):
        from core.enums import Role

        assert parse_role_callback("role:1") == Role.CARRY
        assert parse_role_callback("role:5") == Role.HARD_SUPPORT

    def test_parse_role_callback_invalid(self):
        assert parse_role_callback("role:99") is None
        assert parse_role_callback("invalid") is None
        assert parse_role_callback("role:abc") is None


# ===== Тесты common.py =====


class TestCommonButtons:
    def test_back_button(self):
        btn = back_button()
        assert btn.callback_data == CB_BACK
        assert "Назад" in btn.text

    def test_cancel_button(self):
        btn = cancel_button()
        assert btn.callback_data == CB_CANCEL
        assert "Отмена" in btn.text

    def test_confirm_button(self):
        btn = confirm_button()
        assert btn.callback_data == CB_CONFIRM
        assert "Подтвердить" in btn.text

    def test_confirm_cancel_kb(self):
        kb = confirm_cancel_kb()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 2
        assert kb.inline_keyboard[0][0].callback_data == CB_CONFIRM
        assert kb.inline_keyboard[0][1].callback_data == CB_CANCEL

    def test_back_kb(self):
        kb = back_kb()
        assert len(kb.inline_keyboard) == 1
        assert len(kb.inline_keyboard[0]) == 1
        assert kb.inline_keyboard[0][0].callback_data == CB_BACK


# ===== Тесты heroes.py =====


def _make_heroes(count: int) -> list[HeroButton]:
    """Создать список тестовых героев."""
    return [HeroButton(hero_id=i, name=f"Hero_{i}") for i in range(1, count + 1)]


class TestHeroListKb:
    def test_single_page_no_nav(self):
        heroes = _make_heroes(5)
        kb = hero_list_kb(heroes, page=0)
        # 5 героев: 3 ряда (2+2+1), без навигации
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        hero_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_CB_PREFIX)]
        assert len(hero_buttons) == 5
        # Нет кнопок пагинации
        nav_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_PAGE_CB_PREFIX)]
        assert len(nav_buttons) == 0

    def test_first_page_has_next(self):
        heroes = _make_heroes(20)
        kb = hero_list_kb(heroes, page=0)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        nav_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_PAGE_CB_PREFIX)]
        assert len(nav_buttons) == 1
        assert nav_buttons[0].callback_data == "hero_page:1"
        assert "Далее" in nav_buttons[0].text

    def test_middle_page_has_both_nav(self):
        heroes = _make_heroes(30)
        kb = hero_list_kb(heroes, page=1)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        nav_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_PAGE_CB_PREFIX)]
        assert len(nav_buttons) == 2
        callbacks = {b.callback_data for b in nav_buttons}
        assert "hero_page:0" in callbacks
        assert "hero_page:2" in callbacks

    def test_last_page_has_back(self):
        heroes = _make_heroes(20)
        total_pages = (20 + PAGE_SIZE - 1) // PAGE_SIZE
        kb = hero_list_kb(heroes, page=total_pages - 1)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        nav_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_PAGE_CB_PREFIX)]
        assert len(nav_buttons) == 1
        assert "Назад" in nav_buttons[0].text

    def test_page_size_limit(self):
        heroes = _make_heroes(20)
        kb = hero_list_kb(heroes, page=0)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        hero_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_CB_PREFIX)]
        assert len(hero_buttons) == PAGE_SIZE

    def test_empty_list(self):
        kb = hero_list_kb([], page=0)
        assert len(kb.inline_keyboard) == 0

    def test_negative_page_clamps_to_zero(self):
        heroes = _make_heroes(5)
        kb = hero_list_kb(heroes, page=-1)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        hero_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_CB_PREFIX)]
        assert len(hero_buttons) == 5

    def test_page_beyond_max_clamps(self):
        heroes = _make_heroes(5)
        kb = hero_list_kb(heroes, page=100)
        all_buttons = [btn for row in kb.inline_keyboard for btn in row]
        hero_buttons = [b for b in all_buttons if b.callback_data.startswith(HERO_CB_PREFIX)]
        assert len(hero_buttons) == 5

    def test_hero_buttons_2_per_row(self):
        heroes = _make_heroes(PAGE_SIZE)
        kb = hero_list_kb(heroes, page=0)
        # Без навигации — все ряды по 2
        for row in kb.inline_keyboard:
            assert len(row) <= 2


class TestParseCallbacks:
    def test_parse_hero_callback_valid(self):
        assert parse_hero_callback("hero:42") == 42
        assert parse_hero_callback("hero:1") == 1

    def test_parse_hero_callback_invalid(self):
        assert parse_hero_callback("role:1") is None
        assert parse_hero_callback("hero:abc") is None
        assert parse_hero_callback("") is None

    def test_parse_hero_page_callback_valid(self):
        assert parse_hero_page_callback("hero_page:3") == 3
        assert parse_hero_page_callback("hero_page:0") == 0

    def test_parse_hero_page_callback_invalid(self):
        assert parse_hero_page_callback("hero:1") is None
        assert parse_hero_page_callback("hero_page:abc") is None
