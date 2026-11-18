# syntax=docker/dockerfile:1
ARG UV_VERSION=0.12
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------- builder: зависимости и пакет в изолированный venv ----------
FROM python:3.13-slim AS builder
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---------- runtime: без uv, без исходников сборки, не от root ----------
FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Europe/Moscow \
    PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
# Миграции запускаются из этого же образа: docker compose run --rm bot alembic upgrade head
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic

USER app
CMD ["autopark-bot"]
