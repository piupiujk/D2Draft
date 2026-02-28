"""Тесты для repositories/base.py и repositories/user.py."""

import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

# --- Мокаем зависимости ---

if "supabase" not in sys.modules:
    _mock_supabase = ModuleType("supabase")
    _mock_supabase.AsyncClient = MagicMock()  # type: ignore[attr-defined]
    _mock_supabase.create_async_client = AsyncMock()  # type: ignore[attr-defined]
    sys.modules["supabase"] = _mock_supabase

if "bot.config" not in sys.modules:
    _mock_config = ModuleType("bot.config")
    _settings = MagicMock()
    _settings.SUPABASE_URL = "https://test.supabase.co"
    _settings.SUPABASE_KEY = "test-key"
    _mock_config.settings = _settings  # type: ignore[attr-defined]
    sys.modules["bot.config"] = _mock_config

from core.exceptions import UserNotRegistered  # noqa: E402
from repositories.base import BaseRepository  # noqa: E402
from repositories.user import DuplicateUserError, UserRepository  # noqa: E402

# --- Хелперы для мока Supabase-запросов ---


def _make_mock_client():
    """Создать мок Supabase AsyncClient с цепочкой вызовов."""
    client = MagicMock()

    def _setup_chain(response_data):
        """Настроить цепочку методов таблицы и вернуть финальный execute."""
        table_mock = MagicMock()

        # select().eq().maybe_single().execute()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        execute_mock = AsyncMock()

        response = MagicMock()
        response.data = response_data

        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = execute_mock
        execute_mock.return_value = response

        # insert().execute()
        insert_mock = MagicMock()
        insert_execute = AsyncMock()
        insert_response = MagicMock()
        insert_response.data = [response_data] if response_data else []
        insert_mock.execute = insert_execute
        insert_execute.return_value = insert_response
        table_mock.insert.return_value = insert_mock

        # update().eq().execute()
        update_mock = MagicMock()
        update_eq_mock = MagicMock()
        update_execute = AsyncMock()
        update_response = MagicMock()
        update_response.data = [response_data] if response_data else []
        update_mock.eq.return_value = update_eq_mock
        update_eq_mock.execute = update_execute
        update_execute.return_value = update_response
        table_mock.update.return_value = update_mock

        return table_mock

    client._table_setup = _setup_chain
    return client


SAMPLE_USER = {
    "id": 1,
    "telegram_id": 123456789,
    "steam_id": "76561198000000001",
    "username": "TestPlayer",
    "current_mmr": 3500,
    "mmr_updated_at": "2026-02-28T12:00:00+00:00",
    "main_role": 1,
    "is_premium": False,
    "premium_expires_at": None,
    "notifications_enabled": True,
    "weekly_report_day": 1,
    "created_at": "2026-02-28T10:00:00+00:00",
    "updated_at": "2026-02-28T12:00:00+00:00",
}


# --- Тесты BaseRepository ---


class TestBaseRepository:
    """Тесты базового репозитория."""

    def test_init_with_client(self):
        """Конструктор принимает внешний клиент."""
        mock_client = MagicMock()
        repo = BaseRepository(client=mock_client)
        assert repo._client is mock_client

    def test_init_without_client(self):
        """Конструктор без клиента — клиент None."""
        repo = BaseRepository()
        assert repo._client is None

    def test_get_client_uses_injected(self):
        """_get_client возвращает инжектированный клиент."""
        mock_client = MagicMock()
        repo = BaseRepository(client=mock_client)
        result = asyncio.run(repo._get_client())
        assert result is mock_client

    def test_get_client_lazy_init(self):
        """_get_client вызывает get_supabase при отсутствии клиента."""
        import repositories.base as base_mod

        mock_client = MagicMock()
        original = base_mod.get_supabase
        base_mod.get_supabase = AsyncMock(return_value=mock_client)

        try:
            repo = BaseRepository()
            result = asyncio.run(repo._get_client())
            assert result is mock_client
            base_mod.get_supabase.assert_called_once()
        finally:
            base_mod.get_supabase = original


# --- Тесты UserRepository ---


