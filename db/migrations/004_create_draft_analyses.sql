-- Миграция 004: Создание таблицы draft_analyses
-- Результаты анализа драфтов

CREATE TABLE IF NOT EXISTS draft_analyses (
    id               BIGSERIAL    PRIMARY KEY,
    user_id          BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ally_hero_ids    INTEGER[]    NOT NULL DEFAULT '{}',
    enemy_hero_ids   INTEGER[]    NOT NULL DEFAULT '{}',
    recommended_ids  INTEGER[]    NOT NULL DEFAULT '{}',
    user_role        SMALLINT     CHECK (user_role BETWEEN 1 AND 5),
    confidence       REAL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_draft_analyses_user_id ON draft_analyses (user_id);
CREATE INDEX IF NOT EXISTS idx_draft_analyses_created_at ON draft_analyses (user_id, created_at DESC);
