-- Миграция 001: Создание таблицы users
-- Основная таблица пользователей бота

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    telegram_id   BIGINT       NOT NULL UNIQUE,
    steam_id      VARCHAR(20)  UNIQUE,
    username      VARCHAR(255),
    current_mmr   INTEGER,
    mmr_updated_at TIMESTAMPTZ,
    main_role     SMALLINT     CHECK (main_role BETWEEN 1 AND 5),
    is_premium    BOOLEAN      NOT NULL DEFAULT FALSE,
    premium_expires_at TIMESTAMPTZ,
    notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    weekly_report_day SMALLINT DEFAULT 1 CHECK (weekly_report_day BETWEEN 0 AND 6),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Индексы для частых запросов
CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users (telegram_id);
CREATE INDEX IF NOT EXISTS idx_users_steam_id ON users (steam_id);

-- Триггер автообновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
