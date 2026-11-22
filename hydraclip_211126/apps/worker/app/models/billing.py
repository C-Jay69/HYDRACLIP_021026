"""Billing Models."""

from datetime import datetime, timezone
from typing import Optional

from enum import Enum
from sqlalchemy import (
    Enum as SAEnum,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BillingEventType(str, Enum):
    """Billing event type."""
    SUBSCRIPTION_CREATED = "subscription_created"
    SUBSCRIPTION_UPDATED = "subscription_updated"
    SUBSCRIPTION_CANCELLED = "subscription_cancelled"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    PAYMENT_FAILED = "payment_failed"
    INVOICE_CREATED = "invoice_created"
    INVOICE_PAID = "invoice_paid"
    REFUND = "refund"


class BillingEvent(Base):
    """Billing event model."""
    
    __tablename__ = "billing_events"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stripe_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    event_type: Mapped[BillingEventType] = mapped_column(SAEnum(BillingEventType), nullable=False)
    amount_cents: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="usd", nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    __table_args__ = (
        Index("ix_billing_events_user_id", "user_id"),
        Index("ix_billing_events_stripe_event_id", "stripe_event_id"),
        Index("ix_billing_events_type", "event_type"),
    )


class UsageEvent(Base):
    """Usage event model."""
    
    __tablename__ = "usage_events"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    user: Mapped["User"] = relationship(back_populates="usage_events")

    __table_args__ = (
        Index("ix_usage_events_user_id", "user_id"),
        Index("ix_usage_events_type", "event_type"),
        Index("ix_usage_events_created_at", "created_at"),
    )