"""Клиент для парсинга dota2protracker.com — билды героев от про-игроков."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from curl_cffi import requests as cffi_requests

from core.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://dota2protracker.com"
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Модели ответа
# ---------------------------------------------------------------------------


@dataclass
class ProMetaHero:
    """Герой из мета-списка protracker."""

    hero_id: int
    matches: int
    wins: int
    winrate: float  # wins / matches (0.0 — 1.0)
    contest_rate: float  # пикрейт (0.0 — 1.0)
    meta_score: float  # из detailed_stats


@dataclass
class ProItemBuild:
    """Предмет из билда protracker."""

    name: str
    purchase_rate: float = 0.0  # 0.0 — 1.0
    winrate: float = 0.0  # 0.0 — 1.0
    avg_time: int = 0  # минуты
    is_core: bool = False  # ≥50% purchase rate


@dataclass
class ProTalent:
    """Талант из protracker."""

    level: int  # 10, 15, 20, 25
    name: str
    pick_rate: float = 0.0  # 0.0 — 1.0


@dataclass
class ProBuildData:
    """Полные данные билда героя с protracker."""

    hero_name: str
    position: str = ""  # "pos 1", "pos 2", etc.
    patch: str = ""
    facet_name: str = ""
    matches: int = 0
    winrate: float = 0.0

    starting_items: list[list[str]] = field(default_factory=list)  # наборы стартовых
    core_items: list[ProItemBuild] = field(default_factory=list)
    mid_late_items: list[ProItemBuild] = field(default_factory=list)
    skill_order: list[str] = field(default_factory=list)  # ["Q", "W", "E", ...]
    talents: list[ProTalent] = field(default_factory=list)
    neutral_items: dict[int, list[str]] = field(default_factory=dict)  # tier -> [name, ...]


# ---------------------------------------------------------------------------
# Клиент
# ---------------------------------------------------------------------------


# Допустимые значения MMR для protracker
_PROTRACKER_MMR_TIERS = [0, 2000, 4000, 5000, 6000, 7000, 8000]


def _mmr_to_protracker(mmr: int) -> int:
    """Округлить MMR к ближайшему значению protracker."""
    if mmr <= 0:
        return 0
    best = _PROTRACKER_MMR_TIERS[0]
    for tier in _PROTRACKER_MMR_TIERS:
        if abs(tier - mmr) < abs(best - mmr):
            best = tier
    return best


class ProtrackerClient:
    """Парсер dota2protracker.com для получения билдов героев."""

    def __init__(self) -> None:
        self._session = cffi_requests.Session(impersonate="chrome")

    async def get_meta_heroes(
        self,
        position: int,
        mmr: int = 0,
        period: int = 8,
    ) -> list[ProMetaHero]:
        """Получить мета-героев с protracker для позиции и MMR.

        Args:
            position: Позиция 1-5.
            mmr: MMR игрока (будет округлён к ближайшему тиру protracker).
            period: Период в днях (по умолчанию 8).

        Returns:
            Список ProMetaHero, отсортированный по winrate убывание.
        """
        pt_mmr = _mmr_to_protracker(mmr)
        url = (
            f"{_BASE_URL}/meta"
            f"?mmr={pt_mmr}&position=pos%2B{position}&period={period}"
        )
        logger.info("Protracker meta: загрузка %s", url)

        try:
            resp = await asyncio.to_thread(
                self._session.get,
                url,
                timeout=15,
            )
        except Exception as exc:
            raise ProtrackerError(f"Ошибка загрузки мета: {exc}") from exc

        if resp.status_code != 200:
            raise ProtrackerError(f"Protracker meta вернул HTTP {resp.status_code}")

        raw_data = _extract_meta_data(resp.text)
        return _parse_meta_heroes(raw_data)

    async def get_hero_build(self, hero_name: str) -> ProBuildData:
        """Получить билд героя по имени (English).

        Args:
            hero_name: Имя героя на английском (Anti-Mage, Storm Spirit и т.д.)

        Returns:
            ProBuildData с предметами, скиллами, талантами.

        Raises:
            ProtrackerError: если страница не загружена или данные не распарсены.
        """
        html = await self._fetch_page(hero_name)
        raw_data = _extract_sveltekit_data(html)
        return _parse_build_data(hero_name, raw_data)

    async def _fetch_page(self, hero_name: str) -> str:
        """Загрузить HTML-страницу героя."""
        url = f"{_BASE_URL}/hero/{quote(hero_name)}"
        logger.info("Protracker: загрузка %s", url)

        try:
            resp = await asyncio.to_thread(
                self._session.get,
                url,
                timeout=15,
            )
        except Exception as exc:
            raise ProtrackerError(f"Ошибка загрузки {url}: {exc}") from exc

        if resp.status_code != 200:
            raise ProtrackerError(f"Protracker вернул HTTP {resp.status_code} для {hero_name}")

        return resp.text

    def close(self) -> None:
        """Закрыть сессию."""
        self._session.close()


# ---------------------------------------------------------------------------
# Парсинг SvelteKit данных
# ---------------------------------------------------------------------------

# Regex для извлечения массива data из SvelteKit bootstrap-скрипта
_DATA_RE = re.compile(
    r"__sveltekit_\w+\s*=\s*\{[^}]*\};\s*"
    r".*?\.start\s*\(\s*app\s*,\s*element\s*,\s*\{[^}]*data:\s*(\[.+?\])\s*,\s*form",
    re.DOTALL,
)

# Альтернативный паттерн — данные в deferred формате
_DATA_RE_ALT = re.compile(
    r"data:\s*(\[\s*\{.*?\}\s*(?:,\s*(?:null|\{.*?\})\s*)*\])\s*,\s*form",
    re.DOTALL,
)


def _extract_meta_data(html: str) -> list[dict[str, Any]]:
    """Извлечь мета-данные из SvelteKit bootstrap-скрипта страницы /meta.

    На странице /meta структура: data[0] = глобальные, data[1] = мета-данные.
    """
    match = _DATA_RE.search(html)
    if not match:
        match = _DATA_RE_ALT.search(html)
    if not match:
        raise ProtrackerError("Не удалось найти SvelteKit данные в HTML (meta)")

    raw = match.group(1)
    json_str = _js_to_json(raw)

    try:
        data_array = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ProtrackerError(f"Ошибка парсинга JSON (meta): {exc}") from exc

    if not isinstance(data_array, list) or len(data_array) < 2:
        raise ProtrackerError(
            f"Неожиданный формат данных meta: {len(data_array)} элементов"
        )

    # data[1] содержит мета-данные
    meta_entry = data_array[1]
    if not isinstance(meta_entry, dict):
        raise ProtrackerError("Мета-данные отсутствуют в ответе")

    meta_data = meta_entry.get("data", meta_entry)
    meta_list = meta_data.get("meta", [])

    if not isinstance(meta_list, list):
        raise ProtrackerError("Поле 'meta' не является списком")

    return meta_list


def _parse_meta_heroes(meta_list: list[dict[str, Any]]) -> list[ProMetaHero]:
    """Парсить и агрегировать мета-героев (суммируя варианты/фасеты)."""
    # Агрегация по hero_id (суммируем wins/matches через все hero_variant)
    agg: dict[int, dict[str, float]] = {}

    for entry in meta_list:
        if not isinstance(entry, dict):
            continue

        hero_id = entry.get("hero_id")
        if hero_id is None:
            continue
        hero_id = int(hero_id)

        matches = int(entry.get("matches", 0) or 0)
        wins = int(entry.get("wins", 0) or 0)
        contest_rate = _to_float(entry.get("contest_rate", 0))

        detailed = entry.get("detailed_stats") or {}
        meta_score = _to_float(detailed.get("meta_score", 0))

        if hero_id not in agg:
            agg[hero_id] = {
                "matches": 0,
                "wins": 0,
                "contest_rate": contest_rate,
                "meta_score": meta_score,
            }

        agg[hero_id]["matches"] += matches
        agg[hero_id]["wins"] += wins
        # Берём максимальный contest_rate и meta_score среди вариантов
        if contest_rate > agg[hero_id]["contest_rate"]:
            agg[hero_id]["contest_rate"] = contest_rate
        if meta_score > agg[hero_id]["meta_score"]:
            agg[hero_id]["meta_score"] = meta_score

    result: list[ProMetaHero] = []
    for hero_id, data in agg.items():
        matches = int(data["matches"])
        wins = int(data["wins"])
        winrate = wins / matches if matches > 0 else 0.0

        result.append(
            ProMetaHero(
                hero_id=hero_id,
                matches=matches,
                wins=wins,
                winrate=winrate,
                contest_rate=data["contest_rate"],
                meta_score=data["meta_score"],
            )
        )

    # Сортируем по winrate убывание
    result.sort(key=lambda h: h.winrate, reverse=True)
    return result


def _extract_sveltekit_data(html: str) -> dict[str, Any]:
    """Извлечь данные из SvelteKit bootstrap-скрипта.

    SvelteKit встраивает данные в виде JS-литерала в HTML.
    Нужно конвертировать JS → JSON и распарсить.
    """
    match = _DATA_RE.search(html)
    if not match:
        match = _DATA_RE_ALT.search(html)
    if not match:
        raise ProtrackerError("Не удалось найти SvelteKit данные в HTML")

    raw = match.group(1)

    # Конвертация JS объектных литералов в JSON
    json_str = _js_to_json(raw)

    try:
        data_array = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ProtrackerError(f"Ошибка парсинга JSON: {exc}") from exc

    if not isinstance(data_array, list) or len(data_array) < 3:
        raise ProtrackerError(f"Неожиданный формат данных: {len(data_array)} элементов")

    # data[0] — глобальные данные (itemsMapping, heroesMapping)
    # data[1] — null
    # data[2] — данные героя (buildData, heroStats, etc.)
    hero_entry = data_array[2]
    if not isinstance(hero_entry, dict):
        raise ProtrackerError("Данные героя отсутствуют в ответе")

    hero_data = hero_entry.get("data", hero_entry)

    # Также извлекаем itemsMapping из data[0]
    global_entry = data_array[0]
    if isinstance(global_entry, dict):
        global_data = global_entry.get("data", global_entry)
        if "itemsMapping" in global_data:
            hero_data["_itemsMapping"] = global_data["itemsMapping"]

    return hero_data


def _js_to_json(raw: str) -> str:
    """Конвертировать JS объектные литералы в валидный JSON.

    Обрабатывает:
    - Unquoted keys: {foo: 1} → {"foo": 1}
    - new Date(ts) → ts
    - Bare decimals: .5 → 0.5
    - Trailing commas
    - undefined → null
    """
    s = raw

    # Заменяем new Date(timestamp) на timestamp
    s = re.sub(r"new\s+Date\((\d+)\)", r"\1", s)

    # Заменяем undefined на null
    s = re.sub(r"\bundefined\b", "null", s)

    # Добавляем кавычки к unquoted keys
    # Паттерн: после { или , или начала — слово-без-кавычек с двоеточием
    s = re.sub(r"(?<=[{,\[])\s*(\w+)\s*:", r'"\1":', s)
    # Первый ключ после { может не иметь запятую перед ним
    s = re.sub(r"{\s*(\w+)\s*:", r'"{"\1":', s)
    # Убираем лишние кавычки-скобки от предыдущей замены
    s = s.replace('"{', "{")

    # Bare decimals: .5 → 0.5 и -.5 → -0.5
    s = re.sub(r"(?<=[:,\[])(-?)(\.\d)", r"\g<1>0\2", s)
    s = re.sub(r"(?<=:)\s*(-?)(\.\d)", r" \g<1>0\2", s)

    # Trailing commas перед } или ]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    return s


# ---------------------------------------------------------------------------
# Парсинг данных героя
# ---------------------------------------------------------------------------


def _parse_build_data(hero_name: str, data: dict[str, Any]) -> ProBuildData:
    """Распарсить данные героя из protracker в ProBuildData."""
    result = ProBuildData(hero_name=hero_name)

    result.position = data.get("position", "")
    result.patch = data.get("patchversion", "")

    # Берём первый (основной) билд
    build_list = data.get("buildData", [])
    if not build_list:
        logger.warning("Protracker: нет buildData для %s", hero_name)
        return result

    build_entry = build_list[0]

    # buildData[0] содержит вложенный build_data с данными билда
    build = build_entry.get("build_data", {})
    if not build:
        logger.warning("Protracker: нет build_data для %s", hero_name)
        return result

    # Матчи и WR из build_entry
    result.matches = build_entry.get("num_matches", 0)
    result.winrate = _to_float(build_entry.get("win_rate", 0))

    # Фасет из facetData
    facet_data = data.get("facetData", {})
    facet_id = build_entry.get("facet_id", 0)
    if isinstance(facet_data, dict):
        facets = facet_data.get("facets", [])
        for f in facets:
            if isinstance(f, dict) and f.get("hero_variant") == facet_id:
                result.facet_name = f.get("name", "")
                break

    items_mapping = data.get("_itemsMapping")

    # Стартовые предметы
    result.starting_items = _parse_starting_items(build, items_mapping)

    # Anchor items (core)
    result.core_items = _parse_anchor_items(build, items_mapping)

    # Mid/late items
    result.mid_late_items = _parse_mid_late_items(build, items_mapping)

    # Скиллы
    result.skill_order = _parse_abilities(build, data.get("abilitiesData"))

    # Таланты
    result.talents = _parse_talents(build)

    # Нейтральные предметы
    result.neutral_items = _parse_neutrals(build, items_mapping)

    return result


def _get_item_name(item_id: int | str, items_mapping: dict | list | None) -> str:
    """Получить имя предмета из маппинга protracker."""
    if items_mapping is None:
        return f"Item #{item_id}"

    # itemsMapping может быть списком или словарём
    if isinstance(items_mapping, list):
        for item in items_mapping:
            if isinstance(item, dict) and item.get("item_id") == int(item_id):
                return item.get("displayName", item.get("name", f"Item #{item_id}"))
    elif isinstance(items_mapping, dict):
        item = items_mapping.get(str(item_id))
        if isinstance(item, dict):
            return item.get("displayName", item.get("name", f"Item #{item_id}"))

    return f"Item #{item_id}"


def _parse_starting_items(
    build: dict[str, Any],
    items_mapping: dict | list | None,
) -> list[list[str]]:
    """Парсить стартовые предметы (несколько наборов).

    Формат: [[item_id, item_id, ...], {count, win_rate}]
    """
    result: list[list[str]] = []

    starting_new = build.get("starting_items_new") or build.get("starting_items")
    if not starting_new or not isinstance(starting_new, list):
        return result

    for entry in starting_new[:3]:  # Топ-3 набора
        if isinstance(entry, list) and len(entry) >= 1:
            # Формат: [[item_ids], {stats}] — первый элемент массив ID
            item_ids = entry[0] if isinstance(entry[0], list) else entry
            names = [_get_item_name(iid, items_mapping) for iid in item_ids if isinstance(iid, int)]
            if names:
                result.append(names)

    return result


def _parse_anchor_items(
    build: dict[str, Any],
    items_mapping: dict | list | None,
) -> list[ProItemBuild]:
    """Парсить anchor items (core items).

    Формат: {raw_item_id, pr, win_rate, avg_minute, count}
    """
    result: list[ProItemBuild] = []

    anchors = build.get("anchor_items", [])
    if not anchors or not isinstance(anchors, list):
        return result

    for item in anchors:
        if not isinstance(item, dict):
            continue

        item_id = item.get("raw_item_id", 0)
        name = _get_item_name(item_id, items_mapping)
        pick_rate = _to_float(item.get("pr", 0))
        winrate = _to_float(item.get("win_rate", 0))
        avg_time = int(_to_float(item.get("avg_minute", 0)))

        result.append(
            ProItemBuild(
                name=name,
                purchase_rate=pick_rate,
                winrate=winrate,
                avg_time=avg_time,
                is_core=pick_rate >= 0.5,
            )
        )

    return result


def _parse_mid_late_items(
    build: dict[str, Any],
    items_mapping: dict | list | None,
) -> list[ProItemBuild]:
    """Парсить mid/late game items.

    Формат: {raw_item_id, pr, win_rate, avg_minute, count}
    """
    result: list[ProItemBuild] = []

    items = build.get("items_mid_late", [])
    if not items or not isinstance(items, list):
        return result

    for item in items:
        if not isinstance(item, dict):
            continue

        item_id = item.get("raw_item_id", 0)
        name = _get_item_name(item_id, items_mapping)
        pick_rate = _to_float(item.get("pr", 0))
        winrate = _to_float(item.get("win_rate", 0))
        avg_time = int(_to_float(item.get("avg_minute", 0)))

        result.append(
            ProItemBuild(
                name=name,
                purchase_rate=pick_rate,
                winrate=winrate,
                avg_time=avg_time,
                is_core=pick_rate >= 0.5,
            )
        )

    return result


def _parse_abilities(
    build: dict[str, Any],
    abilities_data: list | dict | None,
) -> list[str]:
    """Парсить порядок прокачки скиллов (первые 10 уровней).

    abilities_new: [[ability_id, ability_id, ...], {pr, wins, count, win_rate}]
    abilities: [{ability_id, name, displayName}, ...]
    """
    # abilities_new — массив последовательностей, берём первую (самую популярную)
    abilities_new = build.get("abilities_new")
    if abilities_new and isinstance(abilities_new, list):
        top_seq = abilities_new[0]
        # Формат: [[ability_ids], {stats}]
        if isinstance(top_seq, list) and len(top_seq) >= 1:
            ability_ids = top_seq[0] if isinstance(top_seq[0], list) else top_seq
            return _abilities_to_letters(ability_ids, abilities_data)

    # Fallback: abilities — массив объектов {ability_id, displayName}
    abilities = build.get("abilities", [])
    if abilities and isinstance(abilities, list):
        return _abilities_to_letters(abilities, abilities_data)

    return []


def _abilities_to_letters(
    abilities: list[Any],
    abilities_data: list | dict | None,
) -> list[str]:
    """Конвертировать список способностей в буквы Q/W/E/R."""
    # Строим маппинг ability_id → порядковый номер (Q=0, W=1, E=2, R=3)
    # На основе abilities_data или по порядку появления
    ability_id_to_slot: dict[int, int] = {}
    slot_labels = ["Q", "W", "E", "R", "D", "F"]

    result: list[str] = []
    for ab in abilities:
        if isinstance(ab, dict):
            ab_id = ab.get("ability_id", 0)
        elif isinstance(ab, int):
            ab_id = ab
        else:
            continue

        if ab_id not in ability_id_to_slot:
            slot_idx = len(ability_id_to_slot)
            if slot_idx < len(slot_labels):
                ability_id_to_slot[ab_id] = slot_idx

        slot = ability_id_to_slot.get(ab_id, -1)
        if 0 <= slot < len(slot_labels):
            result.append(slot_labels[slot])
        else:
            result.append("?")

    return result[:10]  # Первые 10 уровней


def _parse_talents(build: dict[str, Any]) -> list[ProTalent]:
    """Парсить таланты (4 уровня: 10, 15, 20, 25).

    Формат: {lvl, pr, choice: "lt"/"rt", left: {displayName, ...}, right: {displayName, ...}}
    """
    result: list[ProTalent] = []

    talents = build.get("talents", [])
    if not talents or not isinstance(talents, list):
        return result

    for talent_tier in talents:
        if not isinstance(talent_tier, dict):
            continue

        level = talent_tier.get("lvl", 0)
        choice = talent_tier.get("choice", "")
        pick_rate = _to_float(talent_tier.get("pr", 0))

        # Берём выбранный талант (lt = left, rt = right)
        if choice == "lt":
            chosen = talent_tier.get("left", {})
        else:
            chosen = talent_tier.get("right", {})

        if isinstance(chosen, dict):
            name = chosen.get("displayName", chosen.get("name", ""))
        else:
            name = ""

        if level and name:
            result.append(ProTalent(level=level, name=name, pick_rate=pick_rate))

    return result


def _parse_neutrals(
    build: dict[str, Any],
    items_mapping: dict | list | None,
) -> dict[int, list[str]]:
    """Парсить нейтральные предметы по тирам.

    Формат: {"0": {"item_id": {displayName, pick_rate, win_rate, ...}}, "1": {...}, ...}
    Тиры: 0-4 (tier 0 = tier 1 в игре).
    """
    result: dict[int, list[str]] = {}

    neutrals = build.get("neutral_stats", {})
    if not neutrals or not isinstance(neutrals, dict):
        return result

    for tier_key, tier_items in neutrals.items():
        try:
            tier = int(tier_key) + 1  # protracker 0-indexed → game 1-indexed
        except (ValueError, TypeError):
            continue
        if not isinstance(tier_items, dict):
            continue

        # Сортируем по pick_rate, берём топ-3
        sorted_items = sorted(
            tier_items.values(),
            key=lambda x: x.get("pick_rate", 0) if isinstance(x, dict) else 0,
            reverse=True,
        )
        names = []
        for item in sorted_items[:3]:
            if isinstance(item, dict):
                name = item.get("displayName") or item.get("name", "")
                if name:
                    names.append(name)
        if names:
            result[tier] = names

    return result


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------


def _to_float(val: Any) -> float:
    """Безопасная конвертация в float."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _parse_time(val: Any) -> int:
    """Парсить время в минуты."""
    if val is None:
        return 0
    try:
        v = float(val)
        # Если значение > 100, скорее всего это секунды
        if v > 100:
            return int(v / 60)
        return int(v)
    except (ValueError, TypeError):
        # Попробуем парсить строку вроде "12m" или "12:30"
        if isinstance(val, str):
            m = re.match(r"(\d+)", val)
            if m:
                return int(m.group(1))
        return 0


# ---------------------------------------------------------------------------
# Исключения
# ---------------------------------------------------------------------------


class ProtrackerError(Exception):
    """Ошибка при работе с dota2protracker.com."""
