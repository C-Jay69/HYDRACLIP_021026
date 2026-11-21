"""Webhooks Router."""

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.webhook_service import handle_stripe_webhook
import secrets

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = await handle_stripe_webhook(payload, sig_header, db)
        return {"success": True, "event_id": event.id}
    except Exception as e:
        # Log the error
        from app.models.webhook_event import WebhookEvent
        event = WebhookEvent(
            id=secrets.token_urlsafe(16),
            provider="stripe",
            event_id="unknown",
            event_type="unknown",
            payload_json=payload.decode(),
            processed=False,
            error_message=str(e),
        )
        db.add(event)
        await db.commit()
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")