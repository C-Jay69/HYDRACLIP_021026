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
docker compose build api
docker compose up -d
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
