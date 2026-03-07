"""Тесты для services/draft.py — распознавание драфта и рекомендация пиков."""

from unittest.mock import AsyncMock, patch

from clients.llm import DraftRecognition, LLMClient, PickRecommendation
from clients.stratz import HeroMatchup, HeroMatchupData, MetaHeroStats, StratzClient
from core.enums import RankBracket, Role
from services.draft import (
    ValidatedDraft,
    _basic_reason,
    _Candidate,
    _validate_recognition,
    recognize_draft,
    recommend_picks,
)

# ---------------------------------------------------------------------------
# _validate_recognition
# ---------------------------------------------------------------------------


class TestValidateRecognition:
    def test_valid_full_draft(self):
        """Полный драфт с валидными hero_id."""
        rec = DraftRecognition(
            allies=[1, 14, 22, 86, 30],
            enemies=[8, 97, 39, 50, 26],
            user_role=1,
            confidence=0.95,
            raw_response="allies:1,14,22,86,30|enemies:8,97,39,50,26|role:1|confidence:0.95",
        )
        result = _validate_recognition(rec)

        assert result.allies == [1, 14, 22, 86, 30]
        assert result.enemies == [8, 97, 39, 50, 26]
        assert result.user_role == 1
        assert result.confidence == 0.95
        assert not result.needs_confirmation
        assert len(result.allies_names) == 5
        assert len(result.enemies_names) == 5
        assert result.allies_names[0] == "Анти-Маг"

    def test_partial_draft(self):
        """Неполный драфт (3 vs 2)."""
        rec = DraftRecognition(
            allies=[44, 5, 29],
            enemies=[74, 87],
            user_role=0,
            confidence=0.8,
            raw_response="allies:44,5,29|enemies:74,87|role:0|confidence:0.8",
        )
        result = _validate_recognition(rec)

        assert len(result.allies) == 3
        assert len(result.enemies) == 2
        assert result.user_role is None  # role=0 -> None
        assert result.confidence == 0.8
        assert not result.needs_confirmation

    def test_invalid_hero_ids(self):
        """Невалидные hero_id отфильтровываются, уверенность снижается."""
        rec = DraftRecognition(
            allies=[1, 9999],  # 9999 невалидный
            enemies=[8, 7777],  # 7777 невалидный
            confidence=0.9,
            raw_response="allies:1,9999|enemies:8,7777|role:0|confidence:0.9",
        )
        result = _validate_recognition(rec)

        assert result.allies == [1]
        assert result.enemies == [8]
        assert result.invalid_ids == [9999, 7777]
        # Уверенность пересчитана: 0.9 * (2/4) = 0.45
        assert abs(result.confidence - 0.45) < 0.01
        assert result.needs_confirmation  # < порога

    def test_empty_draft(self):
        """Пустой драфт — confidence=0, needs_confirmation."""
        rec = DraftRecognition(
            allies=[],
            enemies=[],
            confidence=0.0,
            raw_response="allies:|enemies:|role:0|confidence:0.0",
        )
        result = _validate_recognition(rec)

        assert result.allies == []
        assert result.enemies == []
        assert result.confidence == 0.0
        assert result.needs_confirmation

    def test_low_confidence_triggers_confirmation(self):
        """confidence < порога -> needs_confirmation=True."""
        rec = DraftRecognition(
            allies=[1],
            enemies=[8],
            confidence=0.5,
            raw_response="allies:1|enemies:8|role:0|confidence:0.5",
        )
        result = _validate_recognition(rec)

        assert result.needs_confirmation

    def test_parser_needs_confirmation_propagated(self):
        """needs_confirmation от парсера сохраняется."""
        rec = DraftRecognition(
            allies=[1, 2],
            enemies=[3, 4],
            confidence=0.9,
            needs_confirmation=True,
            raw_response="test",
        )
        result = _validate_recognition(rec)

        assert result.needs_confirmation

    def test_role_zero_becomes_none(self):
        """user_role=0 преобразуется в None."""
        rec = DraftRecognition(
            allies=[1],
            enemies=[2],
            user_role=0,
            confidence=0.8,
            raw_response="test",
        )
        result = _validate_recognition(rec)

        assert result.user_role is None


# ---------------------------------------------------------------------------
# recognize_draft (интеграция с LLMClient)
# ---------------------------------------------------------------------------


