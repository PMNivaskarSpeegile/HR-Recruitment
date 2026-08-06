# ── Speegile ATS — backend (Django + DRF) ───────────────────────────────────
# Runs the API under gunicorn. Static files (admin / DRF / OpenAPI UI) are
# collected at start and served by WhiteNoise, so no separate web server is
# needed inside the container.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_SETTINGS_MODULE=settings

WORKDIR /app

# postgresql-client gives us `pg_isready` for the startup wait; psycopg2-binary
# already bundles libpq, so no compiler/build deps are required.
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Normalise line endings (entrypoint may be checked out with CRLF on Windows).
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
