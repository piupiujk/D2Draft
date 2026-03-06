"""Тесты для core/validators.py — валидация входных данных."""

from core.validators import (
    MSG_HERO_QUERY_BAD_CHARS,
    MSG_HERO_QUERY_EMPTY,
    MSG_HERO_QUERY_TOO_LONG,
    MSG_IMAGE_TOO_LARGE,
    MSG_MMR_INVALID,
    MSG_STEAM_INPUT_EMPTY,
    MSG_STEAM_INPUT_TOO_LONG,
    validate_hero_query,
    validate_image_size,
    validate_mmr,
    validate_steam_input,
)

# ---------------------------------------------------------------------------
# validate_mmr
# ---------------------------------------------------------------------------


class TestValidateMmr:
    def test_valid_zero(self):
        val, err = validate_mmr("0")
        assert val == 0
        assert err is None

    def test_valid_max(self):
        val, err = validate_mmr("15000")
        assert val == 15000
        assert err is None

    def test_valid_middle(self):
        val, err = validate_mmr("  3500  ")
        assert val == 3500
        assert err is None

    def test_negative(self):
        val, err = validate_mmr("-100")
        assert val is None
        assert err == MSG_MMR_INVALID

    def test_too_high(self):
        val, err = validate_mmr("20000")
        assert val is None
        assert err == MSG_MMR_INVALID

    def test_not_a_number(self):
        val, err = validate_mmr("abc")
        assert val is None
        assert err == MSG_MMR_INVALID

    def test_empty(self):
        val, err = validate_mmr("")
        assert val is None
        assert err == MSG_MMR_INVALID

    def test_float(self):
        val, err = validate_mmr("3500.5")
        assert val is None
        assert err == MSG_MMR_INVALID

    def test_sql_injection(self):
        val, err = validate_mmr("1; DROP TABLE users;")
        assert val is None
        assert err == MSG_MMR_INVALID


# ---------------------------------------------------------------------------
# validate_hero_query
# ---------------------------------------------------------------------------


class TestValidateHeroQuery:
    def test_valid_english(self):
        val, err = validate_hero_query("Anti-Mage")
        assert val == "Anti-Mage"
        assert err is None

    def test_valid_russian(self):
        val, err = validate_hero_query("Антимаг")
        assert val == "Антимаг"
        assert err is None

    def test_valid_abbreviation(self):
        val, err = validate_hero_query("am")
        assert val == "am"
        assert err is None

    def test_valid_with_apostrophe(self):
        val, err = validate_hero_query("Nature's Prophet")
        assert val == "Nature's Prophet"
        assert err is None

    def test_empty(self):
        val, err = validate_hero_query("")
        assert val is None
        assert err == MSG_HERO_QUERY_EMPTY

    def test_whitespace_only(self):
        val, err = validate_hero_query("   ")
        assert val is None
        assert err == MSG_HERO_QUERY_EMPTY

    def test_too_long(self):
        val, err = validate_hero_query("a" * 51)
        assert val is None
        assert err == MSG_HERO_QUERY_TOO_LONG

    def test_special_chars(self):
        val, err = validate_hero_query("<script>alert(1)</script>")
        assert val is None
        assert err == MSG_HERO_QUERY_BAD_CHARS

    def test_sql_injection(self):
        val, err = validate_hero_query("'; DROP TABLE users; --")
        assert val is None
        assert err == MSG_HERO_QUERY_BAD_CHARS

    def test_strips_whitespace(self):
        val, err = validate_hero_query("  Invoker  ")
        assert val == "Invoker"
        assert err is None


# ---------------------------------------------------------------------------
# validate_steam_input
# ---------------------------------------------------------------------------


class TestValidateSteamInput:
    def test_valid_id(self):
        val, err = validate_steam_input("76561198000000000")
        assert val == "76561198000000000"
        assert err is None

    def test_valid_url(self):
        val, err = validate_steam_input("https://steamcommunity.com/id/nickname")
        assert val == "https://steamcommunity.com/id/nickname"
        assert err is None

    def test_empty(self):
        val, err = validate_steam_input("")
        assert val is None
        assert err == MSG_STEAM_INPUT_EMPTY

    def test_whitespace(self):
        val, err = validate_steam_input("   ")
        assert val is None
        assert err == MSG_STEAM_INPUT_EMPTY

    def test_too_long(self):
        val, err = validate_steam_input("a" * 201)
        assert val is None
        assert err == MSG_STEAM_INPUT_TOO_LONG


# ---------------------------------------------------------------------------
# validate_image_size
# ---------------------------------------------------------------------------


class TestValidateImageSize:
    def test_valid_small(self):
        assert validate_image_size(1024) is None

    def test_valid_at_limit(self):
        assert validate_image_size(10 * 1024 * 1024) is None

    def test_too_large(self):
        assert validate_image_size(10 * 1024 * 1024 + 1) == MSG_IMAGE_TOO_LARGE

    def test_none_size(self):
        assert validate_image_size(None) is None
