from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from . import Base


class SocialAccount(Base):
    """A connected publishing account and its live OAuth credentials.

    This table is the single source of truth for platform credentials. The
    ``platform_tokens`` table below stores the same secrets and is therefore
    deliberately left unwritten -- see the note on that class.

    The ``*_encrypted`` columns hold Fernet ciphertext produced by
    ``apps.api.services.crypto``. Never assign a plaintext token to them
    directly; go through ``apps.api.services.social_accounts``.
    """

    __tablename__ = "social_accounts"
    __table_args__ = (
        # Reconnecting the same channel must update the existing row rather
        # than pile up duplicates, while still allowing one user to connect
        # several accounts on the same platform.
        UniqueConstraint(
            "user_id", "platform", "account_id", name="uq_social_account_identity"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    platform = Column(String, nullable=False)  # youtube, instagram, tiktok, x
    account_name = Column(String, nullable=False)
    account_id = Column(String, nullable=True)  # Platform-specific ID
    access_token_encrypted = Column(String, nullable=False)
    refresh_token_encrypted = Column(String, nullable=True)
    token_type = Column(String, default="Bearer")
    scope = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    #: Set when a refresh fails irrecoverably, so the UI can say why the
    #: account stopped working instead of silently failing every post.
    last_error = Column(Text, nullable=True)
    connected_at = Column(DateTime, default=func.now())
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class PlatformToken(Base):
    """Unused. Retained only so the mapped schema matches existing databases.

    This table duplicates every credential field already on
    ``social_accounts``. Writing tokens to both would double the blast radius
    of a leak and leave two rows disagreeing about which token is current
    after a refresh, so the application reads and writes ``social_accounts``
    exclusively. Dropping this table is a separate migration, deliberately
    not bundled with the OAuth work.
    """

    __tablename__ = "platform_tokens"

    id = Column(Integer, primary_key=True, index=True)
    social_account_id = Column(Integer, nullable=False)
    access_token_encrypted = Column(String, nullable=False)
    refresh_token_encrypted = Column(String, nullable=True)
    token_type = Column(String, default="Bearer")
    scope = Column(String, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=False)  # user, subscription, video, project, etc.
    target_id = Column(Integer, nullable=True)
    metadata_json = Column(JSON, default=dict)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(String, nullable=True)
    value_type = Column(String, default="string")  # string, integer, boolean, json
    description = Column(String, nullable=True)
    updated_by = Column(Integer, nullable=True)  # admin user ID
    updated_at = Column(DateTime, default=func.now())


class PromptTemplate(Base):
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    category = Column(String, nullable=False)
    script = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class BillingEvent(Base):
    __tablename__ = "billing_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    stripe_event_id = Column(String, unique=True, nullable=True)
    event_type = Column(String, nullable=False)  # checkout.session.completed, invoice.payment_succeeded, etc.
    amount = Column(Integer, nullable=True)  # in cents
    currency = Column(String, default="usd")
    status = Column(String, default="pending")
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())