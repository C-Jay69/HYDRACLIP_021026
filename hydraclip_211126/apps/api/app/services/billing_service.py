"""Billing Service."""

import logging
from typing import Optional

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.billing import Plan, BillingEvent
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)


async def create_checkout_session(plan_id: str, user_id: str) -> str:
    """Create a Stripe checkout session."""
    from app.services.storage_service import upload_file
    
    # Get plan
    result = await AsyncSessionLocal().execute(select(Plan).where(Plan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise ValueError(f"Plan {plan_id} not found")
    
    # In production, this would call Stripe API
    # For now, return a mock URL
    return f"https://checkout.stripe.com/pay/cs_test_{plan_id}_{user_id}"


async def create_portal_session(user_id: str) -> str:
    """Create a Stripe customer portal session."""
    # In production, this would call Stripe API
    return f"https://billing.stripe.com/portal/cus_test_{user_id}"


async def sync_subscription(user_id: str) -> dict:
    """Sync subscription status from Stripe."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Update subscription status
        user.subscription_status = "active"
        user.plan = plan.name if hasattr(plan, 'name') else "Creator"
        user.video_limit_monthly = plan.video_limit_monthly if hasattr(plan, 'video_limit_monthly') else 25
        user.storage_limit_gb = plan.storage_limit_gb if hasattr(plan, 'storage_limit_gb') else 10
        
        await db.commit()
        
        return {
            "plan": user.plan,
            "status": user.subscription_status,
            "video_limit_monthly": user.video_limit_monthly,
            "storage_limit_gb": user.storage_limit_gb,
        }