# HydraClip API image.
#
# docker-compose.yml has always declared `api: build: ./apps/api`, but no
# Dockerfile existed here — `docker compose build` could only fail.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ffmpeg drives the whole render in services/assembly.py. The Debian build
# includes libass and libx264, which burned-in captions and the watermark
# both depend on.
# fonts-dejavu-core provides the caption typeface; without it libass falls
# back to whatever fontconfig finds, which in a slim image is nothing.
# libpq5 is the runtime library psycopg2 links against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        fonts-dejavu-core \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so layer caching survives source changes.
COPY apps/api/requirements.txt ./apps/api/requirements.txt
RUN pip install -r apps/api/requirements.txt

# Edge TTS (installed from requirements.txt) is the primary online narrator.
# Piper is the local fallback. The image previously installed neither the
# Piper binary nor a voice model, so offline narration could only fail inside
# the container -- /pipeline/status would report it unavailable.
#
# The voice model is a ~60MB download and is deliberately NOT baked in:
# mount it at PIPER_MODEL_PATH (see docker-compose.yml) so the image stays
# small and the voice can be swapped without a rebuild. Fetch one with:
#   curl -L -o en_US-lessac-medium.onnx \
#     https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
#   curl -L -o en_US-lessac-medium.onnx.json \
#     https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
RUN pip install piper-tts

ENV PIPER_MODEL_PATH=/models/piper

# The application imports itself as `apps.api.*`, so the build context is the
# backend directory and the package tree is copied intact.
COPY apps ./apps
COPY seed.py ./seed.py

ENV PYTHONPATH=/app

# Run as a non-root user.
RUN useradd --create-home --uid 1001 hydraclip \
    && chown -R hydraclip:hydraclip /app
USER hydraclip

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
