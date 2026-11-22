"""Billing Service."""

import logging
from typing import Optional

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.billing import BillingEvent
from app.models.user import Plan, Subscription, User

logger = logging.getLogger(__name__)


async def create_checkout_session(plan_id: str, user_id: str) -> str:
    """Create a Stripe checkout session."""
    # Get plan
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Plan).where(Plan.id == plan_id))
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

        # Find the user's active subscription, falling back to an existing plan
        sub_result = await db.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        subscription = sub_result.scalar_one_or_none()

        plan = None
        if subscription is not None:
            plan_result = await db.execute(
                select(Plan).where(Plan.id == subscription.plan_id)
            )
            plan = plan_result.scalar_one_or_none()

        # Update subscription status
        user.subscription_status = subscription.status if subscription else "active"
        if plan is not None:
            user.plan = plan.name
            user.video_limit_monthly = plan.video_limit_monthly
            user.storage_limit_gb = plan.storage_limit_gb

        await db.commit()

        return {
            "plan": user.plan,
            "status": user.subscription_status,
            "video_limit_monthly": user.video_limit_monthly,
            "storage_limit_gb": user.storage_limit_gb,
        }
