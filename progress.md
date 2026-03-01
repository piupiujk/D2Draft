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

---

## 2026-02-28 — TASK-006: HTTP-клиент OpenDota API (DONE)

**Что сделано:**
- `clients/opendota.py` — async класс `OpenDotaClient` на базе httpx:
  - `get_player(account_id)` — профиль игрока (personaname, steamid, rank_tier, mmr_estimate)
  - `get_recent_matches(account_id, limit)` — последние матчи с полными метриками (KDA, GPM, XPM, damage, и т.д.)
  - `get_player_heroes(account_id)` — статистика героев (games, win, winrate)
  - `get_match(match_id)` — детали матча с составами игроков
- Типизированные dataclass-модели: `PlayerProfile`, `RecentMatch`, `PlayerHeroStats`, `MatchDetails`
- Token-bucket rate limiter: не более 60 запросов в минуту (`_RateLimiter`)
- Retry логика: до 3 попыток при 429, 5xx и сетевых ошибках с экспоненциальным backoff
- `APIRateLimited` исключение при исчерпании retry на 429
- Context manager поддержка (`async with OpenDotaClient() as client:`)
- `tests/test_opendota.py` — 18 тестов: парсинг всех 4 эндпоинтов, is_win/winrate свойства, retry на 500/сетевых ошибках, APIRateLimited на 429, 404 без retry, context manager

**Тест-шаги:**
- Шаг 1: `get_player()` с мок-данными — валидный PlayerProfile ✅
- Шаг 2: `get_recent_matches()` — список RecentMatch с метриками ✅
- Шаг 3: Невалидный ID (404) — HTTPStatusError, 1 вызов без retry ✅
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 97/97 тестов ✅

**Заметки для следующей итерации:**
- `uv tool run --with httpx pytest` — нужен флаг `--with httpx` т.к. httpx не входит в стандартное окружение pytest
- OpenDota API использует account_id (32-bit), а не Steam ID 64-bit. Конвертация: `steam_id_64 - 76561197960265728`
- Модели — dataclass (не Pydantic), чтобы не тянуть лишнюю зависимость для простых DTO
- Следующие разблокированные задачи: TASK-008 (Steam клиент, зависит от 006), TASK-017 (анализ матча, зависит от 006+005+003), TASK-019 (профиль, зависит от 006+005)
- Приоритетные critical задачи с выполненными зависимостями: TASK-007 (Stratz), TASK-010 (middleware), TASK-011 (клавиатуры)

---

## 2026-02-28 — TASK-007: HTTP-клиент Stratz API (GraphQL) (DONE)

**Что сделано:**
- `clients/stratz.py` — async класс `StratzClient` на базе httpx для Stratz GraphQL API:
  - `get_meta_heroes(role, bracket)` — мета-герои по роли и ранговому брекету (winWeek, ALL_PICK_RANKED)
  - `get_hero_build(hero_id, role, bracket)` — item build героя по фазам (starting, early, mid, late)
  - `get_hero_matchups(hero_id, bracket)` — matchup-данные: синергии (with) и контрпики (vs) с сортировкой по synergy
- GraphQL запросы оформлены как строковые константы: `QUERY_META_HEROES`, `QUERY_HERO_BUILD`, `QUERY_HERO_MATCHUPS`
- Типизированные dataclass-модели: `MetaHeroStats`, `ItemPurchase`, `HeroBuildData`, `HeroMatchup`, `HeroMatchupData`
- Маппинг enum-ов проекта -> Stratz API: `RANK_TO_STRATZ_BRACKET` (сгруппированные брекеты), `ROLE_TO_STRATZ_POSITION`
- Token-bucket rate limiter: 20 запросов/сек (лимит Stratz API)
- Retry логика: до 3 попыток при 429, 5xx и сетевых ошибках с экспоненциальным backoff
- `StratzGraphQLError` — обработка ошибок GraphQL (errors в ответе)
- `APIRateLimited` при исчерпании retry на 429
- Авторизация через Bearer token (заголовок Authorization)
- Context manager поддержка (`async with StratzClient(token) as client:`)
- `tests/test_stratz.py` — 34 теста: маппинг enum-ов, парсинг мета-героев/билдов/matchups, переменные запроса, Bearer token, пустые ответы, GraphQL ошибки, retry на 500/429/сетевых ошибках, 4xx без retry, context manager

