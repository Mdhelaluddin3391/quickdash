# quickdash
Dango based backend for a QuickQommers

## Docker / Postgres (PostGIS) quick start

This repository ships with a `docker-compose.yml` and `Dockerfile` to run the application with PostGIS and Redis locally.

1. Copy `.env.example` to `.env` and update secrets.
2. Build and start services:

	docker-compose up --build -d

3. Apply migrations and create a superuser (the `web` container runs migrations on startup in compose, but you can run manually):

	docker-compose exec web python manage.py migrate
	docker-compose exec web python manage.py createsuperuser

4. Visit http://localhost:8000 (Daphne ASGI server).

Notes:
- The DB service uses the official `postgis/postgis` image that already includes the PostGIS extensions.
- If you prefer not to use Docker, install Postgres/PostGIS and GDAL on your host. See `config/settings.py` for GeoDjango configuration.
