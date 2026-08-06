#!/usr/bin/env sh
# Backend container startup: wait for Postgres, collect static, run gunicorn.
# (Schema + reference data are loaded by the db container on first init; create
#  the demo users/data once with:  docker compose exec backend python manage.py seed_demo)
set -e

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"

echo "Waiting for Postgres at ${DB_HOST}:${DB_PORT} ..."
until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "${DB_USER:-postgres}" >/dev/null 2>&1; do
  sleep 1
done
echo "Postgres is ready."

python manage.py collectstatic --noinput

exec gunicorn wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 120
