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

---

## 2026-03-02 — TASK-015: Сервис билдов: item build и skill build героя из Stratz (DONE)

**Что сделано:**
- `core/items.py` — маппинг предметов Dota 2 (item_id → ItemData с name_en/name_ru):
  - 150+ предметов: расходники, базовые, ботинки, основные, крупные, нейтральные
  - `ITEM_BY_ID` индекс для быстрого поиска
  - `get_item_name_en(item_id)` / `get_item_name_ru(item_id)` — fallback на "Item #ID" / "Предмет #ID" для неизвестных
- `clients/stratz.py` — расширен новыми моделями и методом:
  - Модели: `AbilityInfo`, `TalentInfo`, `HeroGuideData` (ability_order, talents, winrate)
  - GraphQL запрос `QUERY_HERO_GUIDE` — получение гайда героя (порядок прокачки скиллов и таланты)
  - Метод `get_hero_guide(hero_id, role, bracket)` → `HeroGuideData`
- `services/build.py` — async функция `get_hero_build(hero_id, role, bracket, *, stratz)`:
  - Модель `HeroBuild`: hero_id, name_en/name_ru, starting_items, core_items, situational_items, skill_order, talents, guide_winrate
  - Модель `BuildItem`: item_id, name_en/name_ru, winrate, match_count, time
  - Модель `SkillSlot`: ability_id, slot (0-3: Q/W/E/R)
  - Модель `TalentChoice`: ability_id, slot, winrate, match_count
  - Получение данных из Stratz API: item build (purchasePattern) + guide (abilityMaxOrder, talent)
  - core_items = early_game + mid_game (до 6 шт.), situational = остальные + late_game
  - Дедупликация предметов (по item_id, сохраняя порядок)
  - In-memory кэш с TTL 1 час, `invalidate_build_cache()`
- `tests/services/test_build.py` — 34 теста:
  - _convert_items: 5 тестов (имена, винрейт, время, пустой, неизвестный ID)
  - _convert_talents: 4 теста (конвертация, сортировка, винрейт, пустой)
  - _assemble_build: 9 тестов (hero_build, starting, core, situational, дубликаты, скиллы, таланты, guide_winrate, пустые данные)
  - get_hero_build: 10 тестов (возврат, параметры, кэширование, инвалидация)
  - invalidate_build_cache: 1 тест
  - ItemMapping: 5 тестов (EN/RU имена, неизвестные, tango)

**Тест-шаги:**
- Шаг 1: `get_hero_build(hero_id=1, role=1, bracket='LEGEND')` — получить полный билд ✅ (test_returns_hero_build, test_calls_stratz_with_params)
- Шаг 2: starting_items, core_items, skill_order заполнены ✅ (test_starting_items_filled, test_core_items_filled, test_skill_order_filled)
- Шаг 3: situational_items содержат late_game предметы ✅ (test_situational_items_from_late)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 331/331 тестов ✅

**Заметки для следующей итерации:**
- Stratz API guide запрос: `heroStats.guide` возвращает `abilityMaxOrder` (порядок макса скиллов) и `talent` (выбранные таланты с винрейтами)
- `get_hero_build()` принимает `stratz` через параметр (DI), не создаёт клиент внутри
- core_items ограничены 6 штуками (стартовые считаются отдельно) — early + mid game
- Маппинг предметов `core/items.py` — fallback на "Item #ID" для неизвестных item_id, что обеспечивает graceful degradation
- Кэш билдов отдельный от кэша мета-героев, TTL тоже 1 час
- Разблокированные задачи: TASK-016 (хендлер /build, зависит от 015+012)
- Приоритетные задачи с выполненными зависимостями: TASK-009 (LLM клиент, high), TASK-016 (хендлер /build, critical), TASK-017 (анализ матча, high), TASK-021 (настройки, high), TASK-022 (помощь, high), TASK-023 (роутинг меню, high)

---

## 2026-03-02 — TASK-016: Хендлер /build: ввод героя текстом, вывод полного билда (DONE)

**Что сделано:**
- `bot/states/build.py` — FSM-состояние `BuildStates.waiting_hero_name` для ожидания текстового ввода героя
- `bot/handlers/build.py` — роутер `build_router` с 4 хендлерами:
  - `cmd_build()` — команда `/build [герой]`: с аргументом — сразу билд; без аргумента — запрос ввода (FSM)
  - `btn_build()` — кнопка «Билд героя» из главного меню → запрос ввода героя
  - `process_hero_name()` — FSM-обработка текстового ввода героя (EN/RU/сокращения)
  - `process_hero_callback()` — обработка inline-кнопки героя (например, из /meta) → показ билда
- `_resolve_and_show_build()` — поиск героя через `find_hero()` (поддержка am, qop, Антимаг и т.д.), сброс FSM, вызов `_show_build()`
- `_show_build()` — получение билда из Stratz API через `get_hero_build()`, форматирование через `format_build()`, отправка в HTML parse_mode
- `core/formatting.py` — функция `format_build(build)`:
  - Секции: стартовые предметы, основные (с нумерацией, винрейтом, временем), ситуативные, прокачка скиллов (Q/W/E/R), таланты
  - Эмодзи для разделения секций (🛡🟢🔵🟡📘⭐)
  - Ограничение 4096 символов (лимит Telegram)
  - Винрейт гайда в заголовке
