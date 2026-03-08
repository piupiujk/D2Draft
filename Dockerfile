# === Этап 1: сборка зависимостей ===
FROM python:3.11-slim AS builder

WORKDIR /app

# uv для быстрой установки зависимостей
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

# Установка только production-зависимостей в виртуальное окружение
RUN uv sync --no-dev --frozen

# === Этап 2: финальный образ ===
FROM python:3.11-slim

WORKDIR /app

# Копируем виртуальное окружение из builder
COPY --from=builder /app/.venv /app/.venv

# Копируем исходный код
COPY bot/ bot/
COPY core/ core/
COPY services/ services/
COPY repositories/ repositories/
COPY clients/ clients/
COPY scheduler/ scheduler/
COPY db/ db/
COPY prompts/ prompts/
COPY pyproject.toml ./

# Используем Python из виртуального окружения
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Health check: проверяем что Python и основной модуль импортируются
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import bot" || exit 1

CMD ["python", "-m", "bot"]
