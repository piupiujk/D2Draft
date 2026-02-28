"""Тесты для clients/steam.py — SteamClient."""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx

from clients.steam import (
    SteamClient,
    _parse_steam_input,
    account_id_to_steam_id_64,
    steam_id_64_to_account_id,
)
from core.exceptions import SteamProfileClosed

# ---------------------------------------------------------------------------
# Хелперы
# ---------------------------------------------------------------------------

_STEAM_ID_64_BASE = 76561197960265728
_TEST_STEAM_ID_64 = 76561198047104768
_TEST_ACCOUNT_ID = _TEST_STEAM_ID_64 - _STEAM_ID_64_BASE


def _json_response(data: object, status_code: int = 200) -> httpx.Response:
    """Создать мок-ответ httpx."""
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(data).encode(),
        headers={"content-type": "application/json"},
        request=httpx.Request("GET", "https://example.com/test"),
    )


_OPEN_PROFILE_RESPONSE = {
    "profile": {
        "personaname": "Dendi",
        "steamid": str(_TEST_STEAM_ID_64),
        "avatar": "https://avatar.example.com/small.jpg",
    },
    "rank_tier": 80,
    "mmr_estimate": {"estimate": 6500},
}

_CLOSED_PROFILE_RESPONSE: dict = {
    "profile": None,
    "rank_tier": None,
    "mmr_estimate": None,
}

_VANITY_RESOLVE_SUCCESS = {
    "response": {
        "success": 1,
        "steamid": str(_TEST_STEAM_ID_64),
    }
}

_VANITY_RESOLVE_FAIL = {
    "response": {
        "success": 42,
        "message": "No match",
    }
}


# ---------------------------------------------------------------------------
# Тесты конвертации ID
# ---------------------------------------------------------------------------

class TestSteamIdConversion:
    def test_64_to_account_id(self):
        assert steam_id_64_to_account_id(_TEST_STEAM_ID_64) == _TEST_ACCOUNT_ID

    def test_account_id_to_64(self):
        assert account_id_to_steam_id_64(_TEST_ACCOUNT_ID) == _TEST_STEAM_ID_64

    def test_roundtrip(self):
        aid = steam_id_64_to_account_id(_TEST_STEAM_ID_64)
        assert account_id_to_steam_id_64(aid) == _TEST_STEAM_ID_64


# ---------------------------------------------------------------------------
# Тесты парсинга ввода
# ---------------------------------------------------------------------------

class TestParseSteamInput:
    def test_steam_id_64_numeric(self):
        result = _parse_steam_input(str(_TEST_STEAM_ID_64))
        assert result.steam_id_64 == _TEST_STEAM_ID_64
        assert result.vanity_name is None

    def test_account_id_numeric(self):
        result = _parse_steam_input(str(_TEST_ACCOUNT_ID))
        assert result.steam_id_64 == account_id_to_steam_id_64(_TEST_ACCOUNT_ID)

    def test_profiles_url(self):
        url = f"https://steamcommunity.com/profiles/{_TEST_STEAM_ID_64}"
        result = _parse_steam_input(url)
        assert result.steam_id_64 == _TEST_STEAM_ID_64

    def test_profiles_url_no_scheme(self):
        url = f"steamcommunity.com/profiles/{_TEST_STEAM_ID_64}"
        result = _parse_steam_input(url)
        assert result.steam_id_64 == _TEST_STEAM_ID_64

    def test_profiles_url_trailing_slash(self):
        url = f"https://steamcommunity.com/profiles/{_TEST_STEAM_ID_64}/"
        result = _parse_steam_input(url)
        assert result.steam_id_64 == _TEST_STEAM_ID_64

    def test_id_url(self):
        url = "https://steamcommunity.com/id/dendi"
        result = _parse_steam_input(url)
        assert result.vanity_name == "dendi"
        assert result.steam_id_64 is None

    def test_id_url_no_scheme(self):
        url = "steamcommunity.com/id/ProPlayer123"
        result = _parse_steam_input(url)
        assert result.vanity_name == "ProPlayer123"

    def test_vanity_name_plain(self):
        result = _parse_steam_input("dendi")
        assert result.vanity_name == "dendi"

    def test_invalid_url_raises(self):
        try:
            _parse_steam_input("https://steamcommunity.com/")
            assert False, "Должен был бросить ValueError"
        except ValueError:
            pass

    def test_empty_input_raises(self):
        try:
            _parse_steam_input("   ")
            assert False, "Должен был бросить ValueError"
        except ValueError:
            pass

    def test_special_chars_raises(self):
        try:
            _parse_steam_input("user@#$%!")
            assert False, "Должен был бросить ValueError"
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Тесты SteamClient — resolve_steam_id
# ---------------------------------------------------------------------------