- Роутер `build_router` зарегистрирован в `bot/__main__.py`
- Обработка ошибок: незарегистрированный пользователь → /start, неизвестный герой → «не найден», ошибка API → информативное сообщение
- `tests/test_build_handler.py` — 33 теста:
  - format_build: 12 тестов (заголовок, винрейт, стартовые/основные/ситуативные предметы, скиллы, таланты, HTML, длина, пустой билд, нулевой винрейт)
  - cmd_build: 4 теста (незарегистрированный, без аргумента, с EN аргументом, с RU аргументом)
  - btn_build: 2 теста (незарегистрированный/зарегистрированный)
  - process_hero_name: 3 теста (незарегистрированный, пустой текст, валидный герой)
  - process_hero_callback: 4 теста (незарегистрированный, невалидный ID, валидный ID, неизвестный hero_id)
  - _resolve_and_show_build: 4 теста (валидное имя, алиас, русское имя, неизвестный герой)
  - _show_build: 4 теста (успешный вывод, использование MMR, ошибка API, отсутствие MMR)

**Тест-шаги:**
- Шаг 1: `/build Anti-Mage` → полный билд ✅ (test_with_hero_arg_shows_build, test_shows_build_successfully)
- Шаг 2: `/build Антимаг` → тот же результат ✅ (test_with_russian_hero_arg, test_russian_name)
- Шаг 3: Кнопка «Билд героя» → ввод «am» → билд ✅ (test_shows_hero_input_prompt, test_valid_hero_calls_resolve, test_valid_alias)
- Шаг 4: Ввод несуществующего героя → «Герой не найден» ✅ (test_unknown_hero)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 364/364 тестов ✅

**Заметки для следующей итерации:**
- Хендлер `process_hero_callback` (prefix `hero:`) обрабатывает inline-кнопки героев из /meta — переход к билду при нажатии на героя в списке мета
- `_show_build()` использует `main_role` из профиля пользователя и `mmr_to_bracket()` для определения ранга
- Все pending задачи с выполненными зависимостями (критических нет):
  - TASK-009 (LLM клиент, high, deps: 001 ✅)
  - TASK-017 (анализ матча, high, deps: 006+005+003 ✅)
  - TASK-019 (профиль, high, deps: 006+005 ✅)
  - TASK-021 (настройки, high, deps: 012 ✅)
  - TASK-022 (помощь, high, deps: 001 ✅)
  - TASK-023 (роутинг меню, high, deps: 012+011 ✅)
  - TASK-034 (валидация, high, deps: 012 ✅)
  - TASK-035 (rate limiting, high, deps: 010 ✅)

---

## 2026-03-02 — TASK-017: Сервис анализа матча: базовый разбор с метриками по ролям (DONE)

**Что сделано:**
- `services/match_analysis.py` — async функция `analyze_last_match(steam_id, *, opendota, match_repo, user_id, user_role)`:
  - Модель `MatchAnalysis`: match_id, hero_id, hero_name_ru/en, role, role_detected, duration_sec, result, kills/deaths/assists, metrics, player_stats
  - Модель `RoleMetric`: name, label_ru, value, median, unit + свойства diff и diff_pct
  - Автоопределение роли по `lane_role` + `is_roaming` + `last_hits/min` из OpenDota (`_detect_role()`)
  - Различение carry/hard support на safe lane по last_hits/min (порог 3 LH/мин)
  - Различение offlane/soft support на off lane по last_hits/min
  - Fallback на user_role → CARRY если автоопределение не сработало
- Метрики фильтруются по роли (`_ROLE_METRICS`):
  - Carry/Mid: GPM, XPM, ластхиты, урон героям, урон строениям
  - Offlane: GPM, XPM, урон героям, урон строениям, оглушение
  - Soft/Hard Support: обсервер/сентри варды, лечение, ассисты, оглушение
- Сравнение с медианой (`_MEDIAN_VALUES`): приблизительные медианы для Legend ранга
  - Масштабирование медианы по длительности матча (GPM/XPM не масштабируются)
- Сохранение результата в match_analyses через `MatchAnalysisRepository.insert()` (если переданы repo + user_id)
- Конвертация Steam ID 64-bit → account_id 32-bit через `steam_id_64_to_account_id()`
- `tests/services/test_match_analysis.py` — 47 тестов:
  - _detect_role: 8 тестов (carry, support, mid, offlane, roaming, no lane_role, unknown)
  - _determine_result: 4 теста (radiant/dire × win/loss)
  - _find_player_in_match: 3 теста (найден, не найден, пустой список)
  - _scale_median_by_duration: 5 тестов (GPM не масштабируется, масштабирование к 60мин/15мин/30мин)
  - _build_metrics: 6 тестов (carry-метрики, support-метрики, значения, медианы)
  - RoleMetric: 4 теста (diff, diff_pct, zero median)
  - analyze_last_match: 17 тестов (возврат, герой, роль, результат, метрики, KDA, ошибки, fallback, сохранение в БД)

**Тест-шаги:**
- Шаг 1: `analyze_last_match(steam_id)` — получить MatchAnalysis ✅ (test_returns_match_analysis)
- Шаг 2: Роль определена автоматически (lane_role=1, high CS → CARRY) ✅ (test_role_detected_as_carry)
- Шаг 3: Carry — метрики GPM/XPM/LH; нет obs_placed ✅ (test_metrics_for_carry, test_carry_no_wards)
- Шаг 4: Медианы масштабированы по длительности ✅ (test_median_scaled_for_long_match, test_median_comparison_present)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 411/411 тестов ✅

