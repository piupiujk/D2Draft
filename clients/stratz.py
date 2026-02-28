"""HTTP-клиент Stratz GraphQL API: мета-герои, билды, matchups."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.enums import RankBracket, Role
from core.exceptions import APIRateLimited

# ---------------------------------------------------------------------------
# Маппинг enum-ов проекта -> Stratz API
# ---------------------------------------------------------------------------

# Stratz использует сгруппированные брекеты по два ранга
RANK_TO_STRATZ_BRACKET: dict[RankBracket, str] = {
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
    early_game: list[ItemPurchase] = field(default_factory=list)
    mid_game: list[ItemPurchase] = field(default_factory=list)
    late_game: list[ItemPurchase] = field(default_factory=list)


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


# ---------------------------------------------------------------------------
# GraphQL запросы
# ---------------------------------------------------------------------------

QUERY_META_HEROES = """
query HeroMeta($bracketIds: [RankBracketBasicEnum], $positionIds: [MatchPlayerPositionType]) {
  heroStats {
    winWeek(
      take: 1
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
  $positionId: MatchPlayerPositionType
) {
  heroStats {
    stats(
      heroIds: [$heroId]
      bracketBasicIds: $bracketBasicIds
      positionIds: [$positionId]
      gameModeIds: [ALL_PICK_RANKED]
    ) {
      heroId
      matchCount
      winCount
      purchasePattern {
        startingItems {
          itemId
          matchCount
          winCount
          wasGiven
        }
        earlyGame {
          itemId
          matchCount
          winCount
          time
        }
        midGame {
          itemId
          matchCount
          winCount
          time
        }
        lateGame {
          itemId
          matchCount
          winCount
          time
        }
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
      advantage {
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

        raw_list = (
            data.get("data", {})
            .get("heroStats", {})
            .get("winWeek", [])
        )
        result: list[MetaHeroStats] = []
        for item in raw_list:
            hero_id = item.get("heroId")
            if hero_id is None:
                continue
            result.append(
                MetaHeroStats(
                    hero_id=hero_id,
                    match_count=item.get("matchCount", 0),
                    win_count=item.get("winCount", 0),
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
            stratz_bracket = RANK_TO_STRATZ_BRACKET[RankBracket(bracket)]
            variables["bracketBasicIds"] = [stratz_bracket]
        if role is not None:
            variables["positionId"] = ROLE_TO_STRATZ_POSITION[Role(role)]

        data = await self._query(QUERY_HERO_BUILD, variables)

        stats_list = (
            data.get("data", {})
            .get("heroStats", {})
            .get("stats", [])
        )
        if not stats_list:
            return HeroBuildData(hero_id=hero_id)

        stats = stats_list[0]
        pattern = stats.get("purchasePattern") or {}

        return HeroBuildData(
            hero_id=hero_id,
            starting_items=self._parse_items(pattern.get("startingItems", [])),
            early_game=self._parse_items(pattern.get("earlyGame", [])),
            mid_game=self._parse_items(pattern.get("midGame", [])),
            late_game=self._parse_items(pattern.get("lateGame", [])),
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
            stratz_bracket = RANK_TO_STRATZ_BRACKET[RankBracket(bracket)]
            variables["bracketBasicIds"] = [stratz_bracket]

        data = await self._query(QUERY_HERO_MATCHUPS, variables)

        matchup_data = (
            data.get("data", {})
            .get("heroStats", {})
            .get("matchUp", {})
        )
        advantage_list = matchup_data.get("advantage", [])

        with_heroes: list[HeroMatchup] = []
        vs_heroes: list[HeroMatchup] = []

        for adv in advantage_list:
            for w in adv.get("with", []) or []:
                with_heroes.append(self._parse_matchup(w))
            for v in adv.get("vs", []) or []:
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

    async def _query(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполнить GraphQL-запрос с rate limiting и retry."""
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            await self._limiter.acquire()
            try:
                resp = await self._client.post(
                    self._base_url, json=payload, headers=headers,
                )
            except httpx.HTTPError as exc:
                last_exc = exc
                await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue

            if resp.status_code == 429:
                retry_after = float(
                    resp.headers.get("retry-after", _RETRY_BACKOFF)
                )
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(retry_after)
                    continue
                raise APIRateLimited("Stratz", retry_after=retry_after)

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue

            resp.raise_for_status()
            body = resp.json()

            # Обработка ошибок GraphQL
            if "errors" in body and body["errors"]:
                errors = body["errors"]
                msg = "; ".join(
                    e.get("message", "Неизвестная ошибка GraphQL")
                    for e in errors
                )
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