class TestResolveSteamId:
    def test_resolve_profiles_url(self):
        """URL формата /profiles/xxx возвращает steam_id_64 без API вызовов."""
        client = SteamClient(client=AsyncMock())
        url = f"https://steamcommunity.com/profiles/{_TEST_STEAM_ID_64}"
        result = asyncio.run(client.resolve_steam_id(url))
        assert result == _TEST_STEAM_ID_64

    def test_resolve_numeric_steam_id(self):
        """Числовой Steam ID 64-bit возвращается напрямую."""
        client = SteamClient(client=AsyncMock())
        result = asyncio.run(client.resolve_steam_id(str(_TEST_STEAM_ID_64)))
        assert result == _TEST_STEAM_ID_64

    def test_resolve_vanity_url_success(self):
        """Vanity URL resolve через Steam Web API."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_VANITY_RESOLVE_SUCCESS))

        client = SteamClient(steam_api_key="test_key", client=mock_client)
        result = asyncio.run(client.resolve_steam_id("https://steamcommunity.com/id/dendi"))
        assert result == _TEST_STEAM_ID_64

    def test_resolve_vanity_name_success(self):
        """Vanity name (не URL) resolve через Steam Web API."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_VANITY_RESOLVE_SUCCESS))

        client = SteamClient(steam_api_key="test_key", client=mock_client)
        result = asyncio.run(client.resolve_steam_id("dendi"))
        assert result == _TEST_STEAM_ID_64

    def test_resolve_vanity_no_api_key_raises(self):
        """Vanity URL без STEAM_API_KEY бросает ValueError."""
        client = SteamClient(steam_api_key=None, client=AsyncMock())
        try:
            asyncio.run(client.resolve_steam_id("https://steamcommunity.com/id/dendi"))
            assert False, "Должен был бросить ValueError"
        except ValueError as e:
            assert "STEAM_API_KEY" in str(e)

    def test_resolve_vanity_not_found_raises(self):
        """Vanity URL не найден — ValueError."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_VANITY_RESOLVE_FAIL))

        client = SteamClient(steam_api_key="test_key", client=mock_client)
        try:
            asyncio.run(client.resolve_steam_id("https://steamcommunity.com/id/nonexistent"))
            assert False, "Должен был бросить ValueError"
        except ValueError:
            pass


# ---------------------------------------------------------------------------
# Тесты SteamClient — check_profile_open
# ---------------------------------------------------------------------------

class TestCheckProfileOpen:
    def test_open_profile_returns_true(self):
        """Открытый профиль возвращает True."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_OPEN_PROFILE_RESPONSE))

        client = SteamClient(client=mock_client)
        result = asyncio.run(client.check_profile_open(_TEST_STEAM_ID_64))
        assert result is True

    def test_closed_profile_raises(self):
        """Закрытый профиль бросает SteamProfileClosed."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_CLOSED_PROFILE_RESPONSE))

        client = SteamClient(client=mock_client)
        try:
            asyncio.run(client.check_profile_open(_TEST_STEAM_ID_64))
            assert False, "Должен был бросить SteamProfileClosed"
        except SteamProfileClosed as e:
            assert str(_TEST_STEAM_ID_64) in str(e)

    def test_empty_personaname_raises(self):
        """Профиль с пустым personaname — SteamProfileClosed."""
        response = {"profile": {"personaname": ""}, "rank_tier": None}
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(response))

        client = SteamClient(client=mock_client)
        try:
            asyncio.run(client.check_profile_open(_TEST_STEAM_ID_64))
            assert False, "Должен был бросить SteamProfileClosed"
        except SteamProfileClosed:
            pass


# ---------------------------------------------------------------------------
# Тесты SteamClient — resolve_and_validate
# ---------------------------------------------------------------------------

class TestResolveAndValidate:
    def test_full_flow_profiles_url(self):
        """Полный flow: /profiles/xxx → проверка → никнейм."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_OPEN_PROFILE_RESPONSE))

        client = SteamClient(client=mock_client)
        url = f"https://steamcommunity.com/profiles/{_TEST_STEAM_ID_64}"
        steam_id, name = asyncio.run(client.resolve_and_validate(url))
        assert steam_id == _TEST_STEAM_ID_64
        assert name == "Dendi"

    def test_full_flow_vanity_url(self):
        """Полный flow: /id/xxx → resolve → проверка → никнейм."""
        mock_client = AsyncMock()
        # Первый вызов — resolve vanity, второй — OpenDota profile
        mock_client.get = AsyncMock(side_effect=[
            _json_response(_VANITY_RESOLVE_SUCCESS),
            _json_response(_OPEN_PROFILE_RESPONSE),
        ])

        client = SteamClient(steam_api_key="test_key", client=mock_client)
        steam_id, name = asyncio.run(
            client.resolve_and_validate("https://steamcommunity.com/id/dendi")
        )
        assert steam_id == _TEST_STEAM_ID_64
        assert name == "Dendi"

    def test_full_flow_closed_profile_raises(self):
        """Полный flow с закрытым профилем → SteamProfileClosed."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_CLOSED_PROFILE_RESPONSE))

        client = SteamClient(client=mock_client)
        url = f"https://steamcommunity.com/profiles/{_TEST_STEAM_ID_64}"
        try:
            asyncio.run(client.resolve_and_validate(url))
            assert False, "Должен был бросить SteamProfileClosed"
        except SteamProfileClosed:
            pass


# ---------------------------------------------------------------------------
# Тесты SteamClient — get_persona_name
# ---------------------------------------------------------------------------

class TestGetPersonaName:
    def test_returns_name(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_OPEN_PROFILE_RESPONSE))

        client = SteamClient(client=mock_client)
        name = asyncio.run(client.get_persona_name(_TEST_STEAM_ID_64))
        assert name == "Dendi"

    def test_returns_none_for_closed(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_json_response(_CLOSED_PROFILE_RESPONSE))

        client = SteamClient(client=mock_client)
        name = asyncio.run(client.get_persona_name(_TEST_STEAM_ID_64))
        assert name is None


# ---------------------------------------------------------------------------
# Тесты SteamClient — context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_aenter_returns_self(self):
        client = SteamClient(client=AsyncMock())
        result = asyncio.run(client.__aenter__())
        assert result is client

    def test_close_internal_client(self):
        """close() закрывает внутренний клиент."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        # Создаём с client=None, чтобы флаг _external_client = False
        client = SteamClient()
        client._client = mock_client
        asyncio.run(client.close())
        mock_client.aclose.assert_called_once()

    def test_close_external_client_no_op(self):
        """close() не закрывает внешний клиент."""
        mock_client = AsyncMock()
        mock_client.aclose = AsyncMock()
        client = SteamClient(client=mock_client)
        asyncio.run(client.close())
        mock_client.aclose.assert_not_called()