**Заметки для следующей итерации:**
- Медианы в `_MEDIAN_VALUES` — приблизительные для Legend, в будущем можно брать из API (Stratz/OpenDota)
- `analyze_last_match()` принимает зависимости через параметры (DI): opendota, match_repo, user_id
- При моке supabase в тестах необходимо мокать `sys.modules["supabase"]` и `sys.modules["bot.config"]` до импорта сервиса
- Разблокированные задачи: TASK-018 (хендлер /lastmatch, зависит от 017+012), TASK-028 (LLM-совет, зависит от 017+009+024), TASK-039 (тесты, зависит от 017+013)
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-009 (LLM клиент, deps: 001 ✅)
  - TASK-018 (хендлер /lastmatch, deps: 017+012 ✅)
  - TASK-019 (профиль, deps: 006+005 ✅)
  - TASK-021 (настройки, deps: 012 ✅)
  - TASK-022 (помощь, deps: 001 ✅)
  - TASK-023 (роутинг меню, deps: 012+011 ✅)
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)

---

## 2026-03-02 — TASK-018: Хендлер /lastmatch: вывод разбора последнего матча (DONE)

**Что сделано:**
- `core/formatting.py` — функция `format_match_analysis(analysis)`:
  - Форматирование анализа матча в HTML для Telegram (parse_mode="HTML")
  - Заголовок с ID матча, результат (✅ Победа / ❌ Поражение), длительность
  - Герой, роль, KDA
  - Метрики по роли с медианой и цветовым индикатором (🟢 выше / 🔴 ниже медианы)
  - Для deaths — инвертированная логика (ниже = лучше)
  - Числа >= 1000 форматируются с пробелом (28 000)
  - Ограничение 4096 символов (лимит Telegram)
- `bot/handlers/match.py` — роутер `match_router` с 3 хендлерами:
  - `cmd_lastmatch()` — команда `/lastmatch`: разбор последнего матча
  - `btn_match()` — кнопка «Разбор матча» из главного меню
  - `process_ai_advice()` — callback для кнопки AI-совета (заглушка до TASK-028)
- `_show_last_match()` — общая логика:
  - Показ сообщения о загрузке «⏳ Анализирую последний матч…»
  - Получение анализа из `services/match_analysis.analyze_last_match()`
  - Сохранение в БД через `MatchAnalysisRepository` (если user_id есть)
  - Для premium: inline-кнопка «💡 Получить совет от AI» (callback `ai_advice:{match_id}`)
  - Для free: текст о доступности AI-совета для Premium-подписчиков
  - Обработка ошибок: нет матчей, ошибка API, невалидный Steam ID
- `_get_user_role()` — извлечение роли из профиля пользователя (с валидацией)
- Роутер `match_router` зарегистрирован в `bot/__main__.py`
- `tests/test_match_handler.py` — 38 тестов:
  - format_match_analysis: 16 тестов (match_id, герои, победа/поражение, длительность, KDA, роль, метрики, медиана, зелёный/красный, HTML, длина, пустые метрики, большие числа, саппорт)
  - _get_user_role: 5 тестов (валидная 1/5, None, отсутствует, невалидная)
  - cmd_lastmatch: 3 теста (незарегистрированный, зарегистрированный, premium)
  - btn_match: 2 теста (незарегистрированный/зарегистрированный)
  - process_ai_advice: 3 теста (незарегистрированный, не premium, premium заглушка)
  - _show_last_match: 9 тестов (нет steam_id, невалидный steam_id, вывод анализа, premium кнопка, нет матчей, ошибка API, сообщение загрузки, пользователь без id в БД, метрики соответствуют роли)

**Тест-шаги:**
- Шаг 1: `/lastmatch` → разбор последнего матча с метриками ✅ (test_shows_analysis)
- Шаг 2: Метрики соответствуют роли (carry → GPM/XPM, нет вардов) ✅ (test_metrics_match_role)
- Шаг 3: Для premium — видна кнопка «Получить совет от AI» ✅ (test_premium_gets_button)
- Шаг 4: Для free — видно сообщение о подписке ✅ (test_shows_analysis — Premium в тексте)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 449/449 тестов ✅

**Заметки для следующей итерации:**
- Кнопка AI-совета (`ai_advice:{match_id}`) — заглушка до реализации TASK-028 (LLM-совет)
- `_show_last_match()` создаёт OpenDotaClient и MatchAnalysisRepository внутри (как в хендлере build)
- Для free-пользователей текст о Premium добавляется к основному сообщению (не кнопка)
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-009 (LLM клиент, deps: 001 ✅)
  - TASK-019 (профиль, deps: 006+005 ✅)
  - TASK-021 (настройки, deps: 012 ✅)
  - TASK-022 (помощь, deps: 001 ✅)
  - TASK-023 (роутинг меню, deps: 012+011 ✅)
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)

---

## 2026-03-02 — TASK-019: Сервис профиля: агрегация статистики пользователя (DONE)

