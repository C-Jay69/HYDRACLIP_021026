"""HydraClip Rate Limiter Module."""

import time
from typing import Optional

from fastapi import Request,  HTTPException, status
from redis import Redis

from app.config import get_settings

settings = get_settings()

redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """Get or create Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = Redis.from_url(settings.redis_url, decode_responses=True)
    return redis_client


class RateLimiter:
    """Simple sliding window rate limiter."""

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def check(self, key: str) -> bool:
        """Check if request is allowed. Returns True if allowed."""
        try:
            redis = get_redis()
            now = time.time()
            window_start = now - self.window_seconds

            redis.zremrangebyscore(key, 0, window_start)
            current = redis.zcard(key)

            if current >= self.max_requests:
                return False

            redis.zadd(key, {str(now): now})
            redis.expire(key, self.window_seconds)
            return True
        except Exception:
            # If Redis is unavailable, allow the request (fail open)
            return True

    def get_remaining(self, key: str) -> int:
        """Get remaining requests in window."""
        try:
            redis = get_redis()
            now = time.time()
            window_start = now - self.window_seconds
            redis.zremrangebyscore(key, 0, window_start)
            current = redis.zcard(key)
            return max(0, self.max_requests - current)
        except Exception:
            return self.max_requests


# Pre-configured limiters
auth_limiter = RateLimiter(max_requests=settings.rate_limit_auth, window_seconds=60)
general_limiter = RateLimiter(max_requests=settings.rate_limit_general, window_seconds=60)
generation_limiter = RateLimiter(max_requests=settings.rate_limit_generation, window_seconds=60)


def get_client_ip(request: Request) -> str:
    """Get client IP address from request."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def rate_limit_auth(request: Request) -> None:
    """Rate limit dependency for auth endpoints."""
    ip = get_client_ip(request)
    key = f"rate_limit:auth:{ip}"
    if not auth_limiter.check(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please try again later.",
        )


async def rate_limit_general(request: Request) -> None:
    """Rate limit dependency for general endpoints."""
    ip = get_client_ip(request)
    key = f"rate_limit:general:{ip}"
    if not general_limiter.check(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please slow down.",
        )


async def rate_limit_generation(request: Request) -> None:
    """Rate limit dependency for video generation endpoints."""
    ip = get_client_ip(request)
    key = f"rate_limit:generation:{ip}"
    if not generation_limiter.check(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many generation requests. Please wait before trying again.",
        )