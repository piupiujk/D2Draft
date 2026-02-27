"""Кастомные исключения проекта D2Draft."""


class D2DraftError(Exception):
    """Базовое исключение проекта."""


class HeroNotFound(D2DraftError):
    """Герой не найден по имени или ID."""

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(f"Герой не найден: {query!r}")


class SteamProfileClosed(D2DraftError):
    """Профиль Steam закрыт или данные недоступны."""

    def __init__(self, steam_id: str) -> None:
        self.steam_id = steam_id
        super().__init__(f"Профиль Steam закрыт: {steam_id}")


class APIRateLimited(D2DraftError):
    """Превышен лимит запросов к внешнему API."""

    def __init__(self, service: str, retry_after: float | None = None) -> None:
        self.service = service
        self.retry_after = retry_after
        msg = f"Превышен лимит запросов к {service}"
        if retry_after is not None:
            msg += f" (повтор через {retry_after:.0f} сек)"
        super().__init__(msg)


class UserNotRegistered(D2DraftError):
    """Пользователь не зарегистрирован в боте."""

    def __init__(self, telegram_id: int) -> None:
        self.telegram_id = telegram_id
        super().__init__(f"Пользователь не зарегистрирован: {telegram_id}")