**Что сделано:**
- `services/profile.py` — async функция `get_user_profile(user, *, opendota, mmr_repo)`:
  - Модель `UserProfile`: current_mmr, rank_bracket, main_role, overall_winrate, top_heroes, winrate_7d, winrate_30d, win_streak, loss_streak, mmr_history, total_matches, personaname
  - Модель `TopHero`: hero_id, name_ru, name_en, games, winrate
  - Модель `MmrPoint`: mmr, recorded_at
  - Общий винрейт из статистики героев OpenDota (`_calc_overall_winrate()`)
  - Топ-5 героев по кол-ву игр с винрейтами (`_build_top_heroes()`)
  - Винрейт за 7 и 30 дней из последних 100 матчей (`_calc_recent_winrate()`)
  - Текущая серия побед/поражений (`_calc_streaks()`)
  - Динамика MMR из mmr_history репозитория за 30 дней
  - Ранговый брекет через `mmr_to_bracket()` из сервиса мета
  - Для пользователей без steam_id — минимальный профиль (без API-запросов)
- `tests/services/test_profile.py` — 44 теста:
  - _calc_overall_winrate: 5 тестов (расчёт, пустой, нулевые, тип, диапазон)
  - _build_top_heroes: 10 тестов (top-5, сортировка, имена RU/EN, винрейт, пустые, лимит, неизвестный герой)
  - _calc_recent_winrate: 6 тестов (7/30 дней, пустые, нет свежих, все победы/поражения)
  - _calc_streaks: 6 тестов (серия побед/поражений, пустые, одиночные, чередование)
  - get_user_profile: 17 тестов (возврат, mmr, ранг, роль, винрейт, топ герои, winrate_7d/30d, серии, всего матчей, никнейм, без steam_id, mmr_history, без repo, без mmr, невалидная роль, account_id)

**Тест-шаги:**
- Шаг 1: `get_user_profile(user)` — получить заполненный UserProfile ✅ (test_returns_user_profile)
- Шаг 2: top_heroes содержит до 5 героев с винрейтами ✅ (test_top_heroes_count, test_winrate_calculated)
- Шаг 3: winrate_7d и winrate_30d — числа от 0 до 100 ✅ (test_winrate_7d, test_winrate_30d)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 493/493 тестов ✅

**Заметки для следующей итерации:**
- `get_user_profile()` принимает зависимости через параметры (DI): opendota, mmr_repo
- Для пользователей без steam_id не выполняются API-запросы — возвращается минимальный профиль
- Серия (streak) считается от самого свежего матча — первый матч определяет тип серии
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-020 (хендлер /profile, deps: 019+012 ✅)
  - TASK-021 (настройки, deps: 012 ✅)
  - TASK-022 (помощь, deps: 001 ✅)
  - TASK-023 (роутинг меню, deps: 012+011 ✅)
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)
  - TASK-031 (уведомления, deps: 019+007 ✅)

---

## 2026-03-02 — TASK-020: Хендлер /profile: вывод профиля и статистики пользователя (DONE)

**Что сделано:**
- `core/formatting.py` — функция `format_profile(profile)`:
  - Заголовок с никнеймом (fallback на «Игрок» если нет)
  - MMR и ранговая медаль (эмодзи + русское название ранга)
  - Основная роль на русском
  - Общая статистика: винрейт, кол-во матчей
  - Винрейт за 7 и 30 дней
  - Серия побед/поражений (отображается только если ≥ 2)
  - Динамика MMR за 30 дней (↑/↓/→ с разницей)
  - Топ-5 героев с винрейтами и кол-вом игр
  - Ограничение 4096 символов (лимит Telegram)
  - HTML parse_mode
- `bot/handlers/profile.py` — роутер `profile_router` с 3 хендлерами:
  - `cmd_profile()` — команда `/profile`: вывод профиля
  - `btn_profile()` — кнопка «Мой профиль» из главного меню
  - `process_update_mmr()` — callback для кнопки «Обновить MMR»: получение mmr_estimate из OpenDota, обновление через UserRepository, обновление сообщения с новым профилем
- `_show_profile()` — сообщение загрузки + вывод профиля
- `_show_profile_edit()` — обновление существующего сообщения (после обновления MMR)
- `_build_profile_response()` — общая логика: получение профиля из сервиса, форматирование, inline-кнопка «🔄 Обновить MMR»
- Обработка ошибок: незарегистрированный пользователь → /start, нет Steam → информативное сообщение, ошибка API → fallback текст
- Роутер `profile_router` зарегистрирован в `bot/__main__.py`
- `tests/test_profile_handler.py` — 33 теста:
  - format_profile: 19 тестов (никнейм, MMR, медаль, роль, винрейт общий/7д/30д, матчи, серия побед/поражений, нет серии при 1, топ герои, динамика MMR ↑/↓, HTML, длина, минимальный профиль, fallback никнейм, винрейт героев)
  - cmd_profile: 2 теста (незарегистрированный, зарегистрированный)
  - btn_profile: 2 теста (незарегистрированный, зарегистрированный)
  - process_update_mmr: 5 тестов (незарегистрированный, нет Steam, успешное обновление, ошибка API, нет mmr_estimate)
  - _show_profile: 1 тест (загрузка + профиль)
  - _build_profile_response: 4 теста (текст + клавиатура, ошибка API, герои в профиле, HTML)

**Тест-шаги:**
- Шаг 1: `/profile` → профиль со статистикой ✅ (test_registered_calls_show, test_returns_text_and_keyboard)
- Шаг 2: Кнопка «Обновить MMR» → MMR обновляется ✅ (test_updates_mmr_successfully)
- Шаг 3: Топ-5 героев отображаются ✅ (test_profile_contains_heroes, test_contains_top_heroes)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 526/526 тестов ✅

