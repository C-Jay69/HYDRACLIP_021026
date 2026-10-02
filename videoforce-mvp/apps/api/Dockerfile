# Videoforce API image.
#
# docker-compose.yml has always declared `api: build: ./apps/api`, but no
# Dockerfile existed here — `docker compose build` could only fail.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg is required by services/ai_pipeline.py (FFmpegProcessor).
# libpq5 is the runtime library psycopg2 links against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so layer caching survives source changes.
COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install -r apps/api/requirements.txt

# The application imports itself as `apps.api.*`, so the build context is the
# videoforce-mvp directory and the package tree is copied intact.
COPY apps ./apps
COPY seed.py ./seed.py

ENV PYTHONPATH=/app

# Run as a non-root user.
RUN useradd --create-home --uid 1001 videoforce \
    && chown -R videoforce:videoforce /app
USER videoforce

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
