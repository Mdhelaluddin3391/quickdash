FROM python:3.11

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

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

COPY requirements.txt /code/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . /code

COPY wait-for-db.sh /wait-for-db.sh
RUN chmod +x /wait-for-db.sh

RUN useradd -m appuser && \
    chown -R appuser:appuser /code

USER appuser

EXPOSE 8000

HEALTHCHECK CMD curl --fail http://localhost:8000/ || exit 1

CMD ["/wait-for-db.sh", "daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
