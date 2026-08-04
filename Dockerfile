# ---- Peak Physique backend image ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install uv (fast, reproducible dependency management)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Install deps first for better layer caching
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# App source
COPY . .

EXPOSE 8000

# Apply schema migrations, seed reference data, then start the API
# (gunicorn-style workers via uvicorn). Uses `alembic upgrade head` rather
# than the dev-only create_all path (app/db/init_db.py) — that only ever
# creates tables that don't exist yet, so it silently no-ops on an
# existing production database instead of applying schema changes like
# the bookings.start_time / payment_item_id migration. Both steps are
# idempotent and safe to re-run on every deploy/restart.
CMD ["sh", "-c", "alembic upgrade head && python -m app.db.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"]