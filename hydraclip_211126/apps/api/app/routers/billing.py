"""Billing Router."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import oauth2_scheme, decode_token
from app.models.user import User
from app.models.billing import BillingEvent
from app.models.user import Plan

router = APIRouter(prefix="/billing", tags=["billing"])


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current user from token."""
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/plans")
async def get_plans(db: AsyncSession = Depends(get_db)):
    """Get available subscription plans."""
    result = await db.execute(
        select(Plan).where(Plan.is_active == True).order_by(Plan.price_cents)
    )
    plans = result.scalars().all()
    
    return [
        {
            "id": p.id,
            "name": p.name,
            "price_cents": p.price_cents,
            "price_display": f"${p.price_cents / 100:.2f}",
            "interval": "month",
            "video_limit_monthly": p.video_limit_monthly,
            "storage_limit_gb": p.storage_limit_gb,
            "features": p.features_json,
            "stripe_price_id": p.stripe_price_id,
            "is_active": p.is_active,
        }
        for p in plans
    ]


@router.post("/checkout")
async def create_checkout(
    plan_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe checkout session."""
    from app.services.billing_service import create_checkout_session

    try:
        checkout_url = await create_checkout_session(plan_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"checkout_url": checkout_url}


@router.get("/portal")
async def create_portal(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create Stripe customer portal session."""
    from app.services.billing_service import create_portal_session
    
    portal_url = await create_portal_session(user.id)
    return {"portal_url": portal_url}


@router.get("/subscription")
async def get_subscription(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user subscription."""
    result = await db.execute(
        select(BillingEvent).where(BillingEvent.user_id == user.id).order_by(BillingEvent.created_at.desc())
    )
    events = result.scalars().all()
    
    return {
        "plan": user.plan,
        "status": user.subscription_status,
        "video_limit_monthly": user.video_limit_monthly,
        "storage_limit_gb": user.storage_limit_gb,
    }