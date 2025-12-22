# STAGE 1: Builder
FROM python:3.11-slim-bullseye as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# STAGE 2: Final
FROM python:3.11-slim-bullseye

# Create a non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /home/appuser/app

# Install runtime dependencies (libpq for Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*

# Copy Application Code
COPY . .

# Chown all files to the app user
RUN chown -R appuser:appuser /home/appuser/app

# Switch to non-root user
USER appuser

# Expose port (Gunicorn/Uvicorn usually runs on 8000)
EXPOSE 8000

# Entrypoint script to wait for DB and start server
ENTRYPOINT ["/home/appuser/app/start.sh"]