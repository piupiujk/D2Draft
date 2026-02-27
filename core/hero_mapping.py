"""Двусторонний маппинг героев Dota 2: поиск по ID, имени EN/RU, сокращению."""

from core.constants import HERO_BY_ID, HEROES, HeroData
from core.exceptions import HeroNotFound

# --- Индексы для быстрого поиска (строятся один раз при импорте) ---

# Ключ — имя в нижнем регистре, значение — hero_id
_NAME_TO_ID: dict[str, int] = {}

# Заполняем индексы из HEROES
for _h in HEROES:
    _NAME_TO_ID[_h.name_en.lower()] = _h.hero_id
    _NAME_TO_ID[_h.name_ru.lower()] = _h.hero_id

# Популярные сокращения и альтернативные имена -> hero_id
_ALIASES: dict[str, int] = {
    # --- Керри / Мид ---
    "am": 1,
    "антимаг": 1,
    "магина": 1,
    "bs": 4,
    "бс": 4,
    "cm": 5,
    "кмка": 5,
    "dr": 6,
    "дровка": 6,
    "es": 7,
    "шейкер": 7,
    "jugger": 8,
    "джагер": 8,
    "sf": 11,
    "невермор": 11,
    "pl": 12,
    "пл": 12,
    "sk": 16,
    "песчаный король": 16,
    "ss": 17,
    "шторм": 17,
    "vs": 20,
    "венга спирит": 20,
    "wr": 21,
    "винда": 21,
    "виндранер": 21,
    "lina": 25,
    "sd": 27,
    "шаман": 27,
    "wd": 30,
    "вич": 30,
    "bm": 38,
    "бист": 38,
    "qop": 39,
    "квоп": 39,
    "королева боли": 39,
    "fv": 41,
    "фв": 41,
    "фейслесс": 41,
    "wk": 42,
    "врайс": 42,
    "скелетон кинг": 42,
    "dp": 43,
    "деспро": 43,
    "pa": 44,
    "па": 44,
    "фантомка": 44,
    "ta": 46,
    "тёмплар": 46,
    "темплар": 46,
    "dk": 49,
    "дк": 49,
    "драгон": 49,
    "clock": 51,
    "клок": 51,
    "lesh": 52,
    "леш": 52,
    "np": 53,
    "нп": 53,
    "пророк": 53,
    "ls": 54,
    "найкс": 54,
    "ds": 55,
    "дс": 55,
    "ns": 60,
    "нс": 60,
    "ночной": 60,
    "brood": 61,
    "бруд": 61,
    "bh": 62,
    "бх": 62,
    "баунти": 62,
    "aa": 68,
    "аа": 68,
    "аппа": 68,
    "sb": 71,
    "сб": 71,
    "баратрум": 71,
    "gyro": 72,
    "гиро": 72,
    "alch": 73,
    "алхим": 73,
    "invo": 74,
    "инвок": 74,
    "od": 76,
    "од": 76,
    "аутворлд": 76,
    "brew": 78,
    "брю": 78,
    "ld": 80,
    "лд": 80,
    "медведь": 80,
    "ck": 81,
    "хк": 81,
    "tp": 83,
    "трент": 83,
    "ogre": 84,
    "огр": 84,
    "kotl": 90,
    "котёл": 90,
    "кипер": 90,
    "io": 91,
    "wisp": 91,
    "висп": 91,
    "troll": 95,
    "тролик": 95,
    "cent": 96,
    "кент": 96,
    "mag": 97,
    "маг": 97,
    "timber": 98,
    "тимбер": 98,
    "bb": 99,
    "бб": 99,
    "бристл": 99,
    "sky": 101,
    "скай": 101,
    "aba": 102,
    "аба": 102,
    "et": 103,
    "титан": 103,
    "lc": 104,
    "лк": 104,
    "легионка": 104,
    "ember": 106,
    "эмбер": 106,
    "earth": 107,
    "ёрс": 107,
    "tb": 109,
    "тб": 109,
    "террор": 109,
    "mk": 114,
    "мк": 114,
    "манки": 114,
    "dw": 119,
    "виллоу": 119,
    "pango": 120,
    "панго": 120,
    "grim": 121,
    "грим": 121,
    "hood": 123,
    "худ": 123,
    "snap": 128,
    "снэп": 128,
    "бабка": 128,
    "mars": 129,
    "ring": 131,
    "ринг": 131,
    "dawn": 135,
    "дон": 135,
    "марси": 136,
    "pb": 137,
    "пб": 137,
    "зверь": 137,
    "муэрта": 138,
    "кез": 145,
    "ларго": 155,
    # Void Spirit отдельно (т.к. "vs" уже занят Vengeful Spirit)
    "войд спирит": 126,
    "void spirit": 126,
}

# Добавляем алиасы в общий индекс
for _alias, _hero_id in _ALIASES.items():
    _NAME_TO_ID.setdefault(_alias.lower(), _hero_id)


# --- Публичный API ---


def get_hero_by_id(hero_id: int) -> HeroData:
    """Получить данные героя по ID.

    Raises:
        HeroNotFound: если героя с таким ID нет.
    """
    hero = HERO_BY_ID.get(hero_id)
    if hero is None:
        raise HeroNotFound(str(hero_id))
    return hero


def get_hero_id_by_name(name: str) -> int:
    """Найти hero_id по имени (EN/RU) или сокращению. Нечувствителен к регистру.

    Raises:
        HeroNotFound: если герой не найден.
    """
    hero_id = _NAME_TO_ID.get(name.lower().strip())
    if hero_id is None:
        raise HeroNotFound(name)
    return hero_id


def find_hero(query: str) -> HeroData:
    """Найти героя по любому запросу (ID, имя EN/RU, сокращение).

    Raises:
        HeroNotFound: если герой не найден.
    """
    query = query.strip()

    # Попытка парсинга как числовой ID
    if query.isdigit():
        return get_hero_by_id(int(query))

    hero_id = get_hero_id_by_name(query)
    return HERO_BY_ID[hero_id]


def get_name_en(hero_id: int) -> str:
    """Получить английское имя героя по ID."""
    return get_hero_by_id(hero_id).name_en


def get_name_ru(hero_id: int) -> str:
    """Получить русское имя героя по ID."""
    return get_hero_by_id(hero_id).name_ru
