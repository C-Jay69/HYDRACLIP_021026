"""Quota accounting rules, tested directly against the service.

The HTTP surface is covered in test_videos.py; this file pins the arithmetic
and the 402 gate that the generation endpoint will depend on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from apps.api.models import Plan, Subscription, UsageEvent
from apps.api.services import quota as quota_service


def _plan(db, name: str, limit: int) -> Plan:
    plan = Plan(
        name=name,
        stripe_price_id=f"price_{name.lower()}",
        video_limit_monthly=limit,
        is_active=True,
    )
    db.add(plan)
    db.flush()
    return plan


def _subscribe(db, user_id: int, plan: Plan, status: str = "active", days_ago: int = 5):
    now = datetime.now(timezone.utc)
    sub = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        stripe_subscription_id=f"sub_{user_id}_{plan.id}_{status}",
        status=status,
        current_period_start=now - timedelta(days=days_ago),
        current_period_end=now + timedelta(days=30 - days_ago),
    )
    db.add(sub)
    db.commit()
    return sub


def test_no_subscription_gets_the_free_fallback(db, make_user):
    user = make_user()
    quota = quota_service.get_quota(db, user.id)

    assert quota.plan_name == quota_service.FALLBACK_PLAN_NAME
    assert quota.limit_monthly == quota_service.FALLBACK_VIDEO_LIMIT
    assert quota.used == 0
    assert quota.remaining == quota_service.FALLBACK_VIDEO_LIMIT
    assert quota.exhausted is False


def test_remaining_never_goes_negative(db, make_user):
    user = make_user()
    for _ in range(10):
        quota_service.record_video_generated(db, user.id)
    db.commit()

    quota = quota_service.get_quota(db, user.id)
    assert quota.used == 10
    assert quota.remaining == 0
    assert quota.exhausted is True


def test_quantity_is_summed_not_counted(db, make_user):
    """One event with quantity=3 must consume three of the allowance."""
    user = make_user()
    quota_service.record_video_generated(db, user.id, quantity=3)
    db.commit()

    assert quota_service.get_quota(db, user.id).used == 3


def test_other_event_types_do_not_consume_quota(db, make_user):
    user = make_user()
    db.add(
        UsageEvent(user_id=user.id, event_type="video_published", quantity=5)
    )
    db.commit()

    assert quota_service.get_quota(db, user.id).used == 0


def test_unlimited_plan_is_never_exhausted(db, make_user):
    user = make_user()
    _subscribe(db, user.id, _plan(db, "Enterprise", quota_service.UNLIMITED))

    for _ in range(50):
        quota_service.record_video_generated(db, user.id)
    db.commit()

    quota = quota_service.get_quota(db, user.id)
    assert quota.unlimited is True
    assert quota.remaining is None
    assert quota.exhausted is False


def test_assert_quota_available_passes_under_the_limit(db, make_user):
    user = make_user()
    quota = quota_service.assert_quota_available(db, user.id)
    assert quota.remaining == quota_service.FALLBACK_VIDEO_LIMIT


def test_assert_quota_available_raises_402_when_exhausted(db, make_user):
    user = make_user()
    for _ in range(quota_service.FALLBACK_VIDEO_LIMIT):
        quota_service.record_video_generated(db, user.id)
    db.commit()

    with pytest.raises(HTTPException) as exc:
        quota_service.assert_quota_available(db, user.id)

    assert exc.value.status_code == 402
    assert "Upgrade to continue" in exc.value.detail
    assert quota_service.FALLBACK_PLAN_NAME in exc.value.detail


def test_usage_outside_the_subscription_window_is_excluded(db, make_user):
    user = make_user()
    _subscribe(db, user.id, _plan(db, "Pro", 50), days_ago=5)

    db.add(
        UsageEvent(
            user_id=user.id,
            event_type=quota_service.EVENT_VIDEO_GENERATED,
            quantity=1,
            created_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )
    db.commit()

    assert quota_service.get_quota(db, user.id).used == 0


def test_period_resets_with_the_billing_window(db, make_user):
    """Usage inside the current window counts; the previous window does not."""
    user = make_user()
    _subscribe(db, user.id, _plan(db, "Pro", 50), days_ago=2)

    db.add_all(
        [
            UsageEvent(
                user_id=user.id,
                event_type=quota_service.EVENT_VIDEO_GENERATED,
                quantity=1,
                created_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
            UsageEvent(
                user_id=user.id,
                event_type=quota_service.EVENT_VIDEO_GENERATED,
                quantity=1,
                created_at=datetime.now(timezone.utc) - timedelta(days=40),
            ),
        ]
    )
    db.commit()

    assert quota_service.get_quota(db, user.id).used == 1


def test_expired_subscription_window_falls_back_to_calendar_month(db, make_user):
    """A stale period_end must not freeze quota at its old window."""
    user = make_user()
    plan = _plan(db, "Pro", 50)
    now = datetime.now(timezone.utc)
    db.add(
        Subscription(
            user_id=user.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_stale",
            status="active",
            current_period_start=now - timedelta(days=120),
            current_period_end=now - timedelta(days=90),
        )
    )
    db.commit()

    quota = quota_service.get_quota(db, user.id)
    # Plan still applies, but the window is this calendar month.
    assert quota.plan_name == "Pro"
    assert quota.period_start <= now < quota.period_end


def test_record_video_generated_stores_the_video_id(db, make_user):
    user = make_user()
    event = quota_service.record_video_generated(db, user.id, video_id=42)
    db.commit()

    assert event.event_type == quota_service.EVENT_VIDEO_GENERATED
    assert event.metadata_json == {"video_id": 42}
