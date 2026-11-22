FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    curl \
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Local TTS fallback voice for Piper (Edge TTS is tried first)
RUN mkdir -p /models/piper \
    && curl -L --fail --retry 3 -o /models/piper/en_US-lessac-medium.onnx \
       https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx \
    && curl -L --fail --retry 3 -o /models/piper/en_US-lessac-medium.onnx.json \
       https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json

# Copy application code
COPY . .

# Expose port (for Flower)
EXPOSE 5555

# Run Celery worker
CMD ["celery", "-A", "celery_app", "worker", "--loglevel=info"]