class TestRecognizeDraft:
    async def test_calls_llm_and_validates(self):
        """recognize_draft вызывает llm_client.recognize_draft и валидирует."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recognize_draft.return_value = DraftRecognition(
            allies=[1, 14, 22],
            enemies=[8, 97],
            user_role=2,
            confidence=0.85,
            raw_response="allies:1,14,22|enemies:8,97|role:2|confidence:0.85",
        )

        result = await recognize_draft(b"fake_image_data", mock_llm)

        mock_llm.recognize_draft.assert_awaited_once_with(b"fake_image_data")
        assert isinstance(result, ValidatedDraft)
        assert result.allies == [1, 14, 22]
        assert result.enemies == [8, 97]
        assert result.user_role == 2
        assert not result.needs_confirmation

    async def test_blurry_image_low_confidence(self):
        """Размытое изображение — низкая уверенность, needs_confirmation."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recognize_draft.return_value = DraftRecognition(
            allies=[1],
            enemies=[],
            user_role=0,
            confidence=0.3,
            raw_response="allies:1|enemies:|role:0|confidence:0.3",
        )

        result = await recognize_draft(b"blurry_image", mock_llm)

        assert result.needs_confirmation
        assert result.confidence == 0.3

    async def test_unreadable_image(self):
        """Нечитаемое изображение — пустой результат."""
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recognize_draft.return_value = DraftRecognition(
            allies=[],
            enemies=[],
            user_role=0,
            confidence=0.0,
            needs_confirmation=True,
            raw_response="allies:|enemies:|role:0|confidence:0.0",
        )

        result = await recognize_draft(b"bad_image", mock_llm)

        assert result.needs_confirmation
        assert result.confidence == 0.0
        assert result.allies == []
        assert result.enemies == []


# ---------------------------------------------------------------------------
# _Candidate.score и _basic_reason
# ---------------------------------------------------------------------------


class TestCandidate:
    def test_score_calculation(self):
        """Score рассчитывается по формуле с весами."""
        c = _Candidate(
            hero_id=1,
            name_ru="Анти-Маг",
            name_en="Anti-Mage",
            counter_score=0.8,
            synergy_score=0.6,
            meta_winrate=0.55,
            personal_winrate=0.6,
        )
        # 0.35*0.8 + 0.25*0.6 + 0.25*0.55 + 0.15*0.6 = 0.28 + 0.15 + 0.1375 + 0.09
        expected = 0.35 * 0.8 + 0.25 * 0.6 + 0.25 * 0.55 + 0.15 * 0.6
        assert abs(c.score - expected) < 0.001

    def test_score_without_personal(self):
        """Без личного винрейта используется 0.5."""
        c = _Candidate(
            hero_id=1,
            name_ru="Анти-Маг",
            name_en="Anti-Mage",
            counter_score=1.0,
            synergy_score=1.0,
            meta_winrate=0.55,
            personal_winrate=None,
        )
        expected = 0.35 * 1.0 + 0.25 * 1.0 + 0.25 * 0.55 + 0.15 * 0.5
        assert abs(c.score - expected) < 0.001

    def test_basic_reason_high_meta(self):
        """_basic_reason для героя с высоким мета-винрейтом."""
        c = _Candidate(
            hero_id=1, name_ru="Анти-Маг", name_en="Anti-Mage",
            meta_winrate=0.56, counter_score=0.3, synergy_score=0.3,
        )
        reason = _basic_reason(c)
        assert "56.0%" in reason

    def test_basic_reason_counter(self):
        """_basic_reason для хорошего контрпика."""
        c = _Candidate(
            hero_id=1, name_ru="Анти-Маг", name_en="Anti-Mage",
            meta_winrate=0.50, counter_score=0.8, synergy_score=0.3,
        )
        reason = _basic_reason(c)
        assert "контрпик" in reason.lower()


# ---------------------------------------------------------------------------
# recommend_picks
# ---------------------------------------------------------------------------


def _make_matchup_data(hero_id: int, vs: list[HeroMatchup], with_h: list[HeroMatchup]):
    """Хелпер для создания HeroMatchupData."""
    return HeroMatchupData(hero_id=hero_id, vs_heroes=vs, with_heroes=with_h)


def _make_stratz_mock(
    meta_heroes: list[MetaHeroStats],
    matchup_map: dict[int, HeroMatchupData] | None = None,
):
    """Создать мок StratzClient с заданными мета-героями и matchup-данными."""
    mock = AsyncMock(spec=StratzClient)
    mock.get_meta_heroes.return_value = meta_heroes
    if matchup_map:
        mock.get_hero_matchups.side_effect = lambda hid, **kw: matchup_map.get(
            hid, HeroMatchupData(hero_id=hid)
        )
    else:
        mock.get_hero_matchups.return_value = HeroMatchupData(hero_id=0)
    return mock


