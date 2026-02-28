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
