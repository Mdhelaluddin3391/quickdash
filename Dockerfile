# Use Python 3.12 Slim
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgeos-dev \
        build-essential \
        libpq-dev \
        binutils \
        gdal-bin \
        libgdal-dev \
        libproj-dev \
        curl \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Copy requirements
COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /code

# Permission fixes for scripts
COPY wait-for-db.sh /wait-for-db.sh
COPY start.sh /start.sh
RUN chmod +x /wait-for-db.sh /start.sh

# --- FIX: REMOVED USER CREATION FOR DEV ENVIRONMENT ---
# Development mein Root user use karna safe aur aasan hai taaki permission issues na aayein.

EXPOSE 8000

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8000/ || exit 1

# Start command
CMD ["/start.sh"]