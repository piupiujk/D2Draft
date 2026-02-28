-- Миграция 005: Создание таблицы subscriptions
-- Подписки пользователей (Premium)

CREATE TABLE IF NOT EXISTS subscriptions (
    id           BIGSERIAL    PRIMARY KEY,
    user_id      BIGINT       NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan         VARCHAR(20)  NOT NULL DEFAULT 'premium' CHECK (plan IN ('premium')),
    status       VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'expired', 'cancelled')),
    started_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at   TIMESTAMPTZ  NOT NULL,
    cancelled_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires_at ON subscriptions (expires_at) WHERE status = 'active';
