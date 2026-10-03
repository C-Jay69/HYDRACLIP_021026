# HydraClip

**Generate. Automate. Clip.**

HydraClip turns a topic into a scripted, narrated, assembled video and schedules it for publishing to YouTube, Instagram, TikTok, and X.

## Repository layout

```text
.
├── src/                 # Bun + React web frontend
├── public/              # Public brand and social-preview assets
└── backend/             # FastAPI, Celery workers, migrations, tests, and Compose
```

The backend environment file belongs at `backend/.env`. Copy `backend/.env.example` to get started; never commit the populated file.

## Frontend

Requirements: [Bun](https://bun.sh/).

```bash
bun install
bun run dev
```

Verification:

```bash
bun run typecheck
bun run verify
```

## Backend

Requirements: Docker with the Compose plugin.

```bash
cd backend
cp .env.example .env     # first run only; replace placeholders before use
docker compose config --quiet
docker compose up -d --build
```

The normal stack starts Redis, Ollama, the API, workers, beat, and Flower. It
uses `DATABASE_URL` and the `S3_*` settings for hosted services such as
Supabase; it does not start or wait for local Postgres or MinIO. MinIO's
official container images were discontinued, so object storage is either a
configured external S3-compatible service or `STORAGE_BACKEND=local`.

For a disposable local PostgreSQL container instead of an external database,
set `DATABASE_URL=postgresql://hydraclip:secret@postgres:5432/hydraclip` and
activate its profile:

```bash
docker compose --profile local-db up -d --build
```

Apply database migrations and seed the plans/admin account:

```bash
docker compose run --rm --no-deps api \
  alembic -c apps/api/alembic.ini upgrade head
docker compose run --rm --no-deps api python seed.py
```

Health checks:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

Run backend tests locally:

```bash
cd backend
make install
make test
```

See `backend/.env.example` for Supabase PostgreSQL, S3-compatible storage, stock-media, OAuth, Ollama, and Piper settings.
