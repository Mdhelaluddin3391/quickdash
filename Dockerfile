FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY wait-for-db.sh /wait-for-db.sh
RUN chmod +x /wait-for-db.sh

WORKDIR /code

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        binutils \
        gdal-bin \
        libgdal-dev \
        libproj-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Source code
COPY . /code

# Non-root user
RUN useradd -m appuser && \
    chown -R appuser:appuser /code
USER appuser

EXPOSE 8000

HEALTHCHECK NONE

CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
