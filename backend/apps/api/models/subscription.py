from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON
from sqlalchemy.sql import func
from . import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    stripe_subscription_id = Column(String, unique=True, index=True, nullable=False)
    plan_id = Column(Integer, nullable=False)
    status = Column(String, default="active")  # active, cancelled, past_due
    current_period_start = Column(DateTime, default=func.now())
    current_period_end = Column(DateTime, nullable=False)
    cancel_at_period_end = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # Free, Creator, Pro
    stripe_price_id = Column(String, unique=True, nullable=False)
    video_limit_monthly = Column(Integer, default=0)  # 0 = unlimited
    storage_limit_gb = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    features_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)  # video_generated, video_published, storage_used
    quantity = Column(Integer, default=1)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())