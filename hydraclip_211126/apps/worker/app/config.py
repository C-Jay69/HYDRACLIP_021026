"""HydraClip Application Configuration."""

import os
from functools import lru_cache
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_prefix="HYDRA_",
        env_file=".env",
        env_file_encoding="utf-8",
    )
    
    # Database
    database_url: str = Field(..., description="PostgreSQL connection URL")
    database_pool_size: int = Field(default=5, ge=1, le=20)
    database_max_overflow: int = Field(default=10, ge=0)
    
    # Redis
    redis_url: str = Field(..., description="Redis connection URL")
    
    # MinIO / S3
    minio_endpoint: str = Field(..., description="MinIO/S3 endpoint URL")
    minio_access_key: str = Field(..., description="MinIO/S3 access key")
    minio_secret_key: str = Field(..., description="MinIO/S3 secret key")
    minio_bucket: str = Field(..., description="Default bucket name")
    
    # Security
    secret_key: str = Field(..., description="JWT secret key")
    algorithm: str = Field(default="HS256", description="JWT algorithm")
    access_token_expire_minutes: int = Field(default=15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=365)
    
    # Admin
    admin_email: str = Field(..., description="Admin email address")
    admin_password: str = Field(..., description="Admin password hash")
    
    # Stripe
    stripe_publishable_key: str = Field(..., description="Stripe publishable key")
    stripe_secret_key: str = Field(..., description="Stripe secret key")
    stripe_webhook_secret: str = Field(..., description="Stripe webhook secret")
    stripe_creator_price_id: str = Field(..., description="Creator plan price ID")
    stripe_pro_price_id: str = Field(..., description="Pro plan price ID")
    
    # OAuth
    youtube_client_id: str = Field(..., description="YouTube OAuth client ID")
    youtube_client_secret: str = Field(..., description="YouTube OAuth client secret")
    youtube_redirect_uri: str = Field(..., description="YouTube OAuth redirect URI")
    
    # AI Models
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama server URL")
    ollama_model: str = Field(default="llama3.2", description="Default Ollama model")
    piper_model_path: str = Field(default="/models/piper", description="Piper TTS model path")
    whisper_model_size: str = Field(default="tiny", description="Whisper model size")
    
    # App
    app_url: str = Field(..., description="Application URL")
    next_public_app_url: str = Field(..., description="Next.js public app URL")
    maintenance_mode: bool = Field(default=False, description="Global maintenance mode")
    
    # Plan limits
    free_video_limit: int = Field(default=3, ge=0, description="Free plan video limit per month")
    creator_video_limit: int = Field(default=25, ge=0, description="Creator plan video limit per month")
    pro_video_limit: int = Field(default=-1, ge=-1, description="Pro plan video limit (-1=unlimited)")
    storage_limit_free_gb: int = Field(default=1, ge=1, description="Free plan storage limit in GB")
    storage_limit_creator_gb: int = Field(default=10, ge=1, description="Creator plan storage limit in GB")
    storage_limit_pro_gb: int = Field(default=50, ge=1, description="Pro plan storage limit in GB")
    
    # Feature flags
    enable_youtube_publish: bool = Field(default=True, description="Enable YouTube auto-publish")
    enable_instagram_export: bool = Field(default=True, description="Enable Instagram export")
    enable_tiktok_export: bool = Field(default=True, description="Enable TikTok export")
    enable_x_export: bool = Field(default=True, description="Enable X export")
    enable_ai_images: bool = Field(default=False, description="Enable AI image generation")
    enable_voice_cloning: bool = Field(default=False, description="Enable voice cloning")
    
    # Rate limiting
    rate_limit_auth: int = Field(default=5, ge=1, description="Auth endpoint rate limit per minute")
    rate_limit_general: int = Field(default=30, ge=1, description="General API rate limit per minute")
    rate_limit_generation: int = Field(default=3, ge=1, description="Video generation rate limit per minute")
    
    # CORS
    cors_origins: list = Field(default=["http://localhost:3000", "http://127.0.0.1:3000"])


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def validate_settings() -> bool:
    """Validate that all required settings are present."""
    try:
        s = get_settings()
        required = [
            "database_url",
            "redis_url",
            "minio_endpoint",
            "minio_access_key",
            "minio_secret_key",
            "minio_bucket",
            "secret_key",
            "admin_email",
            "admin_password",
            "stripe_publishable_key",
            "stripe_secret_key",
            "stripe_webhook_secret",
            "stripe_creator_price_id",
            "stripe_pro_price_id",
            "youtube_client_id",
            "youtube_client_secret",
            "youtube_redirect_uri",
        ]
        missing = [r for r in required if not getattr(s, r, None)]
        if missing:
            print(f"❌ Missing required settings: {missing}")
            return False
        print("✓ All required settings validated")
        return True
    except Exception as e:
        print(f"❌ Settings validation error: {e}")
        return False


def get_cors_origins() -> list:
    """Get CORS origins from settings."""
    return get_settings().cors_origins


# Export for use in other modules
settings = get_settings()