"""Social Account and Platform Token Models."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SocialAccountStatus(str, Enum):
    """Social account status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class SocialAccount(Base):
    """Social account model."""
    
    __tablename__ = "social_accounts"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)  # youtube, instagram, tiktok, x
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="social_accounts")
    platform_tokens: Mapped[list["PlatformToken"]] = relationship(back_populates="social_account", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_social_accounts_user_id", "user_id"),
        Index("ix_social_accounts_platform", "platform"),
    )


class PlatformToken(Base):
    """Platform token model (encrypted)."""
    
    __tablename__ = "platform_tokens"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    social_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    token_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False
    )
    
    # Relationships
    social_account: Mapped["SocialAccount"] = relationship(back_populates="platform_tokens")
    
    __table_args__ = (
        Index("ix_platform_tokens_social_account_id", "social_account_id"),
    )