FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies needed by curl-cffi / cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer cache friendly)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY bot/ ./bot/

# Create a non-root user and switch to it
RUN adduser --disabled-password --gecos "" botuser
USER botuser

# Default entrypoint
CMD ["python", "-m", "bot.main"]
