-- Миграция 003: Создание таблицы match_analyses
-- Результаты анализа матчей пользователей

CREATE TABLE IF NOT EXISTS match_analyses (
    id           BIGSERIAL    PRIMARY KEY,
    user_id      BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    match_id     BIGINT       NOT NULL,
    hero_id      INTEGER      NOT NULL,
    role         SMALLINT     CHECK (role BETWEEN 1 AND 5),
    result       VARCHAR(10)  NOT NULL CHECK (result IN ('win', 'loss')),
    duration_sec INTEGER      NOT NULL,
    stats        JSONB        NOT NULL DEFAULT '{}',
    llm_summary  TEXT,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),

    UNIQUE (user_id, match_id)
);

CREATE INDEX IF NOT EXISTS idx_match_analyses_user_id ON match_analyses (user_id);
CREATE INDEX IF NOT EXISTS idx_match_analyses_match_id ON match_analyses (match_id);
CREATE INDEX IF NOT EXISTS idx_match_analyses_created_at ON match_analyses (user_id, created_at DESC);
