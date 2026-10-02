"""Per-plan usage quotas.

The schema has had ``plans.video_limit_monthly``, ``subscriptions`` and
``usage_events`` since the initial migration, but nothing ever read or wrote
them. This module turns them into an enforced limit.

Counting is done from ``usage_events`` rather than by counting ``videos`` rows,
so that deleting a video does not refund quota for the period — matching how
metered billing is normally expected to behave.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.models import Plan, Subscription, UsageEvent

#: Usage event emitted once per video generation request.
EVENT_VIDEO_GENERATED = "video_generated"

#: Applied when a user has no active subscription at all.
FALLBACK_PLAN_NAME = "Free"
FALLBACK_VIDEO_LIMIT = 3

UNLIMITED = 0


@dataclass(frozen=True)
class Quota:
    plan_name: str
    limit_monthly: int
    used: int
    period_start: datetime
    period_end: datetime

    @property
    def unlimited(self) -> bool:
        return self.limit_monthly == UNLIMITED

    @property
    def remaining(self) -> int | None:
        if self.unlimited:
            return None
        return max(0, self.limit_monthly - self.used)

    @property
    def exhausted(self) -> bool:
        return not self.unlimited and self.used >= self.limit_monthly


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _calendar_month_window(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # First day of the following month.
    end = (start + timedelta(days=32)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return start, end


def _as_aware(value: datetime | None) -> datetime | None:
    """Treat naive timestamps from the database as UTC."""
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def get_active_plan(db: Session, user_id: int) -> tuple[Plan | None, Subscription | None]:
    """Return the user's active plan and subscription, if any."""
    subscription = db.scalar(
        select(Subscription)
        .where(Subscription.user_id == user_id, Subscription.status == "active")
        .order_by(Subscription.current_period_end.desc())
    )
    if subscription is None:
        return None, None

    return db.get(Plan, subscription.plan_id), subscription


def get_quota(db: Session, user_id: int) -> Quota:
    """Compute the caller's video allowance for the current period."""
    now = _utcnow()
    plan, subscription = get_active_plan(db, user_id)

    if plan is None:
        plan_name = FALLBACK_PLAN_NAME
        limit = FALLBACK_VIDEO_LIMIT
    else:
        plan_name = plan.name
        limit = plan.video_limit_monthly if plan.video_limit_monthly is not None else UNLIMITED

    period_start = _as_aware(subscription.current_period_start) if subscription else None
    period_end = _as_aware(subscription.current_period_end) if subscription else None

    # Fall back to the calendar month when there is no usable billing window.
    if period_start is None or period_end is None or not (period_start <= now < period_end):
        period_start, period_end = _calendar_month_window(now)

    used = db.scalar(
        select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
            UsageEvent.user_id == user_id,
            UsageEvent.event_type == EVENT_VIDEO_GENERATED,
            UsageEvent.created_at >= period_start.replace(tzinfo=None),
            UsageEvent.created_at < period_end.replace(tzinfo=None),
        )
    )

    return Quota(
        plan_name=plan_name,
        limit_monthly=limit,
        used=int(used or 0),
        period_start=period_start,
        period_end=period_end,
    )


def assert_quota_available(db: Session, user_id: int) -> Quota:
    """Raise 402 when the caller has used their monthly allowance."""
    quota = get_quota(db, user_id)

    if quota.exhausted:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                f"Monthly video limit reached for the {quota.plan_name} plan "
                f"({quota.used}/{quota.limit_monthly}). Upgrade to continue."
            ),
        )

    return quota


def record_video_generated(
    db: Session,
    user_id: int,
    video_id: int | None = None,
    quantity: int = 1,
) -> UsageEvent:
    """Write the usage event that quota counting reads."""
    event = UsageEvent(
        user_id=user_id,
        event_type=EVENT_VIDEO_GENERATED,
        quantity=quantity,
        metadata_json={"video_id": video_id} if video_id is not None else {},
    )
    db.add(event)
    db.flush()
    return event