class TestRecommendPicks:
    async def test_returns_recommendations(self):
        """recommend_picks возвращает список PickRecommendation."""
        meta = [
            MetaHeroStats(hero_id=44, match_count=1000, win_count=550),  # PA
            MetaHeroStats(hero_id=8, match_count=900, win_count=480),   # Jugg (enemy)
            MetaHeroStats(hero_id=1, match_count=800, win_count=440),   # AM
            MetaHeroStats(hero_id=48, match_count=700, win_count=380),  # Luna
            MetaHeroStats(hero_id=81, match_count=600, win_count=320),  # Chaos Knight
        ]
        mock_stratz = _make_stratz_mock(meta)

        with patch("services.draft.get_meta_heroes") as mock_get_meta:
            from services.meta import MetaHero
            mock_get_meta.return_value = [
                MetaHero(hero_id=44, name_ru="Фантом Ассассин", name_en="Phantom Assassin",
                         winrate=0.55, pick_rate=0.1, match_count=1000),
                MetaHero(hero_id=1, name_ru="Анти-Маг", name_en="Anti-Mage",
                         winrate=0.55, pick_rate=0.08, match_count=800),
                MetaHero(hero_id=48, name_ru="Луна", name_en="Luna",
                         winrate=0.54, pick_rate=0.07, match_count=700),
                MetaHero(hero_id=81, name_ru="Хаос Кнайт", name_en="Chaos Knight",
                         winrate=0.53, pick_rate=0.06, match_count=600),
            ]

            result = await recommend_picks(
                allies=[5, 14],        # CM, Pudge — союзники
                enemies=[8, 97],       # Jugg, Magnus — враги
                user_role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=mock_stratz,
            )

        assert len(result) > 0
        assert all(isinstance(r, PickRecommendation) for r in result)
        # Не содержит уже выбранных героев
        picked_ids = {5, 14, 8, 97}
        for r in result:
            assert r.hero_id not in picked_ids

    async def test_excludes_already_picked(self):
        """Рекомендации не включают уже выбранных героев."""
        mock_stratz = _make_stratz_mock([])

        with patch("services.draft.get_meta_heroes") as mock_get_meta:
            from services.meta import MetaHero
            mock_get_meta.return_value = [
                MetaHero(hero_id=1, name_ru="Анти-Маг", name_en="Anti-Mage",
                         winrate=0.55, pick_rate=0.1, match_count=1000),
                MetaHero(hero_id=8, name_ru="Джаггернаут", name_en="Juggernaut",
                         winrate=0.54, pick_rate=0.09, match_count=900),
                MetaHero(hero_id=44, name_ru="Фантом Ассассин", name_en="Phantom Assassin",
                         winrate=0.53, pick_rate=0.08, match_count=800),
            ]

            result = await recommend_picks(
                allies=[1],            # AM уже выбран
                enemies=[8],           # Jugg уже выбран
                user_role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=mock_stratz,
            )

        for r in result:
            assert r.hero_id not in {1, 8}

    async def test_with_llm_enrichment(self):
        """Рекомендации обогащаются пояснениями от LLM."""
        mock_stratz = _make_stratz_mock([])
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.recommend_picks.return_value = [
            PickRecommendation(hero_id=44, name_ru="Фантом Ассассин",
                               reason="Контрпик против магов."),
        ]

        with patch("services.draft.get_meta_heroes") as mock_get_meta:
            from services.meta import MetaHero
            mock_get_meta.return_value = [
                MetaHero(hero_id=44, name_ru="Фантом Ассассин", name_en="Phantom Assassin",
                         winrate=0.55, pick_rate=0.1, match_count=1000),
            ]

            result = await recommend_picks(
                allies=[5],
                enemies=[8],
                user_role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=mock_stratz,
                llm_client=mock_llm,
            )

        assert len(result) > 0
        mock_llm.recommend_picks.assert_awaited_once()
        pa_rec = next((r for r in result if r.hero_id == 44), None)
        if pa_rec:
            assert "Контрпик" in pa_rec.reason

    async def test_empty_meta_returns_empty(self):
        """Если нет мета-героев и matchup-данных — пустой список."""
        mock_stratz = _make_stratz_mock([])

        with patch("services.draft.get_meta_heroes") as mock_get_meta:
            mock_get_meta.return_value = []

            result = await recommend_picks(
                allies=[],
                enemies=[],
                user_role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=mock_stratz,
            )

        assert result == []

    async def test_each_recommendation_has_reason(self):
        """Каждая рекомендация содержит непустую причину."""
        mock_stratz = _make_stratz_mock([])

        with patch("services.draft.get_meta_heroes") as mock_get_meta:
            from services.meta import MetaHero
            mock_get_meta.return_value = [
                MetaHero(hero_id=44, name_ru="Фантом Ассассин", name_en="Phantom Assassin",
                         winrate=0.55, pick_rate=0.1, match_count=1000),
                MetaHero(hero_id=48, name_ru="Луна", name_en="Luna",
                         winrate=0.54, pick_rate=0.08, match_count=800),
                MetaHero(hero_id=81, name_ru="Хаос Кнайт", name_en="Chaos Knight",
                         winrate=0.53, pick_rate=0.06, match_count=600),
            ]

            result = await recommend_picks(
                allies=[5],
                enemies=[8],
                user_role=Role.CARRY,
                bracket=RankBracket.LEGEND,
                stratz=mock_stratz,
            )

        for r in result:
            assert r.hero_id > 0
            assert r.name_ru
            assert r.reason
