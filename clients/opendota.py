"""HTTP-клиент OpenDota API: профиль игрока, матчи, статистика героев."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from core.exceptions import APIRateLimited
from core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Модели ответов
# ---------------------------------------------------------------------------

@dataclass
class PlayerProfile:
    """Профиль игрока из /players/{account_id}."""

    account_id: int
    personaname: str | None = None
    steamid: str | None = None
    avatar: str | None = None
    avatarfull: str | None = None
    rank_tier: int | None = None
    leaderboard_rank: int | None = None
    mmr_estimate: int | None = None


@dataclass
class RecentMatch:
    """Недавний матч из /players/{account_id}/recentMatches."""

    match_id: int
    hero_id: int
    player_slot: int
    radiant_win: bool
    duration: int
    game_mode: int
    lobby_type: int
    start_time: int
    kills: int = 0
    deaths: int = 0
    assists: int = 0
    xp_per_min: int = 0
    gold_per_min: int = 0
    hero_damage: int = 0
    tower_damage: int = 0
    hero_healing: int = 0
    last_hits: int = 0
    lane: int | None = None
    lane_role: int | None = None

    @property
    def is_win(self) -> bool:
        """Выиграл ли игрок этот матч."""
        is_radiant = self.player_slot < 128
        return is_radiant == self.radiant_win


@dataclass
class PlayerHeroStats:
    """Статистика героя из /players/{account_id}/heroes."""

    hero_id: int
    games: int = 0
    win: int = 0
    last_played: int = 0

    @property
    def winrate(self) -> float:
        """Винрейт на герое (0.0 — 1.0)."""
        return self.win / self.games if self.games > 0 else 0.0


@dataclass
class MatchDetails:
    """Детали матча из /matches/{match_id}."""

    match_id: int
    radiant_win: bool
    duration: int
    start_time: int
    game_mode: int
    lobby_type: int
    radiant_score: int = 0
    dire_score: int = 0
    players: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rate limiter (token bucket, 60 запросов в минуту)
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Простой token-bucket rate limiter."""

    def __init__(self, max_tokens: int = 60, refill_period: float = 60.0) -> None:
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
# Клиент OpenDota
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_BACKOFF = 1.0  # секунды (базовый множитель)
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class OpenDotaClient:
    """Async-клиент для OpenDota REST API."""

    def __init__(
        self,
        base_url: str = "https://api.opendota.com/api",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._limiter = _RateLimiter(max_tokens=60, refill_period=60.0)

    # -- публичные методы ---------------------------------------------------

    async def get_player(self, account_id: int) -> PlayerProfile:
        """Получить профиль игрока по account_id (32-bit)."""
        data = await self._get(f"/players/{account_id}")
        profile = data.get("profile", {})
        return PlayerProfile(
            account_id=account_id,
            personaname=profile.get("personaname"),
            steamid=profile.get("steamid"),
            avatar=profile.get("avatar"),
            avatarfull=profile.get("avatarfull"),
            rank_tier=data.get("rank_tier"),
            leaderboard_rank=data.get("leaderboard_rank"),
            mmr_estimate=(data.get("mmr_estimate") or {}).get("estimate"),
        )

    async def get_recent_matches(
        self, account_id: int, limit: int = 20
    ) -> list[RecentMatch]:
        """Получить последние матчи игрока."""
        data = await self._get(f"/players/{account_id}/recentMatches")
        matches: list[RecentMatch] = []
        for m in data[:limit]:
            matches.append(
                RecentMatch(
                    match_id=m["match_id"],
                    hero_id=m["hero_id"],
                    player_slot=m["player_slot"],
                    radiant_win=m.get("radiant_win", False),
                    duration=m.get("duration", 0),
                    game_mode=m.get("game_mode", 0),
                    lobby_type=m.get("lobby_type", 0),
                    start_time=m.get("start_time", 0),
                    kills=m.get("kills", 0),
                    deaths=m.get("deaths", 0),
                    assists=m.get("assists", 0),
                    xp_per_min=m.get("xp_per_min", 0),
                    gold_per_min=m.get("gold_per_min", 0),
                    hero_damage=m.get("hero_damage", 0),
                    tower_damage=m.get("tower_damage", 0),
                    hero_healing=m.get("hero_healing", 0),
                    last_hits=m.get("last_hits", 0),
                    lane=m.get("lane"),
                    lane_role=m.get("lane_role"),
                )
            )
        return matches

    async def get_player_heroes(self, account_id: int) -> list[PlayerHeroStats]:
        """Получить статистику героев игрока."""
        data = await self._get(f"/players/{account_id}/heroes")
        heroes: list[PlayerHeroStats] = []
        for h in data:
            hero_id = int(h.get("hero_id", 0))
            if hero_id == 0:
                continue
            heroes.append(
                PlayerHeroStats(
                    hero_id=hero_id,
                    games=int(h.get("games", 0)),
                    win=int(h.get("win", 0)),
                    last_played=int(h.get("last_played", 0)),
                )
            )
        return heroes

    async def get_match(self, match_id: int) -> MatchDetails:
        """Получить детали матча по match_id."""
        data = await self._get(f"/matches/{match_id}")
        return MatchDetails(
            match_id=data["match_id"],
            radiant_win=data.get("radiant_win", False),
            duration=data.get("duration", 0),
            start_time=data.get("start_time", 0),
            game_mode=data.get("game_mode", 0),
            lobby_type=data.get("lobby_type", 0),
            radiant_score=data.get("radiant_score", 0),
            dire_score=data.get("dire_score", 0),
            players=data.get("players", []),
        )

    # -- lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        """Закрыть HTTP-клиент (только если создан внутри)."""
        if not self._external_client:
            await self._client.aclose()

    async def __aenter__(self) -> OpenDotaClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- внутренняя логика --------------------------------------------------

    async def _get(self, path: str) -> Any:
        """GET-запрос с rate limiting и retry."""
        url = f"{self._base_url}{path}"
        logger.debug("OpenDota GET %s", path)
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            await self._limiter.acquire()
            try:
                resp = await self._client.get(url)
            except httpx.HTTPError as exc:
                last_exc = exc
                await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("retry-after", _RETRY_BACKOFF))
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(retry_after)
                    continue
                raise APIRateLimited("OpenDota", retry_after=retry_after)

            if resp.status_code in _RETRY_STATUS_CODES:
                last_exc = httpx.HTTPStatusError(
                    f"HTTP {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
                await asyncio.sleep(_RETRY_BACKOFF * (2 ** attempt))
                continue

            resp.raise_for_status()
            return resp.json()

        if last_exc is not None:
            raise last_exc
        msg = f"Не удалось получить ответ от OpenDota: {url}"
        raise httpx.HTTPError(msg)
