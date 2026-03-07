"""Клиент Steam API: валидация Steam URL/ID, проверка открытости профиля."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from core.exceptions import SteamProfileClosed
from core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------

# Разница между Steam ID 64-bit и account_id (32-bit)
_STEAM_ID_64_BASE = 76561197960265728

# Паттерны для парсинга Steam-ссылок и ID
_RE_STEAM_ID_64 = re.compile(r"^[17]\d{16}$")
_RE_ACCOUNT_ID = re.compile(r"^\d{1,10}$")
_RE_VANITY_NAME = re.compile(r"^[a-zA-Z0-9_-]{2,32}$")

# Steam Web API endpoint для resolve vanity URL
_STEAM_RESOLVE_URL = "https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def steam_id_64_to_account_id(steam_id_64: int) -> int:
    """Конвертация Steam ID 64-bit → account_id (32-bit) для OpenDota."""
    return steam_id_64 - _STEAM_ID_64_BASE


def account_id_to_steam_id_64(account_id: int) -> int:
    """Конвертация account_id (32-bit) → Steam ID 64-bit."""
    return account_id + _STEAM_ID_64_BASE


# ---------------------------------------------------------------------------
# Парсинг Steam-ввода
# ---------------------------------------------------------------------------

class _ParsedSteamInput:
    """Результат парсинга пользовательского ввода Steam ID/URL."""

    def __init__(
        self,
        *,
        steam_id_64: int | None = None,
        vanity_name: str | None = None,
    ) -> None:
        self.steam_id_64 = steam_id_64
        self.vanity_name = vanity_name


def _parse_steam_input(raw: str) -> _ParsedSteamInput:
    """Парсинг различных форматов Steam-ввода.

    Поддерживаемые форматы:
    - Числовой Steam ID 64-bit: 76561198xxxxxxxxx
    - Числовой account_id 32-bit: 12345678
    - URL: steamcommunity.com/profiles/76561198xxxxxxxxx
    - URL: steamcommunity.com/id/nickname
    - Просто vanity name: nickname
    """
    text = raw.strip().rstrip("/")

    # Попытка распарсить как URL
    if "steamcommunity.com" in text:
        # Добавим схему если нет
        if not text.startswith("http"):
            text = "https://" + text

        parsed = urlparse(text)
        parts = [p for p in parsed.path.split("/") if p]

        if len(parts) >= 2:
            kind = parts[0].lower()  # "profiles" или "id"
            value = parts[1]

            if kind == "profiles" and _RE_STEAM_ID_64.match(value):
                return _ParsedSteamInput(steam_id_64=int(value))

            if kind == "id":
                return _ParsedSteamInput(vanity_name=value)

        msg = f"Не удалось распарсить Steam URL: {raw}"
        raise ValueError(msg)

    # Числовой Steam ID 64-bit
    if _RE_STEAM_ID_64.match(text):
        return _ParsedSteamInput(steam_id_64=int(text))

    # Числовой account_id (32-bit) — конвертируем в 64-bit
    if _RE_ACCOUNT_ID.match(text):
        account_id = int(text)
        if account_id > 0:
            return _ParsedSteamInput(steam_id_64=account_id_to_steam_id_64(account_id))

    # Vanity name
    if _RE_VANITY_NAME.match(text):
        return _ParsedSteamInput(vanity_name=text)

    msg = f"Некорректный формат Steam ID: {raw}"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Клиент Steam
# ---------------------------------------------------------------------------

class SteamClient:
    """Клиент для валидации Steam ID/URL и проверки открытости профиля.

    Для resolve vanity URL использует Steam Web API (требует STEAM_API_KEY).
    Для проверки открытости профиля использует OpenDota API.
    """

    def __init__(
        self,
        steam_api_key: str | None = None,
        opendota_base_url: str = "https://api.opendota.com/api",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._steam_api_key = steam_api_key
        self._opendota_base_url = opendota_base_url.rstrip("/")
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(timeout=30.0)

    async def resolve_steam_id(self, raw_input: str) -> int:
        """Распарсить пользовательский ввод и вернуть Steam ID 64-bit.

        Поддержка форматов:
        - steamcommunity.com/id/nickname
        - steamcommunity.com/profiles/76561198xxxxxxxxx
        - Числовой Steam ID 64-bit
        - Числовой account_id 32-bit
        - Vanity name (nickname)

        Raises:
            ValueError: Некорректный формат ввода.
            httpx.HTTPStatusError: Ошибка Steam API.
        """
        parsed = _parse_steam_input(raw_input)

        if parsed.steam_id_64 is not None:
            return parsed.steam_id_64

        # Нужен resolve vanity name через Steam Web API
        if parsed.vanity_name is not None:
            return await self._resolve_vanity_url(parsed.vanity_name)

        msg = f"Не удалось определить Steam ID из ввода: {raw_input}"
        raise ValueError(msg)

    async def check_profile_open(self, steam_id_64: int) -> bool:
        """Проверить открытость профиля через OpenDota API.

        Возвращает True если профиль открыт (есть данные в OpenDota).

        Raises:
            SteamProfileClosed: Профиль закрыт или данные недоступны.
        """
        account_id = steam_id_64_to_account_id(steam_id_64)
        url = f"{self._opendota_base_url}/players/{account_id}"

        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        # OpenDota возвращает объект с profile=null если профиль закрыт
        profile = data.get("profile")
        if not profile or not profile.get("personaname"):
            raise SteamProfileClosed(str(steam_id_64))

        return True

    async def get_persona_name(self, steam_id_64: int) -> str | None:
        """Получить никнейм игрока из OpenDota."""
        account_id = steam_id_64_to_account_id(steam_id_64)
        url = f"{self._opendota_base_url}/players/{account_id}"

        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        profile = data.get("profile")
        if profile:
            return profile.get("personaname")
        return None

    async def resolve_and_validate(self, raw_input: str) -> tuple[int, str]:
        """Полный flow: парсинг ввода → resolve → проверка открытости → никнейм.

        Возвращает (steam_id_64, persona_name).

        Raises:
            ValueError: Некорректный формат ввода.
            SteamProfileClosed: Профиль закрыт.
        """
        steam_id_64 = await self.resolve_steam_id(raw_input)

        # Проверяем открытость и получаем никнейм за один запрос
        account_id = steam_id_64_to_account_id(steam_id_64)
        url = f"{self._opendota_base_url}/players/{account_id}"

        resp = await self._client.get(url)
        resp.raise_for_status()
        data = resp.json()

        profile = data.get("profile")
        if not profile or not profile.get("personaname"):
            raise SteamProfileClosed(str(steam_id_64))

        persona_name = profile["personaname"]
        return steam_id_64, persona_name

    # -- lifecycle ----------------------------------------------------------

    async def close(self) -> None:
        """Закрыть HTTP-клиент (только если создан внутри)."""
        if not self._external_client:
            await self._client.aclose()

    async def __aenter__(self) -> SteamClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    # -- приватные методы ---------------------------------------------------

    async def _resolve_vanity_url(self, vanity_name: str) -> int:
        """Resolve vanity name через Steam Web API."""
        if not self._steam_api_key:
            msg = (
                "Для resolve vanity URL необходим STEAM_API_KEY. "
                "Укажите числовой Steam ID или ссылку формата "
                "steamcommunity.com/profiles/..."
            )
            raise ValueError(msg)

        resp = await self._client.get(
            _STEAM_RESOLVE_URL,
            params={"key": self._steam_api_key, "vanityurl": vanity_name},
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("response", {})
        if result.get("success") != 1:
            msg = f"Не удалось найти Steam-профиль по имени: {vanity_name}"
            raise ValueError(msg)

        steam_id_str = result.get("steamid", "")
        if not steam_id_str:
            msg = f"Steam API не вернул steamid для: {vanity_name}"
            raise ValueError(msg)

        return int(steam_id_str)