class TestUserRepositoryGetByTelegramId:
    """Тесты метода get_by_telegram_id."""

    def test_returns_user_when_found(self):
        """Возвращает данные пользователя при нахождении."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        response = MagicMock()
        response.data = SAMPLE_USER

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=response)

        repo = UserRepository(client=client)
        result = asyncio.run(repo.get_by_telegram_id(123456789))

        assert result == SAMPLE_USER
        client.table.assert_called_with("users")
        table_mock.select.assert_called_with("*")
        select_mock.eq.assert_called_with("telegram_id", 123456789)

    def test_returns_none_when_not_found(self):
        """Возвращает None если пользователь не найден."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        response = MagicMock()
        response.data = None

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=response)

        repo = UserRepository(client=client)
        result = asyncio.run(repo.get_by_telegram_id(999999))

        assert result is None


class TestUserRepositoryGetBySteamId:
    """Тесты метода get_by_steam_id."""

    def test_returns_user_when_found(self):
        """Возвращает данные пользователя по steam_id."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        response = MagicMock()
        response.data = SAMPLE_USER

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=response)

        repo = UserRepository(client=client)
        result = asyncio.run(repo.get_by_steam_id("76561198000000001"))

        assert result == SAMPLE_USER
        select_mock.eq.assert_called_with("steam_id", "76561198000000001")

    def test_returns_none_when_not_found(self):
        """Возвращает None если steam_id не найден."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        response = MagicMock()
        response.data = None

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=response)

        repo = UserRepository(client=client)
        result = asyncio.run(repo.get_by_steam_id("nonexistent"))

        assert result is None


class TestUserRepositoryCreate:
    """Тесты метода create."""

    def _make_repo_with_no_existing_user(self):
        """Создать UserRepository с моком, где пользователь не существует."""
        client = MagicMock()

        # select -> None (пользователь не найден)
        table_select = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        not_found_response = MagicMock()
        not_found_response.data = None

        table_select.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=not_found_response)

        # insert -> SAMPLE_USER
        insert_mock = MagicMock()
        insert_response = MagicMock()
        insert_response.data = [SAMPLE_USER]
        insert_mock.execute = AsyncMock(return_value=insert_response)
        table_select.insert.return_value = insert_mock

        client.table.return_value = table_select
        return UserRepository(client=client), client

    def test_create_new_user(self):
        """Создание нового пользователя возвращает запись."""
        repo, client = self._make_repo_with_no_existing_user()

        result = asyncio.run(
            repo.create(
                telegram_id=123456789,
                steam_id="76561198000000001",
                username="TestPlayer",
                current_mmr=3500,
                main_role=1,
            )
        )

        assert result["telegram_id"] == 123456789
        assert result["username"] == "TestPlayer"

    def test_create_minimal_user(self):
        """Создание пользователя только с telegram_id."""
        repo, _ = self._make_repo_with_no_existing_user()
        result = asyncio.run(repo.create(telegram_id=123456789))
        assert result is not None

    def test_create_duplicate_telegram_id_raises(self):
        """Дублирование telegram_id вызывает DuplicateUserError."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        existing_response = MagicMock()
        existing_response.data = SAMPLE_USER

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=existing_response)

        repo = UserRepository(client=client)
        try:
            asyncio.run(repo.create(telegram_id=123456789))
            assert False, "Должно было быть DuplicateUserError"
        except DuplicateUserError as e:
            assert e.field == "telegram_id"
            assert e.value == 123456789

    def test_create_duplicate_steam_id_raises(self):
        """Дублирование steam_id вызывает DuplicateUserError."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()

        call_count = 0

        async def _execute():
            nonlocal call_count
            call_count += 1
            resp = MagicMock()
            # Первый вызов (telegram_id) — не найден
            # Второй вызов (steam_id) — найден
            resp.data = SAMPLE_USER if call_count > 1 else None
            return resp

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = _execute

        repo = UserRepository(client=client)
        try:
            asyncio.run(repo.create(telegram_id=999, steam_id="76561198000000001"))
            assert False, "Должно было быть DuplicateUserError"
        except DuplicateUserError as e:
            assert e.field == "steam_id"


