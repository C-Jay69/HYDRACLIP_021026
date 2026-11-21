"""HydraClip Security Module."""

import secrets
import hashlib
import hmac
from typing import Optional
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt as jwtt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 password bearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    **claims,
) -> str:
    """Create a JWT access token."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": str(subject),
        **claims,
    }
    
    encoded = jwtt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwtt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")


def get_token_from_header(authorization: str) -> Optional[str]:
    """Extract JWT token from Authorization header."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def get_current_user(
    token: str = oauth2_scheme,
) -> dict:
    """Get current user from JWT token. Dependency for FastAPI routes."""
    credentials_exception = ValueError("Could not validate credentials")
    
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return {"id": user_id}
    except JWTError:
        raise credentials_exception


async def get_current_user_optional(
    token: Optional[str] = None,
) -> Optional[dict]:
    """Get current user from JWT token (optional)."""
    if token is None:
        return None
    try:
        return await get_current_user(token)
    except Exception:
        return None