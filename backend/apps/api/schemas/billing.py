"""Billing contracts: plans, subscriptions, checkout and portal URLs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlanPublic(BaseModel):
    """A plan as shown on the pricing and billing pages."""

    id: int
    name: str
    video_limit_monthly: int = Field(description="0 means unlimited.")
    storage_limit_gb: int
    features: dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    checkout_available: bool = Field(
        description=(
            "Whether a Stripe Checkout session can be created for this plan "
            "(Stripe configured and a real price id known)."
        )
    )


class SubscriptionPublic(BaseModel):
    """The caller's mirrored subscription state."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_id: int
    plan_name: str | None = Field(
        default=None, description="Resolved from the plan when available."
    )
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class BillingOverview(BaseModel):
    """Everything the billing page renders, in one call."""

    plans: list[PlanPublic]
    subscription: SubscriptionPublic | None = None
    stripe_configured: bool
    publishable_key: str = Field(
        description="Empty when Stripe publishable key is not set."
    )


class CheckoutRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    plan_name: str = Field(min_length=1, max_length=50)


class CheckoutSessionCreated(BaseModel):
    checkout_url: str


class PortalSessionCreated(BaseModel):
    portal_url: str