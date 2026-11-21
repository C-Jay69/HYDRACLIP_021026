"""Health Router."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "hydraclip-api"}


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """Readiness check endpoint."""
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ready", "service": "hydraclip-api", "database": "connected"}
    except Exception as e:
        return {"status": "not ready", "service": "hydraclip-api", "database": "disconnected", "error": str(e)}