-- Миграция 006: Включение RLS и создание политик безопасности
-- Бот обращается к БД через service_role key, поэтому RLS не блокирует серверные запросы.
-- Политики ограничивают доступ для anon-ключа: пользователь видит только свои данные.

-- Включение RLS на всех таблицах
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE mmr_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE draft_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;

-- Политики для таблицы users
-- Пользователь может читать только свою запись (по auth.uid() совпадающему с id)
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (auth.uid()::text = id::text);

CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (auth.uid()::text = id::text);

-- Политики для таблицы mmr_history
CREATE POLICY mmr_history_select_own ON mmr_history
    FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth.uid()::text = id::text));

-- Политики для таблицы match_analyses
CREATE POLICY match_analyses_select_own ON match_analyses
    FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth.uid()::text = id::text));

-- Политики для таблицы draft_analyses
CREATE POLICY draft_analyses_select_own ON draft_analyses
    FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth.uid()::text = id::text));

-- Политики для таблицы subscriptions
CREATE POLICY subscriptions_select_own ON subscriptions
    FOR SELECT
    USING (user_id IN (SELECT id FROM users WHERE auth.uid()::text = id::text));
