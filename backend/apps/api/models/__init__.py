"""Database models for HydraClip.

``Base`` is declared here and every model module is imported at the bottom, so
that importing this package is enough to populate ``Base.metadata`` (needed by
Alembic autogenerate and by ``create_all`` in tests).

Previously this module exported only ``Base``, so ``seed.py``'s
``from apps.api.models import Base, User, Plan, ...`` raised ImportError.
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Imported after Base exists — the model modules do `from . import Base`.
from apps.api.models.project import Project, Video, VideoJob  # noqa: E402
from apps.api.models.schedule import PublishedPost, Schedule  # noqa: E402
from apps.api.models.subscription import Plan, Subscription, UsageEvent  # noqa: E402
from apps.api.models.system import (  # noqa: E402
    AdminAuditLog,
    BillingEvent,
    PlatformToken,
    PromptTemplate,
    SocialAccount,
    SystemSetting,
)
from apps.api.models.user import User  # noqa: E402

__all__ = [
    "Base",
    "AdminAuditLog",
    "BillingEvent",
    "Plan",
    "PlatformToken",
    "Project",
    "PromptTemplate",
    "PublishedPost",
    "Schedule",
    "SocialAccount",
    "Subscription",
    "SystemSetting",
    "UsageEvent",
    "User",
    "Video",
    "VideoJob",
]
