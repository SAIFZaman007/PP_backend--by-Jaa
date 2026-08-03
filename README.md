# Peak Physique — Backend (FastAPI)

Async FastAPI API with SQLAlchemy 2.0, PostgreSQL (SQLite for local dev), JWT auth,
and optional Stripe / Google Calendar / SMTP integrations that degrade gracefully when
unconfigured.

## Run locally

```bash
cp .env.example .env
uv venv
uv sync
uv run python -m app.db.init_db     # create tables + seed demo data
uv run uvicorn app.main:app --reload
```

- API base: `http://localhost:8000/api/v1`
- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Seeded accounts

- Client: `demo@peakphysique.com` / `peak2025`
- Trainer/admin: `FIRST_TRAINER_EMAIL` / `FIRST_TRAINER_PASSWORD` from your `.env`

## Tests

```bash
uv run pytest
```

## Key modules

- `app/core` — config, security (JWT + bcrypt), logging, rate limiting
- `app/models` — user, plan, booking, payment, progress, message
- `app/api/routes` — auth, users, plans, bookings, progress, payments, messages, admin
- `app/services` — email, stripe, google_calendar (all safe when unconfigured)
- `app/db` — async engine/session, `init_db` (create + seed), Alembic migrations

## Migrations

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

See the root `README.md` for full configuration and deployment details, and `SECURITY.md`
before going to production.
