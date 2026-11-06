# Stage 1: Build stage
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

WORKDIR /app

# Install system dependencies needed to compile packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# Install the locked runtime dependencies into a virtual environment.
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Final minimal stage
FROM python:3.12-slim

WORKDIR /app

# Fonts for matplotlib charts
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment built against the same Python base image.
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY bot/ ./bot/

# Persistent data directory for SQLite (mount a Railway volume here)
RUN mkdir -p /app/data && adduser --disabled-password --gecos "" botuser \
    && chown -R botuser:botuser /app
USER botuser

ENV DATA_DIR=/app/data
ENV PATH="/app/.venv/bin:$PATH"

# Default entrypoint
CMD ["sh", "-c", "case \"${BOT_MODE:-polling}\" in polling) exec python -m bot.main ;; webhook) exec python -m bot.webhook ;; *) echo 'Invalid BOT_MODE' >&2; exit 1 ;; esac"]
