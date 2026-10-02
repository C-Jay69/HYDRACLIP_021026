import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent.parent / "videoforce-mvp" / ".env"
load_dotenv(dotenv_path=env_path)

BASE_DIR = Path(__file__).parent.parent.parent.parent.parent / "videoforce-mvp"


def get_env(key: str, default: str = None) -> str:
    """Get environment variable with fallback."""
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"Environment variable {key} is not set")
    return value


class Settings:
    """Application settings."""
    
    # Database
    DATABASE_URL: str = get_env("DATABASE_URL")
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    
    # MinIO/S3 storage
    MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "http://localhost:9000")
    MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.environ.get("MINIO_BUCKET", "videoforce")
    
    # Security
    SECRET_KEY: str = get_env("SECRET_KEY")
    ACCESS_TOKEN_EXPIRES_IN: int = int(os.environ.get("ACCESS_TOKEN_EXPIRES_IN", "3600"))
    REFRESH_TOKEN_EXPIRES_IN: int = int(os.environ.get("REFRESH_TOKEN_EXPIRES_IN", "86400"))
    
    # Stripe
    STRIPE_PUBLISHABLE_KEY: str = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
    STRIPE_SECRET_KEY: str = get_env("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    
    # Admin
    ADMIN_EMAIL: str = os.environ.get("ADMIN_EMAIL", "admin@example.com")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "adminpass")
    
    # AI Models
    OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.environ.get("OLLAMA_MODEL", "llama3.2")
    
    # TTS
    PIPER_MODEL_PATH: str = os.environ.get("PIPER_MODEL_PATH", "/models/piper")
    
    # Whisper
    WHISPER_MODEL_SIZE: str = os.environ.get("WHISPER_MODEL_SIZE", "base")
    
    # Application URLs
    APP_URL: str = os.environ.get("APP_URL", "http://localhost:3000")
    NEXT_PUBLIC_APP_URL: str = os.environ.get("NEXT_PUBLIC_APP_URL", "http://localhost:3000")
    
    # Shutterstock
    SHUTTERSTOCK_API_TOKEN: str = os.environ.get("SHUTTERSTOCK_API_TOKEN", "")
    
    # OAuth (social platforms)
    YOUTUBE_CLIENT_ID: str = os.environ.get("YOUTUBE_CLIENT_ID", "")
    YOUTUBE_CLIENT_SECRET: str = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    YOUTUBE_REDIRECT_URI: str = os.environ.get("YOUTUBE_REDIRECT_URI", "")
    
    INSTAGRAM_CLIENT_ID: str = os.environ.get("INSTAGRAM_CLIENT_ID", "")
    INSTAGRAM_CLIENT_SECRET: str = os.environ.get("INSTAGRAM_CLIENT_SECRET", "")
    INSTAGRAM_REDIRECT_URI: str = os.environ.get("INSTAGRAM_REDIRECT_URI", "")
    
    TIKTOK_CLIENT_ID: str = os.environ.get("TIKTOK_CLIENT_ID", "")
    TIKTOK_CLIENT_SECRET: str = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    TIKTOK_REDIRECT_URI: str = os.environ.get("TIKTOK_REDIRECT_URI", "")
    
    X_CLIENT_ID: str = os.environ.get("X_CLIENT_ID", "")
    X_CLIENT_SECRET: str = os.environ.get("X_CLIENT_SECRET", "")
    X_REDIRECT_URI: str = os.environ.get("X_REDIRECT_URI", "")
    
    # SMTP
    SMTP_HOST: str = os.environ.get("SMTP_HOST", "smtp.example.com")
    SMTP_PORT: int = int(os.environ.get("SMTP_PORT", "587"))
    SMTP_USER: str = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")


settings = Settings()