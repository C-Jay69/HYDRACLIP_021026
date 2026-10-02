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
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "videoforce"

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
