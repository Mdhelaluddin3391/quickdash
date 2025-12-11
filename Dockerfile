# Dockerfile
FROM python:3.12-slim

# Envs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /code

# System Deps (PostGIS & compilation tools)
# [FIX] Added postgresql-client below so pg_isready command works
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    postgresql-client \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    curl \
    netcat-openbsd \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir whitenoise gunicorn

# Project Copy
COPY . .

# Scripts
COPY wait-for-db.sh /wait-for-db.sh
COPY start.sh /start.sh
RUN chmod +x /wait-for-db.sh /start.sh

# User Setup
RUN addgroup --system appgroup && adduser --system --group appuser && \
    mkdir -p /code/staticfiles /code/media && \
    chown -R appuser:appgroup /code

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl --fail http://localhost:8000/api/v1/utils/health/ || exit 1

ENTRYPOINT ["/wait-for-db.sh"]
CMD ["/start.sh"]