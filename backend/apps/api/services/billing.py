"""Stripe billing: plans, checkout, customer portal and webhook bookkeeping.

MVP scope and deliberate simplifications:

* Plans live in the ``plans`` table. The seeded rows carry placeholder price
  ids (``price_free`` / ``price_creator`` / ``price_pro``), so Checkout is
  only offered when a plan has a real price id — either a live one stored on
  the row or an env override (``STRIPE_PRICE_CREATOR`` / ``STRIPE_PRICE_PRO``).
* Subscription state is mirrored locally from Stripe webhooks so quota
  enforcement keeps working without a Stripe call on every request.
* Webhook events are deduplicated through ``billing_events.stripe_event_id``
  (unique column): Stripe retries deliveries, and processing twice would
  resurrect a cancelled subscription.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.api.core.config import settings
from apps.api.models import BillingEvent, Plan, Subscription, User

logger = logging.getLogger(__name__)

#: Price ids that are known placeholders from seed data, not real Stripe objects.
PLACEHOLDER_PRICE_IDS = {"price_free", "price_creator", "price_pro"}

#: Env-var Settings attribute holding a live price id, per plan name.
PRICE_OVERRIDE_ATTRS = {
    "creator": "STRIPE_PRICE_CREATOR",
    "pro": "STRIPE_PRICE_PRO",
}

#: Subscription statuses that count as an active entitlement. These must be
#: values of the ``subscription_status`` Postgres enum — the column is not a
#: free-form string, and writing anything else makes Postgres reject the row
#: (psycopg2.errors.InvalidTextRepresentation).
ACTIVE_SUBSCRIPTION_STATUSES = ("active", "past_due")

#: Stripe reports a few more states than the column can store; fold them into
#: the nearest representable one.
_SUBSCRIPTION_STATUS_MAP = {
    "trialing": "active",
    "unpaid": "past_due",
    "incomplete": "active",
    "incomplete_expired": "cancelled",
}


def normalise_subscription_status(raw: str | None) -> str:
    """Map a Stripe status onto a value the ``subscription_status`` enum allows."""
    value = (raw or "active").strip().lower()
    value = _SUBSCRIPTION_STATUS_MAP.get(value, value)
    return value if value in ("active", "cancelled", "past_due") else "active"


class BillingError(RuntimeError):
    """Request refers to something that does not exist (mapped to 404)."""


class BillingUnavailable(RuntimeError):
    """Stripe is not configured or rejected the call (mapped to 503)."""


class WebhookRejected(RuntimeError):
    """Signature/payload invalid (mapped to 400)."""


def stripe_configured() -> bool:
    return bool((settings.STRIPE_SECRET_KEY or "").strip())


def _stripe():
    if not stripe_configured():
        raise BillingUnavailable(
            "Stripe is not configured on this deployment (STRIPE_SECRET_KEY missing)."
        )
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def price_id_for_plan(plan: Plan) -> str | None:
    """Resolve a usable Stripe price id for a plan, or None."""
    override_attr = PRICE_OVERRIDE_ATTRS.get((plan.name or "").strip().lower(), "")
    if override_attr:
        override = (getattr(settings, override_attr, "") or "").strip()
        if override:
            return override
    stored = (plan.stripe_price_id or "").strip()
    if stored and stored not in PLACEHOLDER_PRICE_IDS:
        return stored
    return None


def fallback_plan(db: Session) -> Plan | None:
    """The plan applied when a user has no active subscription (Free)."""
    return db.scalar(
        select(Plan)
        .where(Plan.is_active.is_(True), func.lower(Plan.name) == "free")
        .limit(1)
    )


def active_subscription(db: Session, user_id: int) -> Subscription | None:
    return db.scalar(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
        .order_by(Subscription.current_period_end.desc().nullslast(), Subscription.id.desc())
        .limit(1)
    )


def plan_for_user(db: Session, user_id: int) -> Plan | None:
    subscription = active_subscription(db, user_id)
    if subscription is not None:
        plan = db.get(Plan, subscription.plan_id)
        if plan is not None:
            return plan
    return fallback_plan(db)


def list_plans(db: Session) -> list[Plan]:
    return list(
        db.scalars(
            select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.id)
        )
    )


def _app_url() -> str:
    return (
        settings.APP_URL
        or settings.NEXT_PUBLIC_APP_URL
        or "http://localhost:3000"
    ).rstrip("/")


def _ensure_customer(db: Session, user: User, stripe) -> str:
    if user.stripe_customer_id:
        return user.stripe_customer_id
    customer = stripe.Customer.create(
        email=user.email,
        name=user.name or None,
        metadata={"user_id": user.id},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    return customer.id


def create_checkout_session(db: Session, user: User, plan_name: str) -> str:
    """Create a Stripe Checkout session for ``plan_name``, returning its URL."""
    stripe = _stripe()
    plan = db.scalar(
        select(Plan).where(
            Plan.is_active.is_(True),
            func.lower(Plan.name) == plan_name.strip().lower(),
        )
    )
    if plan is None:
        raise BillingError(f"No plan named {plan_name!r}.")

    price_id = price_id_for_plan(plan)
    if price_id is None:
        raise BillingUnavailable(
            f"Checkout is not available for the {plan.name} plan yet: no live "
            "Stripe price id is configured for it."
        )

    try:
        customer_id = _ensure_customer(db, user, stripe)
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=f"{_app_url()}/billing?checkout=success",
            cancel_url=f"{_app_url()}/billing?checkout=cancelled",
            metadata={"user_id": user.id, "plan_id": plan.id},
            subscription_data={
                "metadata": {"user_id": user.id, "plan_name": plan.name}
            },
        )
    except BillingError:
        raise
    except Exception as exc:  # stripe.error.StripeError and transport problems
        logger.exception("Stripe checkout session creation failed")
        raise BillingUnavailable(f"Stripe rejected the checkout request: {exc}") from exc

    if not session.url:
        raise BillingUnavailable("Stripe returned a checkout session without a URL.")
    return session.url


def create_portal_session(db: Session, user: User) -> str:
    stripe = _stripe()
    if not user.stripe_customer_id:
        raise BillingUnavailable(
            "You do not have a billing profile yet. Subscribe to a plan first."
        )
    try:
        session = stripe.billingPortal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{_app_url()}/billing",
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stripe portal session creation failed")
        raise BillingUnavailable(f"Stripe rejected the portal request: {exc}") from exc
    return session.url

# --- Webhook processing ------------------------------------------------------


def handle_webhook(db: Session, payload: bytes, signature: str | None) -> str:
    """Verify, deduplicate and apply one Stripe webhook delivery."""
    if not (settings.STRIPE_WEBHOOK_SECRET or "").strip():
        raise BillingUnavailable("STRIPE_WEBHOOK_SECRET is not configured.")
    if not signature:
        raise WebhookRejected("Missing stripe-signature header.")

    stripe = _stripe()
    try:
        event = stripe.Webhook.construct_event(
            payload, signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as exc:
        raise WebhookRejected("Invalid webhook payload.") from exc
    except Exception as exc:  # stripe.error.SignatureVerificationError
        raise WebhookRejected("Webhook signature verification failed.") from exc

    event_id = getattr(event, "id", None)
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_id and (
        db.scalar(
            select(BillingEvent.id).where(BillingEvent.stripe_event_id == event_id)
        )
        is not None
    ):
        return "duplicate ignored"

    handler = {
        "checkout.session.completed": _apply_checkout_session,
        "customer.subscription.created": _apply_subscription_object,
        "customer.subscription.updated": _apply_subscription_object,
        "customer.subscription.deleted": _apply_subscription_object,
    }.get(event_type)

    if handler is not None:
        handler(db, obj)

    db.add(
        BillingEvent(
            user_id=_event_user_id(db, obj),
            stripe_event_id=event_id,
            event_type=event_type,
            metadata_json={"object_id": obj.get("id")} if isinstance(obj, dict) else {},
            status="processed",
        )
    )
    db.commit()
    return "processed"


def _event_user_id(db: Session, obj: Any) -> int | None:
    """Best-effort attribution of a webhook object to a local user."""
    if not isinstance(obj, dict):
        return None
    metadata = obj.get("metadata") or {}
    raw = metadata.get("user_id") or obj.get("client_reference_id")
    if raw and str(raw).isdigit():
        return int(raw)
    customer = obj.get("customer")
    if isinstance(customer, str) and customer.startswith("cus_"):
        user = db.scalar(select(User).where(User.stripe_customer_id == customer))
        if user is not None:
            return user.id
    return None


def _plan_for_price_id(db: Session, price_id: str | None) -> Plan | None:
    if not price_id:
        return None
    plan = db.scalar(select(Plan).where(Plan.stripe_price_id == price_id))
    if plan is not None:
        return plan
    # Env overrides map a price id to a plan name; resolve through them.
    for name, attr in PRICE_OVERRIDE_ATTRS.items():
        if (getattr(settings, attr, "") or "").strip() == price_id:
            return db.scalar(
                select(Plan).where(func.lower(Plan.name) == name).limit(1)
            )
    return None


def _as_naive_utc(timestamp: float | int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None)


def _price_id_of(sub_dict: dict[str, Any]) -> str | None:
    items = sub_dict.get("items", {}).get("data", [])
    if items:
        return (items[0].get("price") or {}).get("id")
    return None


def _apply_checkout_session(db: Session, session_obj: dict[str, Any]) -> None:
    """Fulfil a completed Checkout: mirror the subscription locally."""
    subscription_id = session_obj.get("subscription")
    if not subscription_id:
        logger.warning("checkout.session.completed without a subscription id")
        return

    user_id = _event_user_id(db, session_obj)
    if user_id is None:
        logger.error(
            "Could not resolve the user for checkout session %s", session_obj.get("id")
        )
        return

    stripe = _stripe()
    subscription = stripe.Subscription.retrieve(subscription_id)
    sub_dict = subscription if isinstance(subscription, dict) else subscription.to_dict()

    plan = _plan_for_price_id(db, _price_id_of(sub_dict))
    _upsert_subscription(db, user_id, sub_dict, plan)


def _apply_subscription_object(db: Session, sub_dict: dict[str, Any]) -> None:
    """Mirror subscription state changes (renewals, cancellations, updates)."""
    stripe_id = sub_dict.get("id")
    if not stripe_id:
        return
    existing = db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
    )
    if existing is None:
        # A subscription created outside our checkout (e.g. in the Stripe
        # dashboard). Attribute it via metadata, else ignore: guessing would
        # risk granting someone else's entitlement.
        metadata = sub_dict.get("metadata") or {}
        raw = metadata.get("user_id")
        if not (raw and str(raw).isdigit()):
            logger.warning("Ignoring webhook for unknown subscription %s", stripe_id)
            return
        plan = _plan_for_price_id(db, _price_id_of(sub_dict))
        fallback = fallback_plan(db)
        existing = Subscription(
            user_id=int(raw),
            stripe_subscription_id=stripe_id,
            plan_id=plan.id if plan is not None else (fallback.id if fallback else 0),
        )
        db.add(existing)

    existing.status = normalise_subscription_status(sub_dict.get("status"))
    existing.current_period_start = _as_naive_utc(
        sub_dict.get("current_period_start")
    ) or existing.current_period_start
    existing.current_period_end = _as_naive_utc(sub_dict.get("current_period_end"))
    existing.cancel_at_period_end = bool(sub_dict.get("cancel_at_period_end"))
    db.add(existing)


def _upsert_subscription(
    db: Session,
    user_id: int,
    sub_dict: dict[str, Any],
    plan: Plan | None,
) -> None:
    stripe_id = sub_dict.get("id")
    existing = db.scalar(
        select(Subscription).where(Subscription.stripe_subscription_id == stripe_id)
    )
    if existing is None:
        existing = Subscription(
            user_id=user_id,
            stripe_subscription_id=stripe_id
            or f"unknown_{int(datetime.now(timezone.utc).timestamp())}",
            plan_id=plan.id if plan is not None else 0,
        )
        db.add(existing)
    if plan is not None:
        existing.plan_id = plan.id
    existing.status = normalise_subscription_status(sub_dict.get("status"))
    existing.current_period_start = _as_naive_utc(sub_dict.get("current_period_start"))
    existing.current_period_end = _as_naive_utc(sub_dict.get("current_period_end"))
    existing.cancel_at_period_end = bool(sub_dict.get("cancel_at_period_end"))
    db.add(existing)


def grant_manual_plan(db: Session, user: User, plan: Plan) -> Subscription:
    """Admin override: assign a plan directly, without Stripe.

    Any prior active subscription is cancelled first, so plan lookups resolve
    to exactly one active row. The synthetic stripe id keeps the unique
    constraint happy and marks the row as manual (webhooks never carry it).
    """
    for prior in db.scalars(
        select(Subscription).where(
            Subscription.user_id == user.id,
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
    ):
        prior.status = "cancelled"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    subscription = Subscription(
        user_id=user.id,
        stripe_subscription_id=f"manual_{user.id}_{plan.id}_{int(now.timestamp())}",
        plan_id=plan.id,
        status="active",
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        cancel_at_period_end=False,
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription
