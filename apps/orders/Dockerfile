# Minimal Dockerfile to containerize Orders service for microservice deployment
# This is a scaffold: customize base image, environment, and dependencies.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app
ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]