**Заметки для следующей итерации:**
- `_build_profile_response()` создаёт OpenDotaClient и MmrHistoryRepository внутри
- Кнопка «Обновить MMR» использует callback_data `update_mmr` (без параметров)
- При обновлении MMR обновляется и dict user (для немедленного отображения в обновлённом профиле)
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-021 (настройки, deps: 012 ✅)
  - TASK-022 (помощь, deps: 001 ✅)
  - TASK-023 (роутинг меню, deps: 012+011 ✅)
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)
  - TASK-031 (уведомления, deps: 019+007 ✅)

---

## 2026-03-06 — TASK-022: Хендлер /help: справка по командам и функциям бота (DONE)

**Что сделано:**
- `bot/handlers/help.py` — роутер `help_router` с хендлером `cmd_help()`:
  - Команда `/help` — вывод компактной справки в HTML parse_mode
  - Все 8 команд перечислены: /start, /meta, /build, /lastmatch, /profile, /draft, /settings, /help
  - Описание бесплатных функций: мета-герои, билды, разбор матча, профиль
  - Описание Premium функций: анализ драфта (Vision AI), рекомендации пиков, AI-советы, ситуативные билды, уведомления
  - Текст укладывается в лимит Telegram (4096 символов)
- Роутер `help_router` зарегистрирован в `bot/__main__.py` (до menu_router)
- `tests/test_help_handler.py` — 17 тестов:
  - cmd_help: 2 теста (отправка текста, parse_mode HTML)
  - HELP_TEXT: 13 тестов (наличие всех 8 команд, бесплатные/Premium функции, лимит Telegram, валидный HTML)
  - HelpRouter: 2 теста (существование роутера, импорт)

**Также верифицирован и закрыт TASK-023 (роутинг текстовых кнопок главного меню):**
- BTN_META обрабатывается в meta.py (btn_meta) ✅
- BTN_BUILD обрабатывается в build.py (btn_build) ✅
- BTN_MATCH обрабатывается в match.py (btn_match) ✅
- BTN_PROFILE обрабатывается в profile.py (btn_profile) ✅
- BTN_DRAFT обрабатывается в menu.py (btn_draft — заглушка до TASK-027) ✅
- BTN_SETTINGS обрабатывается в menu.py (btn_settings — заглушка до TASK-021) ✅
- Все хендлеры проверяют регистрацию пользователя (user is None) ✅
- menu_router зарегистрирован последним в __main__.py (ловит оставшиеся тексты) ✅
- Исправлена ошибка сортировки импортов (ruff I001) в test_menu_handler.py ✅

**Тест-шаги TASK-022:**
- Шаг 1: `/help` → список команд с описаниями ✅ (test_sends_help_text)
- Шаг 2: Все 8 команд перечислены ✅ (test_all_eight_commands_listed)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 563/563 тестов ✅

**Заметки для следующей итерации:**
- Хендлер /help не требует регистрации — справка доступна всем пользователям
- Роутер help_router зарегистрирован перед menu_router (порядок важен: menu_router ловит любой текст кнопки)
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-009 (LLM клиент, deps: 001 ✅)
  - TASK-021 (настройки, deps: 012 ✅)
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)
  - TASK-031 (уведомления, medium, deps: 019+007 ✅)

---

## 2026-03-06 — TASK-021: Хендлер /settings: управление уведомлениями, сменой роли, обновлением MMR (DONE)

**Что сделано:**
- `bot/states/settings.py` — FSM-состояния: `waiting_new_mmr`, `waiting_new_steam`
- `bot/handlers/settings.py` — роутер `settings_router` с полным набором хендлеров:
  - `cmd_settings()` — команда `/settings`: показ inline-меню настроек с текущими значениями
  - `btn_settings()` — кнопка «Настройки» из главного меню (перенесена из menu.py)
  - `toggle_notifications()` — переключение уведомлений (callback `settings:toggle_notif`)
  - `change_role_menu()` — показ клавиатуры выбора новой роли (callback `settings:change_role`)
  - `process_role_change()` — обработка выбора роли (prefix `settings_role:`)
  - `update_mmr_settings()` — запрос ввода нового MMR (callback `settings:update_mmr`) → FSM
  - `process_new_mmr()` — обработка ввода MMR (валидация 0-15000), сохранение в Supabase
  - `change_steam_menu()` — запрос нового Steam ID (callback `settings:change_steam`) → FSM
  - `process_new_steam()` — валидация через SteamClient, проверка открытости, сохранение
