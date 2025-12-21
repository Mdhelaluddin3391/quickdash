FROM python:3.12-slim

# Envs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /code

# System Deps
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
    && rm -rf /var/lib/apt/lists/*

# Dependencies (Cached Layer)
COPY requirements.txt .
# Added uvicorn explicitly to allow Gunicorn to run with uvicorn workers for ASGI/Channels support
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir whitenoise gunicorn uvicorn

# User Setup (Create user BEFORE copying code to handle permissions correctly)
RUN addgroup --system appgroup && adduser --system --group appuser

# Scripts
COPY wait-for-db.sh /wait-for-db.sh
COPY start.sh /start.sh
# Fix permissions so appuser can execute them
RUN chmod +x /wait-for-db.sh /start.sh && \
    chown appuser:appgroup /wait-for-db.sh /start.sh

# Project Copy
COPY . .
# Grant ownership to appuser
RUN mkdir -p /code/staticfiles /code/media && \
    chown -R appuser:appgroup /code

# 🔒 SECURITY: Switch to non-root user
USER appuser

EXPOSE 8000

# Healthcheck
# Checks the Django health endpoint. 
# Gunicorn only starts serving execution of start.sh, meaning Migrations are done.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl --fail http://localhost:8000/api/v1/utils/health/ || exit 1

ENTRYPOINT ["/wait-for-db.sh"]
CMD ["/start.sh"]