"""Сервис драфта: распознавание скриншота и рекомендация пиков."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from clients.llm import DraftRecognition, LLMClient, PickRecommendation
from clients.opendota import OpenDotaClient, PlayerHeroStats
from clients.protracker import ProMetaHero, ProtrackerClient, ProtrackerError
from clients.stratz import StratzClient
from core.constants import HERO_BY_ID
from core.enums import RankBracket, Role
from core.hero_mapping import get_hero_by_id
from core.logging import get_logger
from services.meta import get_meta_heroes

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Порог уверенности
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.7


# ---------------------------------------------------------------------------
# Модели
# ---------------------------------------------------------------------------


@dataclass
class ValidatedDraft:
    """Результат распознавания драфта с валидацией hero_id."""

    allies: list[int] = field(default_factory=list)
    enemies: list[int] = field(default_factory=list)
    allies_names: list[str] = field(default_factory=list)
    enemies_names: list[str] = field(default_factory=list)
    user_role: int | None = None
    confidence: float = 0.0
    needs_confirmation: bool = False
    raw_response: str = ""
    invalid_ids: list[int] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Основная функция
# ---------------------------------------------------------------------------


async def recognize_draft(
    image_bytes: bytes,
    llm_client: LLMClient,
) -> ValidatedDraft:
    """Распознать драфт из скриншота через LLM Vision.

    Аргументы:
        image_bytes: байты изображения (PNG/JPEG).
        llm_client: экземпляр LLMClient для Vision-запроса.

    Возвращает ValidatedDraft с валидированными hero_id и именами на русском.
    При confidence < CONFIDENCE_THRESHOLD выставляет needs_confirmation=True.
    """
    recognition: DraftRecognition = await llm_client.recognize_draft(image_bytes)

    return _validate_recognition(recognition)


def _validate_recognition(recognition: DraftRecognition) -> ValidatedDraft:
    """Валидирует распознанные hero_id и обогащает русскими именами."""
    result = ValidatedDraft(
        raw_response=recognition.raw_response,
        confidence=recognition.confidence,
        user_role=(
            recognition.user_role
            if recognition.user_role and recognition.user_role > 0
            else None
        ),
    )

    invalid_ids: list[int] = []

    # Валидация союзников
    for hid in recognition.allies:
        if hid in HERO_BY_ID:
            result.allies.append(hid)
            hero = get_hero_by_id(hid)
            result.allies_names.append(hero.name_en)
        else:
            invalid_ids.append(hid)

    # Валидация противников
    for hid in recognition.enemies:
        if hid in HERO_BY_ID:
            result.enemies.append(hid)
            hero = get_hero_by_id(hid)
            result.enemies_names.append(hero.name_en)
        else:
            invalid_ids.append(hid)

    result.invalid_ids = invalid_ids

    # Пересчёт уверенности при невалидных ID
    if invalid_ids:
        total = len(recognition.allies) + len(recognition.enemies)
        valid = len(result.allies) + len(result.enemies)
        if total > 0:
            result.confidence = result.confidence * (valid / total)

    # Порог уверенности
    if result.confidence < CONFIDENCE_THRESHOLD:
        result.needs_confirmation = True

    # Также помечаем как needs_confirmation, если пришло от парсера
    if recognition.needs_confirmation:
        result.needs_confirmation = True

    # Пустой драфт — низкая уверенность
    if not result.allies and not result.enemies:
        result.needs_confirmation = True
        result.confidence = 0.0

    return result


# ---------------------------------------------------------------------------
# Рекомендация пиков
# ---------------------------------------------------------------------------

# Веса для расчёта score кандидата
_W_META = 0.45     # мета-винрейт на позиции (главный фактор)
_W_COUNTER = 0.25  # контрпик вражеского состава
_W_SYNERGY = 0.15  # синергия с союзниками
_W_PERSONAL = 0.15  # личный винрейт

# Количество рекомендаций
_PICK_COUNT = 5
_LLM_CANDIDATE_COUNT = 8  # отправляем в LLM чуть больше для лучшего контекста


@dataclass
class _Candidate:
    """Внутренний кандидат для ранжирования."""

    hero_id: int
    name_ru: str
    name_en: str
    counter_score: float = 0.0  # чем выше — лучше контрпик врагам
    synergy_score: float = 0.0  # чем выше — лучше синергия с союзниками
    meta_winrate: float = 0.0
    personal_winrate: float | None = None
    personal_games: int | None = None

    @property
    def score(self) -> float:
        """Итоговый score (0.0 — 1.0)."""
        personal = self.personal_winrate if self.personal_winrate is not None else 0.5
        return (
            _W_COUNTER * self.counter_score
            + _W_SYNERGY * self.synergy_score
            + _W_META * self.meta_winrate
            + _W_PERSONAL * personal
        )


async def recommend_picks(
    allies: list[int],
    enemies: list[int],
    user_role: Role | int,
    bracket: RankBracket | str,
    *,
    stratz: StratzClient,
    opendota: OpenDotaClient | None = None,
    llm_client: LLMClient | None = None,
    account_id: int | None = None,
    mmr: int = 0,
) -> list[PickRecommendation]:
    """Рекомендовать 3-5 героев на основе текущего драфта.

    Алгоритм:
    1. Получаем matchup-данные по вражеским героям (контрпики + синергии)
    2. Получаем мета-героев для роли
    3. (опц.) личную статистику из OpenDota
    4. Считаем score = контрпик + синергия + мета + личный опыт
    5. Обогащаем пояснениями через LLM (если доступен)

    Возвращает список PickRecommendation (3-5 штук), отсортированных по score.
    """
    role = Role(user_role)
    rank = RankBracket(bracket)

    picked = set(allies) | set(enemies)

    # --- 1. Параллельно собираем данные ---
    matchup_tasks = [
        stratz.get_hero_matchups(eid, bracket=rank) for eid in enemies
    ]

    # Protracker мета (с fallback на Stratz)
    async def _fetch_protracker_meta() -> list[ProMetaHero] | None:
        protracker = ProtrackerClient()
        try:
            return await protracker.get_meta_heroes(position=int(role), mmr=mmr)
        except ProtrackerError:
            logger.warning("Protracker meta недоступен, fallback на Stratz", exc_info=True)
            return None
        except Exception:
            logger.warning("Protracker meta: неожиданная ошибка", exc_info=True)
            return None
        finally:
            protracker.close()

    personal_task: asyncio.Task[list[PlayerHeroStats]] | None = None
    if opendota is not None and account_id is not None:
        personal_task = asyncio.ensure_future(
            opendota.get_player_heroes(account_id)
        )

    # Запускаем matchup-запросы и protracker мету параллельно
    matchup_results_raw, pro_meta = await asyncio.gather(
        asyncio.gather(*matchup_tasks, return_exceptions=True),
        _fetch_protracker_meta(),
    )

    # Если protracker недоступен — fallback на Stratz
    if pro_meta:
        meta_heroes = [
            type("_Meta", (), {"hero_id": m.hero_id, "winrate": m.winrate})()
            for m in pro_meta
        ]
    else:
        logger.info("Используем Stratz мету как fallback")
        meta_heroes = await get_meta_heroes(role, rank, stratz=stratz, top_n=30)

    personal_stats: list[PlayerHeroStats] = []
    if personal_task is not None:
        try:
            personal_stats = await personal_task
        except Exception:
            pass  # личная статистика не критична

    # --- 2. Строим карты matchup-данных ---
    # counter_map[hero_id] = суммарная synergy vs (отрицательная = хороший контрпик)
    counter_map: dict[int, float] = {}
    # synergy_map[hero_id] = суммарная synergy with союзниками
    synergy_map: dict[int, float] = {}

    for matchup_data in matchup_results_raw:
        if isinstance(matchup_data, Exception):
            continue
        # vs_heroes — герои, которые проигрывают этому врагу (низкая synergy = хороший контрпик)
        for vs in matchup_data.vs_heroes:
            hid = vs.hero_id2
            if hid not in picked:
                # synergy < 0 означает что hero_id2 хорошо играет ПРОТИВ данного врага
                counter_map[hid] = counter_map.get(hid, 0.0) - vs.synergy

    # Синергия с союзниками — через matchup with
    ally_matchup_tasks = [
        stratz.get_hero_matchups(aid, bracket=rank) for aid in allies
    ]
    if ally_matchup_tasks:
        ally_results_raw = await asyncio.gather(
            *ally_matchup_tasks, return_exceptions=True,
        )
        for matchup_data in ally_results_raw:
            if isinstance(matchup_data, Exception):
                continue
            for wh in matchup_data.with_heroes:
                hid = wh.hero_id2
                if hid not in picked:
                    synergy_map[hid] = synergy_map.get(hid, 0.0) + wh.synergy

    # --- 3. Строим кандидатов из мета-героев ---
    meta_map = {m.hero_id: m for m in meta_heroes}
    personal_map = {s.hero_id: s for s in personal_stats}

    # Нормализация counter и synergy скоров
    counter_vals = list(counter_map.values())
    counter_max = max(counter_vals) if counter_vals else 1.0
    counter_min = min(counter_vals) if counter_vals else 0.0
    counter_range = counter_max - counter_min if counter_max != counter_min else 1.0

    synergy_vals = list(synergy_map.values())
    synergy_max = max(synergy_vals) if synergy_vals else 1.0
    synergy_min = min(synergy_vals) if synergy_vals else 0.0
    synergy_range = synergy_max - synergy_min if synergy_max != synergy_min else 1.0

    # Кандидаты — ТОЛЬКО герои из мета-пула для выбранной позиции.
    # Контрпики и синергии используются для ранжирования внутри пула,
    # а не для добавления кандидатов с других позиций.
    candidate_ids = set()
    for m in meta_heroes:
        if m.hero_id not in picked:
            candidate_ids.add(m.hero_id)

    candidates: list[_Candidate] = []
    for hid in candidate_ids:
        hero_data = HERO_BY_ID.get(hid)
        if hero_data is None:
            continue

        meta = meta_map.get(hid)
        personal = personal_map.get(hid)

        c = _Candidate(
            hero_id=hid,
            name_ru=hero_data.name_ru,
            name_en=hero_data.name_en,
            counter_score=(
                (counter_map.get(hid, 0.0) - counter_min) / counter_range
                if hid in counter_map else 0.0
            ),
            synergy_score=(
                (synergy_map.get(hid, 0.0) - synergy_min) / synergy_range
                if hid in synergy_map else 0.0
            ),
            meta_winrate=meta.winrate if meta else 0.5,
            personal_winrate=personal.winrate if personal else None,
            personal_games=personal.games if personal else None,
        )
        candidates.append(c)

    # Сортируем по score
    candidates.sort(key=lambda c: c.score, reverse=True)
    top = candidates[:_LLM_CANDIDATE_COUNT]

    if not top:
        return []

    # --- 4. Генерируем пояснения через LLM ---
    if llm_client is not None:
        recommendations = await _enrich_with_llm(
            top[:_PICK_COUNT], allies, enemies, role, rank, llm_client,
        )
    else:
        recommendations = _build_basic_recommendations(top[:_PICK_COUNT])

    return recommendations


async def _enrich_with_llm(
    candidates: list[_Candidate],
    allies: list[int],
    enemies: list[int],
    role: Role,
    bracket: RankBracket,
    llm_client: LLMClient,
) -> list[PickRecommendation]:
    """Генерировать рекомендации с пояснениями от LLM."""
    allies_names = [
        get_hero_by_id(hid).name_en for hid in allies if hid in HERO_BY_ID
    ]
    enemies_names = [
        get_hero_by_id(hid).name_en for hid in enemies if hid in HERO_BY_ID
    ]

    draft_context = {
        "allies": allies_names,
        "enemies": enemies_names,
        "user_role": int(role),
        "bracket": str(bracket),
        "meta_heroes": [
            {
                "hero_id": c.hero_id,
                "name": c.name_en,
                "meta_winrate": round(c.meta_winrate * 100, 1),
                "personal_winrate": (
                    round(c.personal_winrate * 100, 1)
                    if c.personal_winrate is not None else None
                ),
                "personal_games": c.personal_games,
            }
            for c in candidates
        ],
    }

    try:
        llm_recommendations = await llm_client.recommend_picks(draft_context)
    except Exception:
        return _build_basic_recommendations(candidates)

    # Маппим результат LLM на наших кандидатов
    llm_map = {r.hero_id: r for r in llm_recommendations}
    result: list[PickRecommendation] = []
    for c in candidates:
        llm_rec = llm_map.get(c.hero_id)
        result.append(PickRecommendation(
            hero_id=c.hero_id,
            name_ru=c.name_en,
            reason=llm_rec.reason if llm_rec else _basic_reason(c),
        ))

    return result


def _build_basic_recommendations(
    candidates: list[_Candidate],
) -> list[PickRecommendation]:
    """Сформировать рекомендации без LLM (fallback)."""
    return [
        PickRecommendation(
            hero_id=c.hero_id,
            name_ru=c.name_en,
            reason=_basic_reason(c),
        )
        for c in candidates
    ]


def _basic_reason(c: _Candidate) -> str:
    """Сгенерировать базовое пояснение без LLM."""
    parts: list[str] = []
    if c.meta_winrate > 0.52:
        parts.append(f"Винрейт в мете {c.meta_winrate * 100:.1f}%")
    if c.counter_score > 0.5:
        parts.append("Хороший контрпик врагам")
    if c.synergy_score > 0.5:
        parts.append("Хорошая синергия с союзниками")
    if c.personal_winrate is not None and c.personal_winrate > 0.55:
        parts.append(f"Личный винрейт {c.personal_winrate * 100:.1f}%")
    return ". ".join(parts) if parts else f"Винрейт в мете {c.meta_winrate * 100:.1f}%"