- `_settings_menu_text()` — текст меню с текущими значениями (уведомления, роль, MMR, Steam ID)
- `_settings_kb()` — inline-клавиатура из 4 кнопок (переключение уведомлений, смена роли, обновление MMR, смена Steam)
- `_role_selection_kb()` — inline-клавиатура выбора роли с prefix `settings_role:` (не конфликтует с `role:` из онбординга)
- Заглушка настроек удалена из `bot/handlers/menu.py`
- Роутер `settings_router` зарегистрирован в `bot/__main__.py` (перед help_router и menu_router)
- Все изменения сохраняются через `UserRepository.update()` / `update_mmr()`
- Обработка ошибок: незарегистрированный пользователь → /start, ошибки БД/API → информативные сообщения
- `tests/test_settings_handler.py` — 48 тестов:
  - _settings_menu_text: 9 тестов (заголовок, уведомления вкл/выкл, роль, MMR, Steam ID, тире для пустых, HTML)
  - _settings_kb: 6 тестов (4 кнопки, текст переключения уведомлений, кнопки роли/MMR/Steam)
  - cmd_settings: 4 теста (незарегистрированный, показ меню, HTML, сброс FSM)
  - btn_settings: 2 теста (незарегистрированный, показ меню)
  - toggle_notifications: 5 тестов (незарегистрированный, выключение, включение, обновление сообщения, ошибка)
  - change_role_menu: 2 теста (незарегистрированный, показ выбора роли)
  - process_role_change: 5 тестов (незарегистрированный, невалидная роль, смена роли, обновление сообщения, ошибка)
  - update_mmr_settings: 2 теста (незарегистрированный, показ ввода MMR)
  - process_new_mmr: 8 тестов (незарегистрированный, не число, отрицательный, >15000, валидный, 0, 15000, ошибка БД)
  - change_steam_menu: 2 теста (незарегистрированный, показ ввода Steam)
  - process_new_steam: 6 тестов (незарегистрированный, пустой ввод, валидный Steam, закрытый профиль, невалидный ID, ошибка API)
  - SettingsRouter: 2 теста (существование роутера, FSM-состояния)
- Обновлён `tests/test_menu_handler.py` — удалены 5 тестов заглушки настроек

**Тест-шаги:**
- Шаг 1: `/settings` → inline-меню настроек с текущими значениями ✅ (test_registered_shows_menu)
- Шаг 2: Выключить уведомления → статус изменился ✅ (test_disables_notifications)
- Шаг 3: Сменить роль → выбор роли через inline-кнопки → сохранение ✅ (test_shows_role_selection, test_changes_role)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 611/611 тестов ✅

**Заметки для следующей итерации:**
- Callback prefix `settings_role:` используется для выбора роли в настройках (не конфликтует с `role:` из онбординга)
- При смене Steam: валидация через SteamClient → обновление steam_id + username в Supabase
- При обновлении MMR: ручной ввод числа (0-15000), не через API — пользователь сам знает свой MMR
- Заглушка для кнопки «Настройки» удалена из menu.py — теперь полноценный хендлер в settings.py
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-009 (LLM клиент, deps: 001 ✅)
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)
  - TASK-031 (уведомления, medium, deps: 019+007 ✅)
  - TASK-030 (scheduler, medium, deps: 004+005+006 ✅)
  - TASK-032 (подписки, medium, deps: 005+010 ✅)

---

## 2026-03-06 — TASK-009: Унифицированный LLM-клиент: интерфейс для Vision и текстовых запросов (DONE)

**Что сделано:**
- `clients/llm.py` — класс `LLMClient` с единым async-интерфейсом для OpenAI и Anthropic:
  - `complete(prompt, system, model, max_tokens, temperature)` — текстовый запрос
  - `vision(image_bytes, prompt, system, model, max_tokens, temperature)` — запрос с изображением (Vision)
  - `summarize_match(stats_dict)` — генерация текстового разбора матча (промпт из `prompts/match_summary.txt`)
  - `recommend_picks(draft_context)` — рекомендация пиков (промпт из `prompts/draft_recommendation.txt`)
  - `recognize_draft(image_bytes)` — распознавание драфта из скриншота через Vision (промпт из `prompts/draft_recognition.txt`)
- Конфигурация провайдеров `_PROVIDER_CONFIG`: OpenAI (gpt-4o-mini) и Anthropic (claude-sonnet-4)
- Загрузка промптов из файлов `prompts/*.txt` через `load_prompt(name)` с fallback на встроенные промпты
- Token-bucket rate limiter (20 запросов/мин)
- Retry логика: до 3 попыток при 429, 5xx и сетевых ошибках с экспоненциальным backoff
- `APIRateLimited` при исчерпании retry на 429
- Context manager поддержка (`async with LLMClient() as client:`)
- Типизированные модели ответов: `LLMResponse`, `DraftRecognition`, `PickRecommendation`
- Парсеры ответов: `_parse_draft_recognition()`, `_parse_pick_recommendations()`
- Исправлены ошибки ruff: E501 (длинная строка), I001 (сортировка импортов), F401 (неиспользуемый импорт tempfile)
- `tests/clients/test_llm.py` — 45 тестов:
  - RateLimiter: 1 тест (acquire без блокировки)
  - load_prompt: 2 теста (отсутствующий/существующий файл)
  - LLMClient init: 6 тестов (openai/anthropic/case insensitive/unknown/external client/own client)
  - Context manager: 3 теста (enter/exit own/exit external)
  - OpenAI complete: 5 тестов (ответ/system/auth/model/без system)
  - Anthropic complete: 4 теста (ответ/x-api-key/system в body/без system)
  - OpenAI/Anthropic Vision: 2 теста (base64 image)
  - Retry: 4 теста (500/429/network error/4xx)
  - summarize_match: 2 теста (строка/stats в промпте)
  - recommend_picks: 2 теста (список/плохой формат)
  - recognize_draft: 1 тест (DraftRecognition)
  - Парсеры: 11 тестов (draft recognition/pick recommendations)
  - Provider switching: 2 теста (URL endpoints)

