# Stage 1: Builder
FROM python:3.12-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

# Stage 2: Final
FROM python:3.12-slim

WORKDIR /code

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install runtime dependencies (PostGIS/GeoDjango needs binutils, gdal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    binutils \
    libproj-dev \
    gdal-bin \
    libgdal-dev \
    curl \
    netcat-openbsd \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir /wheels/*

# Setup User
RUN addgroup --system appgroup && adduser --system --group appuser

# Copy Project
COPY . /code

# Copy Scripts
COPY wait-for-db.sh /wait-for-db.sh
COPY start.sh /start.sh

# Permissions
RUN chown -R appuser:appgroup /code && \
    chmod +x /wait-for-db.sh /start.sh && \
    mkdir -p /code/staticfiles /code/media && \
    chown -R appuser:appgroup /code/staticfiles /code/media

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl --fail http://localhost:8000/api/v1/utils/health/ || exit 1

ENTRYPOINT ["/wait-for-db.sh"]
CMD ["/start.sh"]