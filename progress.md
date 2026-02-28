# Progress Log

Лог прогресса работы над задачами проекта D2Draft.

---

## 2026-02-27 — TASK-001: Инициализация проекта (DONE)

**Что сделано:**
- Создан `pyproject.toml` с зависимостями: aiogram>=3.4, supabase, httpx, apscheduler, pydantic-settings, python-dotenv + dev deps (pytest, ruff)
- Создана полная структура папок: `bot/` (handlers/, states/, keyboards/, middlewares/, filters/), `services/`, `repositories/`, `clients/`, `scheduler/jobs/`, `db/migrations/`, `core/`, `prompts/`, `tests/` (services/, clients/, handlers/)
- 17 файлов `__init__.py` созданы во всех пакетах
- Создан `.env.example` со всеми переменными окружения (BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, STRATZ_TOKEN, OPENDOTA_BASE_URL, LLM_API_KEY, LLM_PROVIDER, REDIS_URL)
- Создан `bot/config.py` с Pydantic Settings класс `Settings`
- Создан `bot/__main__.py` с минимальным запуском бота (Bot + Dispatcher + polling)

**Тест-шаги:**
- Шаг 3 (наличие всех директорий и __init__.py) — ✅ Проверено через Glob
- Шаги 1-2 (pip install, python -m bot) — Требуют ручной проверки пользователем (permission block)

**Заметки для следующей итерации:**
- `uv` не установлен в системе — нужно `pip install uv` перед запуском `uv run ruff check .` и `uv run pytest`
- Python 3.12.6 (32-bit) доступен в системе
- Следующие задачи разблокированы: TASK-002, TASK-003, TASK-006, TASK-007, TASK-009, TASK-011, TASK-022, TASK-033, TASK-036

---

## 2026-02-28 — TASK-003: Core-модули героев, enum-ы, исключения (DONE)

**Что сделано:**
- `core/constants.py` — полный список 126 героев Dota 2 с ID, именами EN и RU (актуальный патч, включая Ringmaster, Kez, Largo)
- `core/hero_mapping.py` — двусторонний маппинг hero_id <-> name_en/name_ru, поиск нечувствителен к регистру, 100+ популярных сокращений (am, qop, инвок, фурион и т.д.)
- `core/enums.py` — Role (1-5 с label_ru/label_en), RankBracket (8 рангов), SubscriptionPlan (free/premium), MatchOutcome (win/loss)
- `core/exceptions.py` — HeroNotFound, SteamProfileClosed, APIRateLimited, UserNotRegistered
- `tests/test_core.py` — 26 тестов покрывающих маппинг, поиск, enum-ы, константы
- Исправлена конфигурация `pyproject.toml`: добавлен `[tool.hatch.build.targets.wheel]` для корректной сборки

**Тест-шаги:**
- Шаг 1: `find_hero('Anti-Mage')`, `find_hero('Анти-Маг')`, `find_hero('am')` — все возвращают hero_id=1 ✅
- Шаг 2: 126 героев в маппинге (>= 124) ✅
- Шаг 3: Role содержит значения 1-5 с label_ru ✅
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run pytest tests/test_core.py -v` — 26/26 тестов ✅

**Заметки для следующей итерации:**
- `uv run` не работает из-за зависимости supabase -> storage3 -> pyiceberg (требует Visual C++ Build Tools). Использовать `uv tool run ruff check .` и `uv tool run pytest` вместо `uv run ruff check .`
- Правило ruff N818 отключено т.к. имена исключений заданы в PRD без суффикса Error
- Следующие приоритетные задачи (critical, deps выполнены): TASK-002 (Supabase миграции), TASK-006 (OpenDota клиент), TASK-007 (Stratz клиент), TASK-011 (клавиатуры)

---

## 2026-02-28 — TASK-002: Supabase клиент и SQL-миграции (DONE)

**Что сделано:**
- `db/supabase.py` — async Supabase клиент (singleton) через `create_async_client`
- 6 SQL-миграций:
  - `001_create_users.sql` — таблица users (telegram_id, steam_id, mmr, role, premium, уведомления, updated_at триггер)
  - `002_create_mmr_history.sql` — история MMR с FK на users
  - `003_create_match_analyses.sql` — анализы матчей с JSONB stats
  - `004_create_draft_analyses.sql` — анализы драфтов с INTEGER[] массивами
  - `005_create_subscriptions.sql` — подписки со статусами (active/expired/cancelled)
  - `006_enable_rls.sql` — RLS включён на всех 5 таблицах, 6 политик безопасности
- Исправлен `search_path` в функции `update_updated_at_column` (по рекомендации Supabase Security Advisor)
- `tests/test_db.py` — 14 тестов: singleton-клиент, наличие миграций, содержимое SQL, RLS-политики
- Тесты корректно мокают `supabase` и `bot.config` модули для работы без установленных пакетов

**Тест-шаги:**
- Шаг 1: Все 6 миграций применены к Supabase проекту D2Draft (vsvkfupjkkrvcblklhci) ✅
- Шаг 2: Все 5 таблиц созданы с правильными типами полей (проверено через list_tables) ✅
- Шаг 3: RLS включён на всех таблицах, 6 политик подтверждены через pg_policies ✅
- Security advisors — 0 предупреждений ✅
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run pytest tests/test_db.py tests/test_core.py -v` — 40/40 тестов ✅

