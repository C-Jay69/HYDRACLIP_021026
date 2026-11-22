# HydraClip

AI-powered video generation and publishing platform using only free/open-source local AI models.

## Overview

HydraClip is a full-stack SaaS platform that enables users to:

- Generate short-form and long-form videos from topics/prompts
- Use local AI models (Ollama, Edge TTS, Piper, faster-whisper, FFmpeg)
- Schedule and publish to YouTube, Instagram, TikTok, and X
- Manage everything through a clean dashboard
- Admin panel for platform management

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      HydraClip Platform                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │   Web App    │  │   API        │  │   Worker         │   │
│  │   (React)    │  │   (FastAPI)  │  │   (Celery)       │   │
│  │   Port 3000  │  │   Port 8000  │  │   Background     │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────┘   │
│         │                 │                  │               │
│         └─────────────────┼──────────────────┘               │
│                           │                                  │
│         ┌─────────────────┼─────────────────┐               │
│         │                 │                 │               │
│  ┌──────▼──────┐  ┌───────▼──────┐  ┌───────▼──────┐       │
│  │  PostgreSQL │  │    Redis     │  │    MinIO     │       │
│  │   Port 5432 │  │   Port 6379  │  │   Port 9000  │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Ollama (Port 11434)                     │    │
│  │   Llama 3.2 / Mistral for script generation         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Frontend**: React 19, Vite, TypeScript, Tailwind CSS, shadcn/ui
- **Backend**: FastAPI (Python 3.11+), SQLAlchemy 2.0, Alembic
- **Workers**: Celery + Redis
- **Database**: PostgreSQL
- **Storage**: MinIO (S3-compatible)
- **AI**: Ollama, Edge TTS, Piper, faster-whisper, FFmpeg
- **Payments**: Stripe
- **Deployment**: Docker Compose

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 4GB+ RAM (8GB recommended)
- 10GB+ free disk space

## Quick Start

### 1. Clone and Setup

```bash
git clone <repo-url>
cd hydraclip
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your settings:

```bash
# Required
SECRET_KEY=your-secret-key
ADMIN_EMAIL=admin@hydraclip.com
ADMIN_PASSWORD=adminpassword123

# Stripe
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_CREATOR_PRICE_ID=price_...
STRIPE_PRO_PRICE_ID=price_...

# YouTube OAuth
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REDIRECT_URI=http://localhost:8000/api/oauth/youtube/callback
```

### 3. Start Services

```bash
make setup
make up
```

### 4. Initialize Database

```bash
make migrate
make seed
```

### 5. Pull AI Model

```bash
make pull-model
```

### 6. Access the App

- Web: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Flower: http://localhost:5555
- MinIO Console: http://localhost:9001

## Default Accounts

| Email | Password | Role |
|-------|----------|------|
| admin@hydraclip.com | adminpassword123 | ADMIN |
| test@example.com | testpassword123 | USER |

## Video Generation Pipeline (OpenRouter + Remotion)

Generation is a real end-to-end pipeline, not a simulation:

1. **API** - `POST /api/videos/videos/generate` creates the `Video` + `VideoJob`
   rows and enqueues `tasks.video_generation.generate_video` on Celery.
2. **Worker** - asks **OpenRouter** for a structured plan (title, narration,
   on-screen scenes, colors), searches **Unsplash** for portrait background
   photos, synthesizes the voiceover (Edge TTS → Piper → silence fallback), and
   sends everything to the renderer.
3. **Renderer** - `apps/renderer` is a Remotion (React) service that renders a
   1080x1920 H.264 MP4 with photo backgrounds, a Ken Burns motion effect, dark
   overlays and photographer credits. The worker uploads it to SeaweedFS/S3 and
   the API's `/download` endpoint returns a presigned URL.

```bash
# Required for LLM planning (https://openrouter.ai/keys)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openrouter/auto

