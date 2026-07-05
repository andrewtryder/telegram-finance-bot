# Stage 1: Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies needed to compile packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Build wheels for all dependencies to keep the build fast and clean
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Final minimal stage
FROM python:3.12-slim

WORKDIR /app

# Copy compiled wheels from builder
COPY --from=builder /app/wheels /app/wheels

# Install wheels without index and clean up wheels directory
RUN pip install --no-cache-dir --no-index --find-links=/app/wheels /app/wheels/*.whl \
    && rm -rf /app/wheels

# Copy application source
COPY bot/ ./bot/

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos "" botuser
USER botuser

# Default entrypoint
CMD ["python", "-m", "bot.main"]

