"""HTTP-клиент Stratz GraphQL API: мета-герои, билды, matchups."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import httpx
from curl_cffi import requests as cffi_requests

from core.enums import RankBracket, Role
from core.exceptions import APIRateLimited
from core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Маппинг enum-ов проекта -> Stratz API
# ---------------------------------------------------------------------------

# Stratz использует сгруппированные брекеты по два ранга
RANK_TO_STRATZ_BRACKET: dict[RankBracket, str] = {
    RankBracket.HERALD: "HERALD",
    RankBracket.GUARDIAN: "GUARDIAN",
    RankBracket.CRUSADER: "CRUSADER",
    RankBracket.ARCHON: "ARCHON",
    RankBracket.LEGEND: "LEGEND",
    RankBracket.ANCIENT: "ANCIENT",
    RankBracket.DIVINE: "DIVINE",
    RankBracket.IMMORTAL: "IMMORTAL",
}

# RankBracketBasicEnum — парные брекеты для heroStats.winWeek/stats
RANK_TO_STRATZ_BRACKET_BASIC: dict[RankBracket, str] = {
    RankBracket.HERALD: "HERALD_GUARDIAN",
    RankBracket.GUARDIAN: "HERALD_GUARDIAN",
    RankBracket.CRUSADER: "CRUSADER_ARCHON",
    RankBracket.ARCHON: "CRUSADER_ARCHON",
    RankBracket.LEGEND: "LEGEND_ANCIENT",
    RankBracket.ANCIENT: "LEGEND_ANCIENT",
    RankBracket.DIVINE: "DIVINE_IMMORTAL",
    RankBracket.IMMORTAL: "DIVINE_IMMORTAL",
}

ROLE_TO_STRATZ_POSITION: dict[Role, str] = {
    Role.CARRY: "POSITION_1",
    Role.MID: "POSITION_2",
    Role.OFFLANE: "POSITION_3",
    Role.SOFT_SUPPORT: "POSITION_4",
    Role.HARD_SUPPORT: "POSITION_5",
}

# ---------------------------------------------------------------------------
# Модели ответов
# ---------------------------------------------------------------------------


@dataclass
class MetaHeroStats:
    """Статистика героя из мета-запроса."""

    hero_id: int
    match_count: int
    win_count: int
    trend: float = 0.0  # Дельта винрейта (this_week - last_week)

    @property
    def winrate(self) -> float:
        """Винрейт (0.0 — 1.0)."""
        return self.win_count / self.match_count if self.match_count > 0 else 0.0


@dataclass
class ItemPurchase:
    """Элемент билда — предмет с метриками."""

    item_id: int
    match_count: int = 0
    win_count: int = 0
    time: int | None = None
    was_given: bool = False

    @property
    def winrate(self) -> float:
        """Винрейт с этим предметом (0.0 — 1.0)."""
        return self.win_count / self.match_count if self.match_count > 0 else 0.0


@dataclass
class HeroBuildData:
    """Данные билда героя из Stratz API."""

    hero_id: int
    starting_items: list[ItemPurchase] = field(default_factory=list)
    boot_items: list[ItemPurchase] = field(default_factory=list)
    early_game: list[ItemPurchase] = field(default_factory=list)
    mid_game: list[ItemPurchase] = field(default_factory=list)
    late_game: list[ItemPurchase] = field(default_factory=list)


@dataclass
class AbilityInfo:
    """Информация о способности из гайда."""

    ability_id: int
    slot: int  # 0-3 для обычных, 4+ для талантов


@dataclass
class TalentInfo:
    """Информация о таланте."""

    ability_id: int
    slot: int
    win_count: int = 0
    match_count: int = 0

    @property
    def winrate(self) -> float:
        """Винрейт с этим талантом (0.0 — 1.0)."""
        return self.win_count / self.match_count if self.match_count > 0 else 0.0


@dataclass
class HeroGuideData:
    """Данные гайда героя из Stratz API: порядок прокачки и таланты."""

    hero_id: int
    match_count: int = 0
    win_count: int = 0
    ability_order: list[AbilityInfo] = field(default_factory=list)
    talents: list[TalentInfo] = field(default_factory=list)

    @property
    def winrate(self) -> float:
        """Винрейт гайда (0.0 — 1.0)."""
        return self.win_count / self.match_count if self.match_count > 0 else 0.0


@dataclass
class HeroMatchup:
    """Matchup героя с другим героем."""

    hero_id2: int
    match_count: int = 0
    win_count: int = 0
    synergy: float = 0.0

    @property
    def winrate(self) -> float:
        """Винрейт в паре (0.0 — 1.0)."""
        return self.win_count / self.match_count if self.match_count > 0 else 0.0


@dataclass
class HeroMatchupData:
    """Данные matchup-ов героя: синергии и контрпики."""

    hero_id: int
    with_heroes: list[HeroMatchup] = field(default_factory=list)
    vs_heroes: list[HeroMatchup] = field(default_factory=list)


@dataclass
class GuideItemsData:
    """Агрегированные предметы из гайд-матчей (реальные билды топ-игроков)."""

    hero_id: int
    match_count: int = 0
    item_counts: dict[int, int] = field(default_factory=dict)  # item_id -> кол-во матчей


# ---------------------------------------------------------------------------
# GraphQL запросы
# ---------------------------------------------------------------------------

QUERY_META_HEROES = """
query HeroMeta($bracketIds: [RankBracket], $positionIds: [MatchPlayerPositionType]) {
  heroStats {
    winWeek(
      take: 2
      bracketIds: $bracketIds
      positionIds: $positionIds
      gameModeIds: [ALL_PICK_RANKED]
    ) {
      heroId
      matchCount
      winCount
    }
  }
}
"""

QUERY_HERO_BUILD = """
query HeroBuild(
  $heroId: Short!
  $bracketBasicIds: [RankBracketBasicEnum]
  $positionIds: [MatchPlayerPositionType]
) {
  heroStats {
    itemStartingPurchase(
      heroId: $heroId
      bracketBasicIds: $bracketBasicIds
      positionIds: $positionIds
    ) {
      itemId
      matchCount
      winCount
      wasGiven
    }
    itemBootPurchase(
      heroId: $heroId
      bracketBasicIds: $bracketBasicIds
      positionIds: $positionIds
    ) {
      itemId
      matchCount
      winCount
    }
    itemFullPurchase(
      heroId: $heroId
      bracketBasicIds: $bracketBasicIds
      positionIds: $positionIds
      minTime: 10
    ) {
      itemId
      matchCount
      winCount
      time
    }
  }
}
"""

QUERY_HERO_GUIDE = """
query HeroGuide(
  $heroId: Short!
  $positionIds: [MatchPlayerPositionType]
  $bracketBasicIds: [RankBracketBasicEnum]
) {
  heroStats {
    talent(
      heroId: $heroId
      positionIds: $positionIds
      bracketBasicIds: $bracketBasicIds
    ) {
      abilityId
      matchCount
      winCount
      winsAverage
    }
    abilityMaxLevel(
      heroId: $heroId
      positionIds: $positionIds
      bracketBasicIds: $bracketBasicIds
    ) {
      abilityId
      level
      matchCount
      winCount
    }
  }
}
"""

QUERY_HERO_GUIDE_ITEMS = """
query HeroGuideItems(
  $heroId: Short!
  $positionId: MatchPlayerPositionType
  $take: Int
) {
  heroStats {
    guide(
      heroId: $heroId
      positionId: $positionId
      take: $take
    ) {
      heroId
      matchCount
      guides {
        matchId
        itemIds
        steamAccountId
      }
    }
  }
}
"""

QUERY_HERO_MATCHUPS = """
query HeroMatchups($heroId: Short!, $bracketBasicIds: [RankBracketBasicEnum]) {
  heroStats {
    matchUp(
      heroId: $heroId
      bracketBasicIds: $bracketBasicIds
    ) {
      heroId
      with {
        heroId2
        matchCount
        winCount
        synergy
      }
      vs {
        heroId2
        matchCount
        winCount
        synergy
      }
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Rate limiter (token bucket)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Простой token-bucket rate limiter для Stratz API."""

    def __init__(self, max_tokens: int = 20, refill_period: float = 1.0) -> None:
        self._max_tokens = max_tokens
        self._refill_period = refill_period
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Ожидает, пока не появится токен."""
        async with self._lock:
            self._refill()
            if self._tokens < 1:
                wait = self._refill_period * (1 - self._tokens) / self._max_tokens
                await asyncio.sleep(wait)
                self._refill()
            self._tokens -= 1

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(
            self._max_tokens,
            self._tokens + elapsed * (self._max_tokens / self._refill_period),
        )
        self._last_refill = now


# ---------------------------------------------------------------------------
# Клиент Stratz
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.0
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}

_GRAPHQL_URL = "https://api.stratz.com/graphql"


class StratzClient:
    """Async-клиент для Stratz GraphQL API."""

    def __init__(
        self,
        token: str,
        *,
        base_url: str = _GRAPHQL_URL,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._token = token
        self._base_url = base_url
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._session = cffi_requests.Session(impersonate="chrome")
        # Stratz лимиты: 20 запросов/сек
        self._limiter = _RateLimiter(max_tokens=20, refill_period=1.0)

    # -- публичные методы ---------------------------------------------------

    async def get_meta_heroes(
        self,
        role: Role | int,
        bracket: RankBracket | str,
    ) -> list[MetaHeroStats]:
        """Получить мета-героев по роли и ранговому брекету.

        Возвращает список MetaHeroStats с heroId, matchCount, winCount
        за последнюю неделю для ALL_PICK_RANKED.
        """
        position = ROLE_TO_STRATZ_POSITION[Role(role)]
        stratz_bracket = RANK_TO_STRATZ_BRACKET[RankBracket(bracket)]

        variables = {
            "bracketIds": [stratz_bracket],
            "positionIds": [position],
        }
        data = await self._query(QUERY_META_HEROES, variables)

        raw_list = data.get("data", {}).get("heroStats", {}).get("winWeek", [])

        # winWeek returns entries grouped by heroId; with take:2 we get
        # two entries per hero (this week index 0, last week index 1).
        by_hero: dict[int, list[dict]] = defaultdict(list)
        for item in raw_list:
            hero_id = item.get("heroId")
            if hero_id is not None:
                by_hero[hero_id].append(item)

        result: list[MetaHeroStats] = []
        for hero_id, weeks in by_hero.items():
            # First entry = most recent week
            this_week = weeks[0]
            mc = this_week.get("matchCount", 0)
            wc = this_week.get("winCount", 0)
            this_wr = wc / mc if mc > 0 else 0.0

            trend = 0.0
            if len(weeks) >= 2:
                last_week = weeks[1]
                lmc = last_week.get("matchCount", 0)
                lwc = last_week.get("winCount", 0)
                last_wr = lwc / lmc if lmc > 0 else 0.0
                trend = this_wr - last_wr

            result.append(
                MetaHeroStats(
                    hero_id=hero_id,
                    match_count=mc,
                    win_count=wc,
                    trend=trend,
                )
            )
        return result

    async def get_hero_build(
        self,
        hero_id: int,
        role: Role | int | None = None,
        bracket: RankBracket | str | None = None,
    ) -> HeroBuildData:
        """Получить item build героя по роли и брекету.

        Возвращает HeroBuildData с предметами по фазам игры:
        starting, early, mid, late.
        """
        variables: dict[str, Any] = {"heroId": hero_id}
        if bracket is not None:
            stratz_bracket = RANK_TO_STRATZ_BRACKET_BASIC[RankBracket(bracket)]
            variables["bracketBasicIds"] = [stratz_bracket]
        if role is not None:
            variables["positionIds"] = [ROLE_TO_STRATZ_POSITION[Role(role)]]

        data = await self._query(QUERY_HERO_BUILD, variables)

        hero_stats = data.get("data", {}).get("heroStats", {})
        starting_raw = hero_stats.get("itemStartingPurchase", []) or []
        boot_raw = hero_stats.get("itemBootPurchase", []) or []
        full_raw = hero_stats.get("itemFullPurchase", []) or []

        # Агрегируем full items по itemId (суммируем matchCount/winCount)
        agg: dict[int, dict[str, int]] = {}
        for item in full_raw:
            iid = item.get("itemId", 0)
            if iid not in agg:
                agg[iid] = {"itemId": iid, "matchCount": 0, "winCount": 0, "time": 0}
            agg[iid]["matchCount"] += item.get("matchCount", 0)
            agg[iid]["winCount"] += item.get("winCount", 0)

        aggregated = sorted(agg.values(), key=lambda x: x["matchCount"], reverse=True)

        return HeroBuildData(
            hero_id=hero_id,
            starting_items=self._parse_items(starting_raw),
            boot_items=self._parse_items(boot_raw),
            early_game=self._parse_items(aggregated),
            mid_game=[],
            late_game=[],
        )

    async def get_hero_guide(
        self,
        hero_id: int,
        role: Role | int | None = None,
        bracket: RankBracket | str | None = None,
    ) -> HeroGuideData:
        """Получить гайд героя: порядок прокачки скиллов и таланты.

        Использует heroStats.talent() и heroStats.abilityMaxLevel().
        Возвращает HeroGuideData с ability_order и talents.
        """
        variables: dict[str, Any] = {"heroId": hero_id}
        if role is not None:
            variables["positionIds"] = [ROLE_TO_STRATZ_POSITION[Role(role)]]
        if bracket is not None:
            stratz_bracket = RANK_TO_STRATZ_BRACKET_BASIC[RankBracket(bracket)]
            variables["bracketBasicIds"] = [stratz_bracket]

        data = await self._query(QUERY_HERO_GUIDE, variables)

        hero_stats = data.get("data", {}).get("heroStats", {})
        talent_list = hero_stats.get("talent") or []
        ability_list = hero_stats.get("abilityMaxLevel") or []

        if not talent_list and not ability_list:
            return HeroGuideData(hero_id=hero_id)

        # abilityMaxLevel: каждый элемент = {abilityId, level, matchCount, winCount}
        # level = уровень героя, на котором скиллят эту способность.
        # Строим skill build: на каждом уровне берём ability с макс matchCount.
        # Ограничиваемся уровнями 1-18 (основная прокачка).
        abilities: list[AbilityInfo] = []
        by_level: dict[int, list[dict]] = defaultdict(list)
        for ab in ability_list:
            lvl = ab.get("level", 0)
            if 1 <= lvl <= 18:
                by_level[lvl].append(ab)

        # Для каждого уровня героя: какую способность скиллят чаще всего
        for lvl in sorted(by_level.keys()):
            best = max(by_level[lvl], key=lambda x: x.get("matchCount", 0))
            # slot: определяем по позиции ability_id среди уникальных abilities
            abilities.append(
                AbilityInfo(
                    ability_id=best.get("abilityId", 0),
                    slot=best.get("abilityId", 0),  # temporary: use abilityId as slot
                )
            )

        # talent: каждый элемент = {abilityId, matchCount, winCount, winsAverage}
        total_match = 0
        total_win = 0
        talents: list[TalentInfo] = []
        for i, t in enumerate(talent_list):
            mc = t.get("matchCount", 0)
            wc = t.get("winCount", 0)
            total_match += mc
            total_win += wc
            talents.append(
                TalentInfo(
                    ability_id=t.get("abilityId", 0),
                    slot=i,
                    win_count=wc,
                    match_count=mc,
                )
            )

        return HeroGuideData(
            hero_id=hero_id,
            match_count=total_match,
            win_count=total_win,
            ability_order=abilities,
            talents=talents,
        )

    async def get_hero_guide_items(
        self,
        hero_id: int,
        role: Role | int | None = None,
        *,
        take: int = 10,
    ) -> GuideItemsData:
        """Получить предметы из гайд-матчей (реальные билды топ-игроков).

        Берёт `take` матчей из guide endpoint и агрегирует itemIds
        по частоте — предметы, встречающиеся чаще всего, считаются core.
        """
        variables: dict[str, Any] = {"heroId": hero_id, "take": take}
        if role is not None:
            variables["positionId"] = ROLE_TO_STRATZ_POSITION[Role(role)]

        data = await self._query(QUERY_HERO_GUIDE_ITEMS, variables)

        guide_list = data.get("data", {}).get("heroStats", {}).get("guide", [])
        if not guide_list:
            return GuideItemsData(hero_id=hero_id)

        entry = guide_list[0]
        guides = entry.get("guides") or []
        total_matches = len(guides)

        if total_matches == 0:
            return GuideItemsData(hero_id=hero_id, match_count=entry.get("matchCount", 0))

        item_counts: dict[int, int] = defaultdict(int)
        for g in guides:
            item_ids = g.get("itemIds") or []
            seen_in_match: set[int] = set()
            for item_id in item_ids:
                if item_id and item_id not in seen_in_match:
                    seen_in_match.add(item_id)
                    item_counts[item_id] += 1

        return GuideItemsData(
            hero_id=hero_id,
            match_count=total_matches,
            item_counts=dict(item_counts),
        )

    async def get_hero_matchups(
        self,
        hero_id: int,
        bracket: RankBracket | str | None = None,
    ) -> HeroMatchupData:
        """Получить matchup-данные героя: синергии (with) и контрпики (vs).

        Возвращает HeroMatchupData со списками HeroMatchup,
        отсортированными по synergy.
        """
        variables: dict[str, Any] = {"heroId": hero_id}
        if bracket is not None:
            stratz_bracket = RANK_TO_STRATZ_BRACKET_BASIC[RankBracket(bracket)]
            variables["bracketBasicIds"] = [stratz_bracket]

        data = await self._query(QUERY_HERO_MATCHUPS, variables)

        matchup_list = data.get("data", {}).get("heroStats", {}).get("matchUp", []) or []

        with_heroes: list[HeroMatchup] = []
        vs_heroes: list[HeroMatchup] = []

        for entry in matchup_list:
            for w in entry.get("with", []) or []:
                with_heroes.append(self._parse_matchup(w))
            for v in entry.get("vs", []) or []:
                vs_heroes.append(self._parse_matchup(v))

        # Сортируем: синергии по убыванию synergy, контрпики по возрастанию
        with_heroes.sort(key=lambda m: m.synergy, reverse=True)
        vs_heroes.sort(key=lambda m: m.synergy)

        return HeroMatchupData(
            hero_id=hero_id,
            with_heroes=with_heroes,
            vs_heroes=vs_heroes,
        )

    # -- lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        """Закрыть HTTP-клиент (только если создан внутри)."""
        if not self._external_client:
            await self._client.aclose()

    async def __aenter__(self) -> StratzClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- внутренняя логика --------------------------------------------------

    @staticmethod
    def _parse_items(raw: list[dict[str, Any]]) -> list[ItemPurchase]:
        """Разобрать список предметов из ответа Stratz."""
        result: list[ItemPurchase] = []
        for item in raw:
            item_id = item.get("itemId")
            if item_id is None:
                continue
            result.append(
                ItemPurchase(
                    item_id=item_id,
                    match_count=item.get("matchCount", 0),
                    win_count=item.get("winCount", 0),
                    time=item.get("time"),
                    was_given=item.get("wasGiven", False),
                )
            )
        # Сортируем по популярности (matchCount) по убыванию
        result.sort(key=lambda p: p.match_count, reverse=True)
        return result

    @staticmethod
    def _parse_matchup(raw: dict[str, Any]) -> HeroMatchup:
        """Разобрать один matchup из ответа Stratz."""
        return HeroMatchup(
            hero_id2=raw.get("heroId2", 0),
            match_count=raw.get("matchCount", 0),
            win_count=raw.get("winCount", 0),
            synergy=raw.get("synergy", 0.0),
        )

    def _sync_query(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Синхронный запрос через curl_cffi (обход Cloudflare)."""
        resp = self._session.post(url, json=payload, headers=headers, timeout=30)
        return {"status_code": resp.status_code, "body": resp.text, "headers": dict(resp.headers)}

    async def _query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполнить GraphQL-запрос с rate limiting и retry."""
        logger.debug("Stratz GraphQL запрос, variables=%s", variables)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_exc: Exception | None = None
        import json as json_mod

        for attempt in range(_MAX_RETRIES):
            await self._limiter.acquire()
            try:
                raw = await asyncio.to_thread(
                    self._sync_query,
                    self._base_url,
                    headers,
                    payload,
                )
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(_RETRY_BACKOFF * (2**attempt))
                continue

            status = raw["status_code"]

            if status == 429:
                retry_after = float(raw["headers"].get("retry-after", _RETRY_BACKOFF))
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(retry_after)
                    continue
                raise APIRateLimited("Stratz", retry_after=retry_after)

            if status in _RETRY_STATUS_CODES:
                last_exc = Exception(f"HTTP {status}")
                await asyncio.sleep(_RETRY_BACKOFF * (2**attempt))
                continue

            if status >= 400:
                # GraphQL APIs return 400 with JSON body on query errors
                try:
                    body = json_mod.loads(raw["body"])
                    if "errors" in body and body["errors"]:
                        errors = body["errors"]
                        msg = "; ".join(
                            e.get("message", "Неизвестная ошибка GraphQL") for e in errors
                        )
                        raise StratzGraphQLError(msg, errors=errors)
                except (ValueError, KeyError):
                    pass
                raise httpx.HTTPStatusError(
                    f"HTTP {status}: {raw['body'][:200]}",
                    request=httpx.Request("POST", self._base_url),
                    response=httpx.Response(status),
                )

            body = json_mod.loads(raw["body"])

            # Обработка ошибок GraphQL (для 200 с ошибками)
            if "errors" in body and body["errors"]:
                errors = body["errors"]
                msg = "; ".join(e.get("message", "Неизвестная ошибка GraphQL") for e in errors)
                raise StratzGraphQLError(msg, errors=errors)

            return body

        if last_exc is not None:
            raise last_exc
        msg = "Не удалось получить ответ от Stratz API"
        raise httpx.HTTPError(msg)


class StratzGraphQLError(Exception):
    """Ошибка в ответе Stratz GraphQL API."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None) -> None:
        self.errors = errors or []
        super().__init__(message)
