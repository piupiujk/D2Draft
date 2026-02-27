"""Перечисления для проекта D2Draft."""

from enum import IntEnum, StrEnum


class Role(IntEnum):
    """Роли игроков в Dota 2 (позиции 1-5)."""

    CARRY = 1
    MID = 2
    OFFLANE = 3
    SOFT_SUPPORT = 4
    HARD_SUPPORT = 5

    @property
    def label_ru(self) -> str:
        return _ROLE_LABELS_RU[self]

    @property
    def label_en(self) -> str:
        return _ROLE_LABELS_EN[self]


_ROLE_LABELS_RU: dict[Role, str] = {
    Role.CARRY: "Керри",
    Role.MID: "Мидер",
    Role.OFFLANE: "Оффлейнер",
    Role.SOFT_SUPPORT: "Софт-саппорт",
    Role.HARD_SUPPORT: "Хард-саппорт",
}

_ROLE_LABELS_EN: dict[Role, str] = {
    Role.CARRY: "Carry",
    Role.MID: "Mid",
    Role.OFFLANE: "Offlane",
    Role.SOFT_SUPPORT: "Soft Support",
    Role.HARD_SUPPORT: "Hard Support",
}


class RankBracket(StrEnum):
    """Ранговые скобки Dota 2 (как в Stratz API)."""

    HERALD = "HERALD"
    GUARDIAN = "GUARDIAN"
    CRUSADER = "CRUSADER"
    ARCHON = "ARCHON"
    LEGEND = "LEGEND"
    ANCIENT = "ANCIENT"
    DIVINE = "DIVINE"
    IMMORTAL = "IMMORTAL"


class SubscriptionPlan(StrEnum):
    """Тарифные планы подписки."""

    FREE = "free"
    PREMIUM_MONTHLY = "premium_monthly"
    PREMIUM_YEARLY = "premium_yearly"


class MatchOutcome(StrEnum):
    """Результат матча."""

    WIN = "win"
    LOSS = "loss"