**Тест-шаги:**
- Шаг 1: `get_meta_heroes(role=1, bracket='DIVINE')` — список MetaHeroStats с heroId, matchCount, winCount ✅
- Шаг 2: `get_hero_build(hero_id=1)` — HeroBuildData со startingItems, earlyGame, midGame, lateGame ✅
- Шаг 3: Невалидный запрос (GraphQL error) — StratzGraphQLError, не crash ✅
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 131/131 тестов ✅

**Заметки для следующей итерации:**
- Stratz API использует сгруппированные брекеты: HERALD_GUARDIAN, CRUSADER_ARCHON, LEGEND_ANCIENT, DIVINE_IMMORTAL (enum RankBracketBasicEnum)
- Позиции: POSITION_1 через POSITION_5 (enum MatchPlayerPositionType)
- Endpoint: POST https://api.stratz.com/graphql, авторизация Bearer token
- Лимиты: 20 req/sec, 250/min, 2000/hour, 10000/day
- Для skill build (порядок прокачки скиллов) потребуется отдельный запрос через `heroStats.guide` — это будет реализовано в TASK-015 (сервис билдов)
- Следующие разблокированные задачи: TASK-013 (мета-сервис, зависит от 007+003), TASK-015 (билд-сервис, зависит от 007+003)
- Приоритетные critical задачи с выполненными зависимостями: TASK-010 (middleware), TASK-011 (клавиатуры), TASK-013 (мета-сервис), TASK-015 (билд-сервис)

---

## 2026-03-01 — TASK-010: Middleware: auth, subscription, throttle (DONE)

**Что сделано:**
- `bot/middlewares/auth.py` — AuthMiddleware: загружает пользователя по telegram_id из Supabase через UserRepository, инжектит в data['user']. Если не найден — data['user'] = None. Поддержка DI через конструктор (user_repo). Извлечение telegram_id из Update (message, callback_query, inline_query) и прямых событий.
- `bot/middlewares/subscription.py` — SubscriptionMiddleware: проверяет is_premium и premium_expires_at, инжектит data['is_premium']. Зависит от AuthMiddleware (ожидает data['user']). Поддержка str и datetime для expires_at, обработка невалидных значений.
- `bot/middlewares/throttle.py` — ThrottleMiddleware: in-memory rate limiter по telegram_id. Хранит dict {telegram_id: [timestamps]}, отклоняет при превышении лимита. Отправляет предупреждение пользователю. Настраиваемые rate_limit и window_sec.
- Middleware зарегистрированы в `bot/__main__.py`: throttle → auth → subscription (throttle первым для отсечения спама до запросов в БД).
- `tests/test_middlewares.py` — 25 тестов: извлечение telegram_id (4), AuthMiddleware (4), SubscriptionMiddleware (11), ThrottleMiddleware (6).
- Исправлены ошибки сортировки импортов (ruff I001).

**Тест-шаги:**
- Шаг 1: Зарегистрированный пользователь — data['user'] заполнен ✅ (test_registered_user_loaded)
- Шаг 2: Незарегистрированный — data['user'] = None ✅ (test_unregistered_user_none)
- Шаг 3: 3 запроса при лимите 3, 4-й заблокирован ✅ (test_over_limit_blocks)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 156/156 тестов ✅

