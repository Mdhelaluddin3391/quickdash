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
# Fix line endings just in case and make executable
RUN sed -i 's/\r$//g' /wait-for-db.sh /start.sh && \
    chmod +x /wait-for-db.sh /start.sh

# Create a non-root user
RUN addgroup --system appgroup && adduser --system --group appuser

# Chown all files to the new user
RUN chown -R appuser:appgroup /code

# Switch to non-root user
USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK CMD curl --fail http://localhost:8000/api/v1/utils/health/ || exit 1

# Start command
CMD ["/start.sh"]