class TestUserRepositoryUpdate:
    """Тесты метода update."""

    def test_update_existing_user(self):
        """Обновление полей существующего пользователя."""
        client = MagicMock()
        table_mock = MagicMock()

        # select -> пользователь найден
        select_mock = MagicMock()
        eq_select = MagicMock()
        maybe_single_mock = MagicMock()
        found_response = MagicMock()
        found_response.data = SAMPLE_USER
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_select
        eq_select.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=found_response)

        # update -> обновлённые данные
        update_mock = MagicMock()
        update_eq = MagicMock()
        updated_user = {**SAMPLE_USER, "username": "NewName"}
        update_response = MagicMock()
        update_response.data = [updated_user]
        table_mock.update.return_value = update_mock
        update_mock.eq.return_value = update_eq
        update_eq.execute = AsyncMock(return_value=update_response)

        client.table.return_value = table_mock

        repo = UserRepository(client=client)
        result = asyncio.run(repo.update(123456789, username="NewName"))

        assert result["username"] == "NewName"
        table_mock.update.assert_called_with({"username": "NewName"})

    def test_update_nonexistent_user_raises(self):
        """Обновление несуществующего пользователя вызывает UserNotRegistered."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        not_found = MagicMock()
        not_found.data = None

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=not_found)

        repo = UserRepository(client=client)
        try:
            asyncio.run(repo.update(999999, username="Ghost"))
            assert False, "Должно было быть UserNotRegistered"
        except UserNotRegistered as e:
            assert e.telegram_id == 999999


class TestUserRepositoryUpdateMmr:
    """Тесты метода update_mmr."""

    def test_update_mmr_changes_value(self):
        """update_mmr обновляет current_mmr и mmr_updated_at."""
        client = MagicMock()
        table_mock = MagicMock()

        # select -> пользователь найден
        select_mock = MagicMock()
        eq_select = MagicMock()
        maybe_single_mock = MagicMock()
        found_response = MagicMock()
        found_response.data = SAMPLE_USER
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_select
        eq_select.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=found_response)

        # update -> обновлённые данные
        update_mock = MagicMock()
        update_eq = MagicMock()
        updated_user = {**SAMPLE_USER, "current_mmr": 4000}
        update_response = MagicMock()
        update_response.data = [updated_user]
        table_mock.update.return_value = update_mock
        update_mock.eq.return_value = update_eq
        update_eq.execute = AsyncMock(return_value=update_response)

        client.table.return_value = table_mock

        repo = UserRepository(client=client)
        result = asyncio.run(repo.update_mmr(123456789, 4000))

        assert result["current_mmr"] == 4000
        # Проверяем что в update переданы current_mmr и mmr_updated_at
        call_args = table_mock.update.call_args[0][0]
        assert call_args["current_mmr"] == 4000
        assert "mmr_updated_at" in call_args

    def test_update_mmr_nonexistent_user_raises(self):
        """update_mmr для несуществующего пользователя вызывает UserNotRegistered."""
        client = MagicMock()
        table_mock = MagicMock()
        select_mock = MagicMock()
        eq_mock = MagicMock()
        maybe_single_mock = MagicMock()
        not_found = MagicMock()
        not_found.data = None

        client.table.return_value = table_mock
        table_mock.select.return_value = select_mock
        select_mock.eq.return_value = eq_mock
        eq_mock.maybe_single.return_value = maybe_single_mock
        maybe_single_mock.execute = AsyncMock(return_value=not_found)

        repo = UserRepository(client=client)
        try:
            asyncio.run(repo.update_mmr(999999, 5000))
            assert False, "Должно было быть UserNotRegistered"
        except UserNotRegistered as e:
            assert e.telegram_id == 999999


class TestDuplicateUserError:
    """Тесты исключения DuplicateUserError."""

    def test_attributes(self):
        """Атрибуты field и value заполнены корректно."""
        err = DuplicateUserError("telegram_id", 123)
        assert err.field == "telegram_id"
        assert err.value == 123
        assert "telegram_id" in str(err)
        assert "123" in str(err)

    def test_is_exception(self):
        """DuplicateUserError является Exception."""
        err = DuplicateUserError("steam_id", "abc")
        assert isinstance(err, Exception)
