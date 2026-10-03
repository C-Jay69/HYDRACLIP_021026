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

The normal stack starts Redis, the API, workers, and beat. It uses
`DATABASE_URL`, Supabase Auth, hosted LLMs, and the `S3_*` settings without
forcing local substitutes. It does not start or wait for local Postgres, MinIO,
Ollama, or Flower. MinIO's official container images were discontinued, so
object storage is either a configured external S3-compatible service or
`STORAGE_BACKEND=local`.

Text generation defaults to OpenRouter (`openrouter/auto`), automatically falls
back to NVIDIA NIM, and can optionally fall back to local Ollama. Configure only
private server-side environment variables—never put provider keys in frontend
code:

```dotenv
LLM_PROVIDER_ORDER=openrouter,nvidia_nim,ollama
OPENROUTER_API_KEY=your-private-key
OPENROUTER_MODEL=openrouter/auto
NVIDIA_NIM_API_KEY=your-private-key
NVIDIA_NIM_MODEL=meta/llama-3.1-70b-instruct
```

Start the optional local fallback only when needed:

```bash
docker compose --profile local-llm up -d ollama
```

Flower is optional monitoring—not an application dependency. Start its current
documented image only when you want the dashboard at http://localhost:5555:

```bash
docker compose --profile monitoring up -d flower
```

For a disposable local PostgreSQL container instead of an external database,
set `DATABASE_URL=postgresql://hydraclip:secret@postgres:5432/hydraclip` and
activate its profile:

```bash
docker compose --profile local-db up -d --build
```

## Login configuration

The web login page is `/auth`. Email/password is verified by Supabase Auth;
after verification HydraClip issues its own API token pair and synchronizes the
user by normalized email. Put the project URL and **publishable/anon** key in
`backend/.env` (never the service-role key):

```dotenv
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-publishable-or-anon-key
```

In Supabase Dashboard:

1. Open **Authentication → Providers → Email** and enable email/password.
2. Open **Authentication → URL Configuration** and set the local Site URL to
   `http://localhost:3000`; add `http://localhost:3000/auth` to allowed redirects.
3. Decide whether **Confirm email** is enabled. When enabled, HydraClip tells the
   user to confirm before signing in instead of pretending signup completed.

Google login directly reuses `YOUTUBE_CLIENT_ID` and
`YOUTUBE_CLIENT_SECRET`; it requests only `openid email profile`, while the
separate YouTube connection still requests upload permission. In the same
Google Cloud **Web application** OAuth client, keep the YouTube callback and add
the login callback as a second Authorized redirect URI:

```text
http://localhost:8000/oauth/youtube/callback
http://localhost:8000/auth/google/callback
```

Also keep `http://localhost:3000` as an Authorized JavaScript origin, then set:

```dotenv
GOOGLE_LOGIN_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

Production values must use the real HTTPS API/app hosts and match Google Cloud
exactly. Do not paste client secrets or populated `.env` files into issues or
chat.

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

See `backend/.env.example` for Supabase PostgreSQL/Auth, S3-compatible storage, OpenRouter/NVIDIA/Ollama, stock-media, OAuth, and Piper settings.
