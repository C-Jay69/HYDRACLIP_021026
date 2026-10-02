"""Application settings.

Consolidated from the old ``apps/api/app/core/config.py``, which had three
problems that made the service impossible to start:

1. ``DATABASE_URL`` and ``STRIPE_SECRET_KEY`` were read with a helper that
   raised ``ValueError`` at class-definition time. Importing the module without
   a fully populated ``.env`` crashed the process — and a Stripe key should
   never be required just to boot the API.
2. The ``.env`` path resolved to ``videoforce-mvp/apps/videoforce-mvp/.env``,
   which does not exist, so the file was never loaded.
3. ``seed.py`` imported ``apps.api.core.config`` while ``main.py`` imported
   ``apps.api.app.core.config`` — two different trees, one of them empty.

Everything now lives here, backed by pydantic-settings.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# videoforce-mvp/apps/api/core/config.py -> parents[3] == videoforce-mvp/
BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"

INSECURE_SECRET_KEY = "super-secret-key-change-in-production"


class Settings(BaseSettings):
    """Runtime configuration, loaded from the environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    # --- Database -----------------------------------------------------------
    DATABASE_URL: str = "postgresql://videoforce:secret@localhost:5432/videoforce"
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Object storage -----------------------------------------------------
    # These are plain S3 settings despite the MinIO names: they work
    # unchanged against AWS S3, Cloudflare R2, Backblaze B2 or Spaces.
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "videoforce"

    #: "local" keeps rendered files on disk; "s3" uploads them to the bucket
    #: above. Default local, so a fresh checkout works with no object store
    #: running -- the MinIO defaults above would otherwise make an
    #: unconfigured deployment look configured.
    STORAGE_BACKEND: str = "local"

    S3_REGION: str = "us-east-1"

    #: MinIO serves path-style URLs (host/bucket/key). Virtual-host style
    #: (bucket.host/key) needs per-bucket DNS, which MinIO does not set up.
    S3_FORCE_PATH_STYLE: bool = True

    #: The externally reachable base URL of the object store.
    #:
    #: This is the setting that decides whether Instagram and TikTok can
    #: actually fetch a video. MINIO_ENDPOINT is usually an internal address
    #: like http://minio:9000, which resolves only inside the Docker
    #: network; a URL signed against it is useless to a third party. Set
    #: this to the public HTTPS address of the bucket (or a CDN in front of
    #: it) and URLs are signed against that host instead.
    MEDIA_PUBLIC_BASE_URL: str = ""

    #: How long a signed media URL stays valid. Providers queue downloads,
    #: so this needs slack; a URL that expires mid-fetch fails the publish.
    MEDIA_URL_EXPIRY_SECONDS: int = 86400

    #: Keep the local scratch copy after a successful upload. Off by
    #: default: the worker's disk is not where finished videos should live.
    MEDIA_RETAIN_LOCAL: bool = False

    # --- Security -----------------------------------------------------------
    SECRET_KEY: str = INSECURE_SECRET_KEY
    JWT_ALGORITHM: str = "HS256"
    # Seconds. Names kept for compatibility with the existing .env.example.
    ACCESS_TOKEN_EXPIRES_IN: int = 3600
    REFRESH_TOKEN_EXPIRES_IN: int = 86400
    # Failed logins allowed per email+IP inside the window before 429.
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    # --- Billing ------------------------------------------------------------
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # --- Bootstrap admin ----------------------------------------------------
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "adminpass"

    # --- Local AI models ----------------------------------------------------
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"
    OLLAMA_TIMEOUT_SECONDS: float = 120.0
    PIPER_MODEL_PATH: str = "/models/piper"
    WHISPER_MODEL_SIZE: str = "base"
    TTS_TIMEOUT_SECONDS: float = 120.0

    #: Scratch space for intermediate render artefacts.
    MEDIA_WORK_DIR: str = "/tmp/videoforce"
    #: Wall-clock ceiling for one generation job.
    JOB_TIMEOUT_SECONDS: float = 900.0

    # --- Background execution ------------------------------------------------
    #: "inline" runs jobs as asyncio tasks inside the API process (dev only;
    #: work is lost on restart). "celery" dispatches to the worker fleet.
    JOB_RUNNER: Literal["inline", "celery"] = "inline"

    #: Both default to REDIS_URL when left blank, so a single setting is
    #: enough for the common deployment.
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    #: Beat intervals, in seconds.
    STALE_JOB_SWEEP_SECONDS: float = 300.0
    WORK_DIR_SWEEP_SECONDS: float = 3600.0
    SCHEDULE_TICK_SECONDS: float = 60.0

    #: Delete work-directory artefacts older than this.
    WORK_DIR_TTL_SECONDS: float = 86_400.0

    @property
    def celery_broker_url(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL

    @property
    def celery_result_backend(self) -> str:
        """Celery reads the URL scheme as a backend *module* name.

        A bare "postgresql://" raises ModuleNotFoundError: the SQLAlchemy
        backend needs the "db+" prefix. Normalise it here so a plain database
        URL in the environment cannot take the worker down.
        """
        backend = self.CELERY_RESULT_BACKEND or self.REDIS_URL
        if backend.startswith(("postgresql://", "postgres://", "sqlite://", "mysql://")):
            return f"db+{backend}"
        return backend

    # --- Application URLs ---------------------------------------------------
    APP_URL: str = "http://localhost:3000"
    NEXT_PUBLIC_APP_URL: str = "http://localhost:3000"

    # --- Stock media --------------------------------------------------------
    SHUTTERSTOCK_API_TOKEN: str = ""

    # --- Stock media providers -----------------------------------------------
    #: Pexels: free photos *and* video, portrait orientation on both, and
    #: video_files[] lists exact pixel dimensions so we can pick a native
    #: 1080x1920 file instead of downscaling 4K. Preferred source.
    PEXELS_API_KEY: str = ""

    #: Pixabay: free, royalty-free, no watermark, and it has video. Their
    #: terms require caching results for 24h and downloading rather than
    #: hotlinking; both are implemented in services/stock.
    PIXABAY_API_KEY: str = ""

    #: Unsplash: photos only. Their guidelines require pinging the
    #: download_location endpoint on each download and crediting the
    #: photographer.
    UNSPLASH_ACCESS_KEY: str = ""

    #: Preference order when sourcing footage. The first configured provider
    #: that can satisfy a scene wins.
    STOCK_PROVIDER_ORDER: str = "pexels,pixabay,unsplash,shutterstock"

    #: Pixabay requires search responses to be cached for 24 hours.
    STOCK_CACHE_TTL_SECONDS: int = 86400

    # --- Video assembly --------------------------------------------------------
    #: Vertical by default: the platforms Phase 5 publishes to (Shorts,
    #: Reels, TikTok) are all 9:16.
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30

    #: Seconds a still image is held on screen when a scene has no clip.
    SCENE_MIN_SECONDS: float = 2.0
    SCENE_MAX_SECONDS: float = 12.0

    #: Burned-in captions. Subtitles are timed from the measured duration of
    #: each synthesised sentence, so no speech recognition is involved.
    SUBTITLES_ENABLED: bool = True
    SUBTITLE_FONT_SIZE: int = 56

    #: Ceiling on a single render.
    RENDER_TIMEOUT_SECONDS: int = 900

    #: Absolute path to ffmpeg/ffprobe. Blank means "find it on PATH".
    FFMPEG_BINARY: str = ""
    FFPROBE_BINARY: str = ""

    # --- Secret storage ------------------------------------------------------
    #: Fernet key material for encrypting stored OAuth tokens. When blank the
    #: key is derived from SECRET_KEY, which means rotating SECRET_KEY strands
    #: every connected account. Set this explicitly in production.
    TOKEN_ENCRYPTION_KEY: str = ""

    #: How long an in-flight OAuth authorisation may take before its state
    #: blob expires.
    OAUTH_STATE_TTL_SECONDS: int = 600

    #: Refresh an access token this long before it actually expires.
    TOKEN_REFRESH_LEEWAY_SECONDS: int = 300

    # --- Social platform OAuth ---------------------------------------------
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""
    YOUTUBE_REDIRECT_URI: str = ""

    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    INSTAGRAM_REDIRECT_URI: str = ""

    TIKTOK_CLIENT_ID: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    TIKTOK_REDIRECT_URI: str = ""

    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""
    X_REDIRECT_URI: str = ""

    #: Meta versions its Graph API in the URL and retires old versions, so
    #: this has to be configurable rather than baked into the client.
    INSTAGRAM_GRAPH_VERSION: str = "v21.0"

    #: Ceiling on how long a provider may take to finish processing an upload.
    PUBLISH_POLL_TIMEOUT_SECONDS: float = 300.0
    PUBLISH_POLL_INTERVAL_SECONDS: float = 5.0

    # --- Email --------------------------------------------------------------
    SMTP_HOST: str = "smtp.example.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalise_database_url(cls, value: str) -> str:
        """SQLAlchemy 1.4+ rejects the legacy ``postgres://`` scheme."""
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql://", 1)
        return value

    @model_validator(mode="after")
    def _reject_insecure_production_config(self) -> "Settings":
        if self.ENVIRONMENT == "production" and self.SECRET_KEY == INSECURE_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the placeholder value. Set a strong, unique "
                "SECRET_KEY before running with ENVIRONMENT=production."
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        """Unique, non-empty browser origins allowed to call the API."""
        candidates = [self.APP_URL, self.NEXT_PUBLIC_APP_URL]
        return sorted({origin for origin in candidates if origin})


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