# Background photos (https://unsplash.com/developers)
UNSPLASH_ACCESS_KEY=...

# Remotion licence: "free-license" is valid for individuals and
# companies of up to 3 people. Larger companies need a Company License.
REMOTION_LICENSE_KEY=free-license
REMOTION_IS_PRODUCTION=false
RENDER_CONCURRENCY=1
RENDER_TABS=4
RENDER_TIMEOUT_SECONDS=1800
```

If `OPENROUTER_API_KEY` is empty, the worker uses a deterministic fallback
plan. If `UNSPLASH_ACCESS_KEY` is empty (or a search returns nothing), the
composition falls back to the animated gradient background. The renderer is
CPU-only; a 30-second short can take several minutes. Raise `RENDER_TABS` if the
host has more cores. Health check: `http://localhost:3002/health`.

## AI Model Setup

### Ollama

Ollama remains available for other tasks, but video generation now uses
OpenRouter for planning. Pull a model if you want to use Ollama directly:

```bash
docker-compose exec ollama ollama pull llama3.2
docker-compose exec ollama ollama pull mistral
```

### Edge TTS

Edge TTS is cloud-based but free. The worker uses `edge-tts==7.3.1`.

### Piper TTS

Piper is the local fallback. The worker image bundles the
`en_US-lessac-medium` voice under `/models/piper`, so it works offline.

### faster-whisper

Whisper models are downloaded automatically. Default is "tiny" for speed.

## Stripe Setup

1. Create a Stripe account at https://stripe.com
2. Get API keys from Dashboard → Developers → API keys
3. Create products and prices:
   - Free: $0/month
   - Creator: $19/month
   - Pro: $49/month
4. Set webhook endpoint: `http://localhost:8000/api/webhooks/stripe`
5. Add webhook events: `checkout.session.completed`, `customer.subscription.*`, `invoice.*`

## Social Platform OAuth Setup

### YouTube

1. Go to Google Cloud Console
2. Create a project
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials
5. Add redirect URI: `http://localhost:8000/api/oauth/youtube/callback`
6. Set `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET`

### Instagram, TikTok, X

These platforms require Business/Creator accounts and app review for write access. HydraClip provides compliant manual export workflows instead.

## API Limitations

| Platform | Auto-Publish | Notes |
|----------|-------------|-------|
| YouTube | ✅ Full | Data API v3, OAuth 2.0 |
| Instagram | ❌ Manual | Requires Business account + app review |
| TikTok | ❌ Manual | Requires app approval |
| X | ❌ Manual | Write access requires paid tier |

For platforms without auto-publish, HydraClip generates export packages (MP4 + JSON metadata + upload guide).

## Admin Panel

Access at `/admin` with admin credentials.

Features:
- Dashboard metrics
- User management
- Job monitoring
- System settings
- Audit logs

## Deployment

### VPS

```bash
# On your VPS
git clone <repo-url>
cd hydraclip
cp .env.example .env
# Edit .env with production values
make setup
make up
```

### Railway

```bash
railway init
railway up
```

### Render

1. Connect repository
2. Set environment variables
3. Deploy

### Fly.io

```bash
fly launch
fly deploy
```

## Troubleshooting

### Ollama not responding

```bash
docker-compose exec ollama ollama list
docker-compose exec ollama ollama pull llama3.2
```

### Database connection issues

```bash
docker-compose exec postgres psql -U hydraclip -d hydraclip
```

### Worker not processing jobs

```bash
docker-compose logs worker
docker-compose restart worker
```

### MinIO access issues

Default credentials: `minioadmin` / `minioadmin`
Console: http://localhost:9001

## Project Structure

```
hydraclip/
├── apps/
│   ├── web/                    # React frontend
│   ├── api/                    # FastAPI backend
│   └── worker/                 # Celery workers
├── docker-compose.yml
├── .env.example
├── seed.py
├── Makefile
└── README.md
```

## License

MIT License