**Заметки для следующей итерации:**
- Порядок middleware в outer_middleware: первый зарегистрированный выполняется первым (throttle → auth → subscription)
- Для тестов aiogram — мокаем sys.modules["aiogram"], sys.modules["aiogram.types"] с классами _BaseMiddleware, _Update, _TelegramObject
- isinstance-проверки в middleware работают с мок-объектами через `update.__class__ = Update`
- Следующие разблокированные задачи: TASK-012 (онбординг, зависит от 008+010+011), TASK-032 (подписки, зависит от 005+010), TASK-035 (rate limiting, зависит от 010)
- Приоритетные critical задачи с выполненными зависимостями: TASK-011 (клавиатуры), TASK-013 (мета-сервис), TASK-015 (билд-сервис)

---

## 2026-03-01 — TASK-011: Клавиатуры: главное меню, выбор ролей, общие кнопки, герои с пагинацией (DONE)

**Что сделано:**
- `bot/keyboards/menu.py` — reply-клавиатура 3x2 главного меню (Анализ драфта, Герои меты, Разбор матча, Билд героя, Мой профиль, Настройки). Константы `BTN_*` и кортеж `ALL_MENU_BUTTONS` для роутинга в хендлерах. `resize_keyboard=True`, `input_field_placeholder`.
- `bot/keyboards/roles.py` — inline-клавиатура из 5 кнопок (Керри / Мидер / Оффлейнер / Софт-саппорт / Хард-саппорт) с callback_data `role:{1-5}`. Функция `parse_role_callback()` для парсинга.
- `bot/keyboards/common.py` — общие inline-кнопки: Назад (`common:back`), Отмена (`common:cancel`), Подтвердить (`common:confirm`). Готовые клавиатуры `confirm_cancel_kb()` и `back_kb()`.
- `bot/keyboards/heroes.py` — генерация inline-кнопок из списка героев с пагинацией. `HeroButton` dataclass, `PAGE_SIZE=8`, кнопки по 2 в ряд, навигация «Назад»/«Далее». Парсеры `parse_hero_callback()` и `parse_hero_page_callback()`. Защита от невалидных страниц (clamping).
- `tests/test_keyboards.py` — 29 тестов: MainMenu (6), RoleSelection (5), CommonButtons (5), HeroListKb (9), ParseCallbacks (4).

**Тест-шаги:**
- Шаг 1: `main_menu_kb()` — ReplyKeyboardMarkup с 6 кнопками в 3 рядах по 2 ✅
- Шаг 2: `role_selection_kb()` — InlineKeyboardMarkup с 5 кнопками (role:1..role:5), тексты на русском ✅
- Шаг 3: `hero_list_kb(heroes, page=0)` — первая страница с кнопкой «Далее», без «Назад» ✅
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 185/185 тестов ✅

**Заметки для следующей итерации:**
- Моки aiogram в тестах должны включать все типы, используемые другими тестами (BaseMiddleware, TelegramObject, Update), чтобы работать при любом порядке сбора тестов
- Константы кнопок меню (`BTN_DRAFT`, `BTN_META` и т.д.) экспортируются для использования в роутинге хендлеров (TASK-023)
- Приоритетные задачи с выполненными зависимостями: TASK-008 (Steam клиент, high), TASK-013 (мета-сервис, critical), TASK-015 (билд-сервис, critical), TASK-012 (онбординг — зависит от 008+010+011, всё кроме 008 done)

---

## 2026-03-01 — TASK-008: Клиент Steam API: валидация Steam URL/ID, проверка открытости профиля (DONE)

**Что сделано:**
- `clients/steam.py` — класс `SteamClient` для валидации Steam URL/ID и проверки открытости профиля:
  - `resolve_steam_id(raw_input)` — парсинг и resolve любого формата Steam-ввода в Steam ID 64-bit
  - `check_profile_open(steam_id_64)` — проверка открытости профиля через OpenDota API, бросает `SteamProfileClosed`
  - `get_persona_name(steam_id_64)` — получение никнейма из OpenDota
  - `resolve_and_validate(raw_input)` — полный flow: парсинг → resolve → проверка → никнейм
