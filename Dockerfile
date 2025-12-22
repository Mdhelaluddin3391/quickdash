# ==============================
# BUILDER STAGE
# ==============================
FROM python:3.10-slim-bullseye as builder

WORKDIR /app

# Install system dependencies (PostGIS requires gdal/geos)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gdal-bin \
    libgdal-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install -r requirements.txt

# ==============================
# RUNNER STAGE
# ==============================
FROM python:3.10-slim-bullseye

WORKDIR /app

# Install Runtime Libs
RUN apt-get update && apt-get install -y \
    libpq5 \
    gdal-bin \
    libgdal-dev \
    netcat \
    && rm -rf /var/lib/apt/lists/*

# Copy installed python packages
COPY --from=builder /install /usr/local

# Copy Source
COPY . .

# Collect Static (Fake secret key just for build step)
RUN SECRET_KEY=build-key python manage.py collectstatic --noinput

# Permission
RUN chmod +x start.sh

EXPOSE 8000

CMD ["./start.sh"]