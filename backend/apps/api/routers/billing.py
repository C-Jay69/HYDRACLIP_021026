"""Stripe billing endpoints: overview, checkout, portal and webhook."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from apps.api.core.deps import CurrentUser, DbSession
from apps.api.models import Plan
from apps.api.schemas.billing import (
    BillingOverview,
    CheckoutRequest,
    CheckoutSessionCreated,
    PortalSessionCreated,
)
from apps.api.services import billing as billing_service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/overview", response_model=BillingOverview)
def billing_overview(db: DbSession, user: CurrentUser) -> BillingOverview:
    """Plans, the caller's current subscription, and what is possible."""
    from apps.api.schemas.billing import PlanPublic, SubscriptionPublic

    plans = billing_service.list_plans(db)
    subscription = billing_service.active_subscription(db, user.id)

    subscription_body = None
    if subscription is not None:
        subscription_body = SubscriptionPublic.model_validate(subscription)
        plan = db.get(Plan, subscription.plan_id)
        if plan is not None:
            subscription_body.plan_name = plan.name

    return BillingOverview(
        plans=[
            PlanPublic(
                id=plan.id,
                name=plan.name,
                video_limit_monthly=plan.video_limit_monthly,
                storage_limit_gb=plan.storage_limit_gb,
                features=plan.features_json or {},
                is_active=plan.is_active,
                checkout_available=billing_service.price_id_for_plan(plan) is not None,
            )
            for plan in plans
        ],
        subscription=subscription_body,
        stripe_configured=billing_service.stripe_configured(),
        publishable_key=(settings_publishable_key()),
    )


def settings_publishable_key() -> str:
    from apps.api.core.config import settings

    return (settings.STRIPE_PUBLISHABLE_KEY or "").strip()


@router.post("/checkout", response_model=CheckoutSessionCreated)
def start_checkout(
    payload: CheckoutRequest, db: DbSession, user: CurrentUser
) -> CheckoutSessionCreated:
    """Open Stripe Checkout for the requested plan."""
    try:
        url = billing_service.create_checkout_session(db, user, payload.plan_name)
    except billing_service.BillingError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except billing_service.BillingUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return CheckoutSessionCreated(checkout_url=url)


@router.post("/portal", response_model=PortalSessionCreated)
def open_portal(db: DbSession, user: CurrentUser) -> PortalSessionCreated:
    """Open the Stripe customer portal (card, cancellation, invoices)."""
    try:
        url = billing_service.create_portal_session(db, user)
    except billing_service.BillingUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return PortalSessionCreated(portal_url=url)


@router.post("/webhook", response_class=Response, status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: DbSession) -> Response:
    """Stripe webhook receiver.

    Deliberately *not* behind ``CurrentUser``: Stripe cannot authenticate.
    Authenticity comes from the ``stripe-signature`` header instead, so the
    raw body is read here — FastAPI's JSON parsing would consume the bytes
    the signature check needs.
    """
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        outcome = billing_service.handle_webhook(db, payload, signature)
    except billing_service.WebhookRejected as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except billing_service.BillingUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return Response(
        content='{"received": "%s"}' % outcome, media_type="application/json"
    )