- Парсинг форматов: `_parse_steam_input()` поддерживает:
  - Числовой Steam ID 64-bit (76561198xxxxxxxxx)
  - Числовой account_id 32-bit (автоконвертация)
  - URL: `steamcommunity.com/profiles/76561198xxxxxxxxx`
  - URL: `steamcommunity.com/id/nickname` (с и без https://)
  - Просто vanity name
- Вспомогательные функции: `steam_id_64_to_account_id()`, `account_id_to_steam_id_64()`
- Resolve vanity URL через Steam Web API (`ISteamUser/ResolveVanityURL/v1/`), требует STEAM_API_KEY
- Context manager поддержка (`async with SteamClient() as client:`)
- `tests/test_steam.py` — 31 тест: конвертация ID (3), парсинг ввода (11), resolve_steam_id (6), check_profile_open (3), resolve_and_validate (3), get_persona_name (2), context manager (3)

**Тест-шаги:**
- Шаг 1: `steamcommunity.com/id/dendi` → resolve → числовой Steam ID 64-bit ✅ (test_resolve_vanity_url_success)
- Шаг 2: `steamcommunity.com/profiles/76561198047104768` → парсинг → тот же формат ✅ (test_resolve_profiles_url)
- Шаг 3: Закрытый профиль → `SteamProfileClosed` ✅ (test_closed_profile_raises)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 216/216 тестов ✅

**Заметки для следующей итерации:**
- Для resolve vanity URL нужен STEAM_API_KEY. Без ключа — только числовые Steam ID и URL формата /profiles/
- Steam ID 64-bit начинается с 7 (76561197...), account_id — до 10 цифр. Разница: `_STEAM_ID_64_BASE = 76561197960265728`
- `resolve_and_validate()` — рекомендуемый метод для онбординга (TASK-012): парсинг + resolve + проверка + никнейм за минимум запросов
- TASK-012 (онбординг) теперь полностью разблокирован (зависимости: 008 ✅, 010 ✅, 011 ✅)
- Приоритетные задачи с выполненными зависимостями: TASK-012 (онбординг, critical), TASK-013 (мета-сервис, critical), TASK-015 (билд-сервис, critical)

---

## 2026-03-01 — TASK-012: Онбординг: /start, привязка Steam, ввод MMR и роли (DONE)

**Что сделано:**
- `bot/states/onboarding.py` — FSM-состояния онбординга: `waiting_steam_id`, `confirming_nickname`, `waiting_mmr`, `waiting_role`
- `bot/handlers/start.py` — полный FSM-диалог онбординга через роутер aiogram:
  - `cmd_start()` — точка входа: если пользователь зарегистрирован → главное меню, иначе → онбординг
  - `process_steam_id()` — приём Steam ID/URL, валидация через `SteamClient.resolve_and_validate()`, обработка SteamProfileClosed
  - `confirm_nickname()` / `cancel_nickname()` — подтверждение никнейма из Steam (inline-кнопки)
  - `process_mmr()` — ввод MMR (валидация 0-15000)
  - `process_role()` — выбор роли (inline-клавиатура 5 кнопок), создание профиля в Supabase через `UserRepository.create()`
- Обработка ошибок: закрытый профиль (инструкция как открыть), невалидный Steam ID, дублирование аккаунта, ошибки API/БД
- `STEAM_API_KEY` добавлен в `bot/config.py` и `.env.example`
- Роутер `start_router` зарегистрирован в `bot/__main__.py`
- `tests/test_onboarding.py` — 21 тест покрывающий все шаги онбординга:
  - cmd_start: существующий пользователь (3 теста), новый пользователь (1 тест)
  - process_steam_id: валидный ID, закрытый профиль, невалидный ID, пустой текст, ошибка API (5 тестов)
  - confirm/cancel nickname (2 теста)
  - process_mmr: валидный, 0, 15000, отрицательный, >15000, нечисловой (6 тестов)
  - process_role: создание профиля, дубликат, невалидная роль, ошибка БД (4 теста)

**Тест-шаги:**
- Шаг 1: /start новому пользователю → приветствие + запрос Steam ID ✅ (test_new_user_starts_onboarding)
- Шаг 2: Валидный Steam ID → подтверждение никнейма ✅ (test_valid_steam_id)
- Шаг 3: Подтверждение → MMR → роль → главное меню ✅ (test_confirm_asks_mmr, test_valid_mmr, test_valid_role_creates_user)
- Шаг 4: Повторный /start → сразу главное меню ✅ (test_existing_user_shows_main_menu)
- Шаг 5: Невалидный Steam ID → сообщение об ошибке ✅ (test_invalid_steam_id)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 237/237 тестов ✅

**Заметки для следующей итерации:**
- Мок Router должен использовать `_PassthroughDecorator` (возвращает функцию без изменений) вместо MagicMock, чтобы `asyncio.run()` мог вызывать handler-функции
- Мок `aiogram.types` должен дополнять существующий модуль (`if not hasattr`), а не создавать новый, чтобы работать при любом порядке сбора тестов
- Мок `supabase` должен содержать `AsyncClient` и `create_async_client` на верхнем уровне модуля (помимо `supabase._async.client`)
- Разблокированные задачи: TASK-014 (хендлер /meta), TASK-016 (хендлер /build), TASK-018 (хендлер /lastmatch), TASK-020 (хендлер /profile), TASK-021 (хендлер /settings), TASK-023 (роутинг меню), TASK-034 (валидация)
- Приоритетные задачи с выполненными зависимостями: TASK-013 (мета-сервис, critical), TASK-015 (билд-сервис, critical), TASK-014 (хендлер /meta, critical — зависит от 013+012)

---

## 2026-03-01 — TASK-013: Сервис мета-героев: топ герои по роли и рангу из Stratz (DONE)

**Что сделано:**
- `services/meta.py` — async функция `get_meta_heroes(role, bracket, *, stratz, opendota, account_id, top_n)`:
  - Получение мета-героев из Stratz API по роли и ранговому брекету
  - Модель `MetaHero`: hero_id, name_ru, name_en, winrate, pick_rate, match_count, personal_winrate, personal_games
  - Обогащение личным винрейтом из OpenDota (если передан account_id)
  - In-memory кэш с TTL 1 час (`_cache` dict с timestamp)
  - Функция `invalidate_meta_cache()` для ручного сброса
  - Функция `mmr_to_bracket(mmr)` для определения ранга по MMR
  - Сортировка по винрейту (убывание), ограничение top_n
  - Пропуск неизвестных hero_id (graceful degradation)
- `_build_meta_list()` — построение MetaHero из MetaHeroStats с расчётом pick_rate
- `_enrich_with_personal()` — обогащение личной статистикой из OpenDota
- `tests/services/test_meta.py` — 28 тестов:
  - mmr_to_bracket: 8 тестов (все ранги от Herald до Immortal)
  - _build_meta_list: 8 тестов (сортировка, pick_rate, имена, top_n, пустой ввод, неизвестные ID)
  - _enrich_with_personal: 3 теста (обогащение, None для отсутствующих, сохранение мета-данных)
  - get_meta_heroes: 8 тестов (возврат, винрейт, имена на русском, кэширование, разные параметры, обогащение OpenDota, без account_id, top_n)
  - invalidate_meta_cache: 1 тест

**Тест-шаги:**
- Шаг 1: `get_meta_heroes(role=1, bracket='LEGEND')` — получить 5-10 героев ✅ (test_returns_meta_heroes)
- Шаг 2: Проверить что winrate > 0 и имя на русском заполнено ✅ (test_winrate_positive, test_names_in_russian)
- Шаг 3: Повторный вызов с теми же параметрами — результат из кэша (API вызван 1 раз) ✅ (test_caching_second_call_no_api)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 265/265 тестов ✅

**Заметки для следующей итерации:**
- Сервис принимает клиенты Stratz/OpenDota через параметры (DI), не создаёт их сам
- Кэш хранит MetaHero без personal_winrate — личная статистика добавляется при каждом запросе
- `mmr_to_bracket()` использует приблизительные пороги MMR (Valve не публикует точные)
- Приоритетные задачи с выполненными зависимостями: TASK-015 (билд-сервис, critical), TASK-014 (хендлер /meta, critical — зависит от 013+012)

---

## 2026-03-01 — TASK-014: Хендлер /meta: выбор роли и вывод списка мета-героев (DONE)

**Что сделано:**
- `core/formatting.py` — функция `format_meta_heroes(heroes, role_label)`:
  - Форматирование списка мета-героев в HTML для Telegram (parse_mode="HTML")
  - Нумерация, винрейт/пикрейт/кол-во матчей, личная статистика (если есть)
  - Ограничение длины до 4096 символов (лимит Telegram)
- `bot/handlers/meta.py` — роутер `meta_router` с 3 хендлерами:
  - `cmd_meta()` — команда `/meta [роль]`: без аргумента — клавиатура выбора роли; с аргументом (carry/mid/керри/2) — сразу список героев
  - `btn_meta()` — кнопка «Герои меты» из главного меню → выбор роли
  - `process_meta_role()` — callback обработка выбора роли → вывод мета-героев
  - `_show_meta_heroes()` — общая логика: получение героев из Stratz, обогащение OpenDota, форматирование, inline-кнопки героев для перехода к билду
- Отдельный callback prefix `meta_role:` (не конфликтует с `role:` из онбординга)
- Парсинг роли из текста: поддержка EN/RU/числа (`_ROLE_ALIASES`)
- Обработка ошибок: API недоступен → информативное сообщение; незарегистрированный пользователь → предложение /start
- Роутер зарегистрирован в `bot/__main__.py`
- `tests/test_meta_handler.py` — 32 теста:
  - format_meta_heroes: 6 тестов (пустой список, герои с/без личной стат., HTML-теги, длина, нумерация)
  - _parse_role_from_text: 8 тестов (EN/RU/числа, регистр, пробелы, неизвестные)
  - _parse_meta_role_callback: 4 теста (валидные/невалидные)
  - cmd_meta: 5 тестов (незарегистрированный, без аргумента, с аргументом EN/RU, невалидный аргумент)
  - btn_meta: 2 теста (зарегистрированный/незарегистрированный)
  - process_meta_role: 3 теста (незарегистрированный, невалидная роль, валидная роль)
  - _show_meta_heroes: 4 теста (успешный вывод, ошибка API, без steam_id, пустой список)

**Тест-шаги:**
- Шаг 1: Кнопка «Герои меты» → клавиатура выбора роли ✅ (test_shows_role_keyboard)
- Шаг 2: Выбрать «Carry» → список героев с винрейтами ✅ (test_valid_role_calls_show, test_shows_heroes)
- Шаг 3: Нажать на героя → inline-кнопки героев генерируются (переход к билду — TASK-016) ✅ (test_shows_heroes)
- Шаг 4: `/meta mid` → герои для мида без доп. шагов ✅ (test_with_role_arg_shows_heroes)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 297/297 тестов ✅

**Заметки для следующей итерации:**
- Используется отдельный prefix `meta_role:` вместо `role:` чтобы не конфликтовать с FSM-состоянием онбординга (callback_data `role:` ловится в OnboardingStates.waiting_role)
- `_show_meta_heroes()` создаёт StratzClient/OpenDotaClient внутри, а не принимает через DI — это упрощает хендлер, но затрудняет мокирование (нужно патчить классы)
- `core/formatting.py` создан и может быть расширен для других фич (format_build, format_match_analysis и т.д. — TASK-038)
- Приоритетные задачи с выполненными зависимостями: TASK-009 (LLM клиент, critical), TASK-015 (сервис билдов, critical), TASK-017 (анализ матча, high)
