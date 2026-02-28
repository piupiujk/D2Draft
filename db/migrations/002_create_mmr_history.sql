-- Миграция 002: Создание таблицы mmr_history
-- История изменений MMR пользователей

CREATE TABLE IF NOT EXISTS mmr_history (
    id         BIGSERIAL    PRIMARY KEY,
    user_id    BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mmr        INTEGER      NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_mmr_history_user_id ON mmr_history (user_id);
CREATE INDEX IF NOT EXISTS idx_mmr_history_recorded_at ON mmr_history (user_id, recorded_at DESC);