**Тест-шаги:**
- Шаг 1: Создать LLMClient с тестовым API ключом ✅ (test_creates_with_openai_provider, test_creates_with_anthropic_provider)
- Шаг 2: summarize_match() с тестовыми данными — текстовый ответ ✅ (test_returns_string, test_sends_stats_in_prompt)
- Шаг 3: Смена LLM_PROVIDER — корректное переключение ✅ (test_openai_uses_chat_completions_url, test_anthropic_uses_messages_url)
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run --with httpx pytest tests/ -v` — 656/656 тестов ✅

**Заметки для следующей итерации:**
- Код LLM-клиента и тесты были уже реализованы, потребовалось только исправить ошибки ruff (E501, I001, F401)
- Промпты (`prompts/*.txt`) ещё не созданы — это TASK-024. LLMClient использует fallback промпты если файлов нет
- Разблокированные задачи (зависят от TASK-009):
  - TASK-025 (распознавание драфта, medium, deps: 009+024)
  - TASK-028 (LLM-совет по матчу, medium, deps: 017+009+024)
  - TASK-029 (ситуативные билды, medium, deps: 015+009+024)
- Приоритетные pending задачи с выполненными зависимостями (high):
  - TASK-034 (валидация, deps: 012 ✅)
  - TASK-035 (rate limiting, deps: 010 ✅)
- Приоритетные pending задачи (medium, deps выполнены):
  - TASK-024 (LLM-промпты, deps: 003 ✅) — блокирует TASK-025, 028, 029
  - TASK-030 (scheduler, deps: 004+005+006 ✅)
  - TASK-031 (уведомления, deps: 019+007 ✅)
  - TASK-032 (подписки, deps: 005+010 ✅)

---

## 2026-03-06 — Первый запуск бота: исправление runtime-ошибок и совместимости с API (DONE)

**Что сделано:**

Бот впервые запущен в боевом режиме. Обнаружены и исправлены множественные проблемы совместимости между написанным кодом и актуальными версиями зависимостей/API.

### 1. Установка зависимостей
- `pip install httpx apscheduler` — отсутствовали в системе
- `pip install "httpx[http2]"` — пакет `h2` требовался для Supabase (http2=True)
- `pip install supabase --no-deps` + ручная установка субзависимостей — обход `pyiceberg` (требует Visual C++ Build Tools, отсутствует)
- Создана заглушка `pyiceberg` в site-packages — модуль `storage3` импортирует `pyiceberg.catalog.rest.RestCatalog` при старте, но для работы бота storage не используется

### 2. Фикс postgrest 2.28: maybe_single() возвращает None
- **Проблема:** `postgrest` 2.28 изменил поведение `.maybe_single().execute()` — возвращает `None` (не объект с `.data`) когда запись не найдена. Старый код вызывал `response.data` → `AttributeError: 'NoneType' object has no attribute 'data'`
- **Исправлено в:** `repositories/user.py` (2 места), `repositories/match_analysis.py` (1), `repositories/subscription.py` (1)
- Добавлена проверка `if response is None: return None` перед обращением к `.data`

### 3. RLS-политики Supabase: разрешение доступа для anon-роли
- **Проблема:** RLS-политики были настроены через `auth.uid()` (Supabase Auth JWT), но бот использует `anon` ключ без Supabase Auth → `auth.uid()` = NULL → все операции блокировались (INSERT 401, SELECT 406)
- **Решение:** Применена миграция `allow_anon_full_access` — добавлены RLS-политики для `anon` роли на все 5 таблиц (SELECT/INSERT/UPDATE)

### 4. Cloudflare блокирует Stratz API
- **Проблема:** Stratz API за Cloudflare challenge ("Just a moment..."), httpx-запросы из Python блокируются (403), хотя браузер проходит
- **Решение:** Интегрирован `cloudscraper` — замена httpx на cloudscraper в `StratzClient._query()` через `asyncio.to_thread()` (cloudscraper синхронный)
- `pip install cloudscraper`
- `clients/stratz.py`: добавлен `import cloudscraper`, `self._scraper = cloudscraper.create_scraper()`, метод `_sync_query()`, переписан `_query()` с `asyncio.to_thread`

### 5. Обновление Stratz GraphQL API (схема изменилась)
- **Два типа enum-ов рангов:**
  - `RankBracket` — одиночные (`HERALD`, `LEGEND`, `ANCIENT`) — используется в `winWeek`
  - `RankBracketBasicEnum` — парные (`HERALD_GUARDIAN`, `LEGEND_ANCIENT`) — используется в `stats`, `itemStartingPurchase`, `itemFullPurchase`
- Добавлен `RANK_TO_STRATZ_BRACKET_BASIC` маппинг (парные), `RANK_TO_STRATZ_BRACKET` обновлён на одиночные
- **QUERY_META_HEROES:** тип переменной `$bracketIds` изменён с `[RankBracketBasicEnum]` на `[RankBracket]`
- **QUERY_HERO_BUILD:** полностью переписан — старый `stats.purchasePattern` удалён из API, заменён на `itemStartingPurchase` + `itemFullPurchase` (отдельные top-level поля `HeroStatsQuery`). Переменная `$positionId` → `$positionIds` (массив). Удалён `gameModeIds` (не поддерживается `stats`)
- **Парсинг build:** предметы из `itemFullPurchase` разделяются по времени: early (<15мин), mid (15-25мин), late (>25мин)
- **QUERY_HERO_GUIDE:** `guide` больше не принимает `bracketBasicIds` и `positionIds` → убраны. Поля `winCount`, `abilityMaxOrder`, `talent` удалены из `HeroGuideListType`. Guide API теперь возвращает конкретные матчи, а не агрегированные данные → **guide временно отключён**, возвращается пустой `HeroGuideData`

### 6. Фикс дублирования match_analyses
- **Проблема:** Повторный `/lastmatch` для того же матча → `409 Conflict` (unique constraint `match_analyses_user_id_match_id_key`)
- **Решение:** `services/match_analysis.py` — перед `insert` добавлена проверка `get_by_match_id()`, вставка только если записи нет

**Файлы изменены:**
- `repositories/user.py` — фикс maybe_single()
- `repositories/match_analysis.py` — фикс maybe_single()
- `repositories/subscription.py` — фикс maybe_single()
- `clients/stratz.py` — cloudscraper, обновление GraphQL-запросов и маппингов
- `services/build.py` — отключение guide, использование пустого HeroGuideData
- `services/match_analysis.py` — проверка дубликатов перед insert

**Текущее состояние бота (проверено вручную):**
- `/start` — онбординг работает ✅ (ссылка формата profiles/..., не id/... — STEAM_API_KEY пустой)
- `/meta` — мета-герои по ролям ✅
- `/build` — билд героя (предметы без скиллов/талантов) ✅
- `/lastmatch` — разбор матча с метриками ✅
- `/profile` — профиль и статистика ✅
- `/settings` — настройки ✅
- `/help` — справка ✅

**Что НЕ работает / ограничения:**
- Ссылки формата `steamcommunity.com/id/...` — требуют `STEAM_API_KEY` (не заполнен в .env)
- Скиллы и таланты в `/build` — Stratz guide API изменился, временно отключены
- LLM-советы по матчам — заглушка (TASK-028)
- Драфт-анализ — не реализован

**Заметки для следующей итерации:**
- `cloudscraper` — синхронная библиотека, используется через `asyncio.to_thread()`. Может замедлять при большом количестве запросов. В будущем рассмотреть async-альтернативу или кеширование Cloudflare cookies
- `pyiceberg` заглушка в site-packages — хрупкое решение, при обновлении supabase может сломаться. Рассмотреть переход на `service_role` ключ (обходит RLS) или понижение версии storage3
- Stratz API активно меняет GraphQL-схему. При следующих проблемах использовать introspection-запрос `{ __type(name: "...") { fields { name } } }` для проверки
- STEAM_API_KEY нужно получить на https://steamcommunity.com/dev/apikey и добавить в .env
- Приоритетные pending задачи:
  - TASK-034 (валидация Steam при регистрации, high)
  - TASK-035 (rate limiting, high)
  - TASK-024 (LLM-промпты, medium) — блокирует TASK-025, 028, 029
  - TASK-030 (scheduler, medium)
  - Восстановление guide (скиллы/таланты) — нужен новый подход к Stratz API

---

## 2026-03-07 — TASK-034: Валидация входных данных (DONE)

**Что сделано:**
- Создан `core/validators.py` — централизованный модуль валидации с функциями:
  - `validate_mmr(raw)` — проверка MMR (целое число 0–15000)
  - `validate_hero_query(raw)` — проверка имени героя (длина ≤50, только буквы/цифры/пробелы/дефисы/апострофы, защита от XSS/SQL injection)
  - `validate_steam_input(raw)` — проверка Steam-ввода (не пуст, длина ≤200)
  - `validate_image_size(file_size)` — проверка размера изображений (≤10 МБ)
- Интеграция в хендлеры:
  - `bot/handlers/start.py` — MMR и Steam ID валидируются через `core/validators.py` (убрано дублирование)
  - `bot/handlers/settings.py` — MMR и Steam ID валидируются через `core/validators.py` (убрано дублирование)
  - `bot/handlers/build.py` — имя героя валидируется через `validate_hero_query()` (и в `/build [герой]`, и в FSM)
- Убрана неиспользуемая константа `_MMR_INVALID_TEXT` из `start.py`
- Создан `tests/test_validators.py` — 28 тестов покрывающих все валидаторы (MMR, герой, Steam, изображение)

**Тест-шаги:**
- `uv tool run ruff check .` — 0 ошибок ✅
- `uv tool run pytest tests/test_core.py tests/test_validators.py -v` — 54/54 тестов ✅
- SQL injection в Steam ID (`1; DROP TABLE users;`) → отклонено ✅
- MMR = -100 → отклонено ✅
- Имя героя со спецсимволами (`<script>alert(1)</script>`) → отклонено ✅
- Проверка размера изображений >10 МБ → отклонено ✅

**Заметки для следующей итерации:**
- `validate_image_size()` создан, но хендлер `/draft` (TASK-027) ещё не реализован — интеграция будет при создании хендлера
- Остальные тесты (14 файлов) падают на `ModuleNotFoundError` (httpx, cloudscraper) — предсуществующая проблема среды `uv tool run`
- Приоритетные pending задачи:
  - TASK-035 (rate limiting, high)
  - TASK-024 (LLM-промпты, medium) — блокирует TASK-025, 028, 029
  - TASK-030 (scheduler, medium)
  - TASK-032 (подписки, medium)