**Заметки для следующей итерации:**
- `uv run` по-прежнему не работает из-за supabase → storage3 → pyiceberg (Visual C++ Build Tools). Использовать `uv tool run`.
- Тесты для async-кода используют `asyncio.run()` вместо `pytest-asyncio` для совместимости с `uv tool run pytest`
- Мокирование `sys.modules` в тестах: supabase и bot.config мокаются до импорта db.supabase
- Следующие разблокированные задачи (critical): TASK-004 (user repo), TASK-006 (OpenDota), TASK-007 (Stratz), TASK-011 (клавиатуры)
- TASK-004 разблокирован и является следующим по цепочке зависимостей (блокирует TASK-005, TASK-010, TASK-012)

---

## 2026-02-28 — TASK-004: Базовые репозитории: user repo с CRUD (DONE)

**Что сделано:**
- `repositories/base.py` — базовый класс `BaseRepository` с lazy-инициализацией Supabase клиента (поддержка DI через конструктор или singleton через `get_supabase()`)
- `repositories/user.py` — класс `UserRepository` с полным набором async CRUD-методов:
  - `get_by_telegram_id(telegram_id)` — поиск пользователя по telegram_id
  - `get_by_steam_id(steam_id)` — поиск пользователя по steam_id
  - `create(telegram_id, steam_id, username, current_mmr, main_role)` — создание с проверкой дубликатов
  - `update(telegram_id, **fields)` — обновление произвольных полей
  - `update_mmr(telegram_id, new_mmr)` — обновление MMR с фиксацией mmr_updated_at
- `DuplicateUserError` — кастомное исключение при дублировании telegram_id/steam_id
- `tests/test_repositories.py` — 18 тестов покрывающих: BaseRepository (инициализация, lazy-init), get_by_telegram_id, get_by_steam_id, create (новый/минимальный/дубликат telegram_id/дубликат steam_id), update (существующий/несуществующий), update_mmr (обновление/несуществующий), DuplicateUserError

**Тест-шаги:**
- Шаг 1: Создание тестового пользователя через `user_repo.create()` — ✅ (тест test_create_new_user)
- Шаг 2: Получение через `get_by_telegram_id()` — данные совпадают ✅ (тест test_returns_user_when_found)
- Шаг 3: Обновление MMR через `update_mmr()` — значение изменилось ✅ (тест test_update_mmr_changes_value)
- Шаг 4: Попытка создать дубликат — `DuplicateUserError` ✅ (тесты test_create_duplicate_telegram_id_raises, test_create_duplicate_steam_id_raises)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run pytest tests/ -v` — 58/58 тестов ✅

**Заметки для следующей итерации:**
- Паттерн мокирования: для тестов Supabase-запросов нужно собирать цепочку `.table().select().eq().maybe_single().execute()` из MagicMock + AsyncMock
- При мокировании `get_supabase` нужно патчить в модуле `repositories.base`, а не `db.supabase` (из-за `from db.supabase import get_supabase`)
- Следующие разблокированные задачи (critical, deps выполнены): TASK-006 (OpenDota клиент), TASK-007 (Stratz клиент), TASK-011 (клавиатуры)
- TASK-005 (остальные репозитории) теперь разблокирован (зависит от TASK-004)
- TASK-010 (middleware) теперь разблокирован (зависит от TASK-004)

---

## 2026-02-28 — TASK-005: Репозитории: mmr_history, match_analyses, draft_analyses, subscriptions (DONE)

**Что сделано:**
- `repositories/mmr_history.py` — класс `MmrHistoryRepository`:
  - `insert(user_id, mmr)` — добавление записи в историю
  - `get_history(user_id, days=30)` — получение истории за N дней с фильтрацией по дате
- `repositories/match_analysis.py` — класс `MatchAnalysisRepository`:
  - `insert(user_id, match_id, hero_id, role, result, duration_sec, stats, llm_summary)` — вставка анализа матча
  - `get_by_match_id(user_id, match_id)` — поиск по match_id для конкретного пользователя
  - `get_latest(user_id, limit=1)` — последние анализы
- `repositories/draft_analysis.py` — класс `DraftAnalysisRepository`:
  - `insert(user_id, ally_hero_ids, enemy_hero_ids, recommended_ids, user_role, confidence)` — вставка анализа драфта
  - `get_latest(user_id, limit=5)` — последние анализы драфтов
- `repositories/subscription.py` — класс `SubscriptionRepository`:
  - `create(user_id, plan, expires_at)` — создание подписки со статусом active
  - `get_active(user_id)` — получение активной подписки
  - `deactivate(subscription_id)` — деактивация (статус cancelled + cancelled_at)
- `tests/test_repositories_extra.py` — 21 тест покрывающий все 4 репозитория

**Тест-шаги:**
- Шаг 1: insert в mmr_history + get_history за 30 дней — ✅ (тесты test_insert_returns_record, test_returns_list_of_records)
- Шаг 2: insert в match_analyses + get_by_match_id — ✅ (тесты test_insert_returns_record, test_returns_record_when_found)
- Шаг 3: create подписку + get_active + deactivate — ✅ (тесты test_create_returns_record, test_returns_active_subscription, test_deactivate_sets_cancelled)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run pytest tests/ -v` — 79/79 тестов ✅

**Заметки для следующей итерации:**
- Все 4 репозитория следуют паттерну BaseRepository с lazy-init Supabase клиента
- Хелперы `_mock_insert`, `_mock_select_list`, `_mock_select_single`, `_mock_update` упрощают создание моков для Supabase-цепочек
- Следующие разблокированные задачи: TASK-017 (анализ матча, зависит от 006+005+003), TASK-019 (профиль, зависит от 006+005), TASK-030 (scheduler, зависит от 004+005+006), TASK-032 (подписки, зависит от 005+010)
- Приоритетные critical задачи с выполненными зависимостями: TASK-006 (OpenDota), TASK-007 (Stratz), TASK-010 (middleware), TASK-011 (клавиатуры)
