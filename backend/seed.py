"""Seed script for HydraClip.

Creates:
- Admin user from env vars
- Sample regular user
- Free, Creator and Pro plans
- Active subscriptions for both users
- Default system settings and prompt templates
- A sample project and video record for demos
- An audit log entry recording the seed

Genuinely idempotent: re-running updates existing rows instead of duplicating
them.

Fixed in this pass:
- imported ``hash_password`` from ``apps.api.services.auth``, which did not exist
- passed ``is_staff`` / ``is_superuser`` to ``User``, which has neither column
- used ``PromptTemplate`` without importing it (NameError)
- wrote a UUID string into ``AdminAuditLog.target_id`` (an Integer column) and
  omitted the non-nullable ``admin_id``
- keyed ``get_or_create`` on every field including freshly generated UUIDs, so
  each run inserted duplicate subscriptions
- never created the sample project/video the docstring promised
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from apps.api.core.db import SessionLocal
from apps.api.models import (
    AdminAuditLog,
    Plan,
    Project,
    PromptTemplate,
    Subscription,
    SystemSetting,
    User,
    Video,
)
from apps.api.services.auth import hash_password


def utcnow() -> datetime:
    """Timezone-aware UTC now (``datetime.utcnow()`` is deprecated)."""
    return datetime.now(timezone.utc)


def get_or_create(session, model, defaults: dict[str, Any] | None = None, **lookup):
    """Fetch a row by its natural key, creating or updating it as needed.

    ``lookup`` identifies the row; ``defaults`` holds the mutable attributes.
    The previous implementation matched on *every* field, so changing a quota
    produced a second row instead of updating the first.
    """
    instance = session.query(model).filter_by(**lookup).first()
    values = defaults or {}

    if instance is None:
        instance = model(**lookup, **values)
        session.add(instance)
        session.flush()  # assign the primary key for downstream references
        return instance

    for key, value in values.items():
        setattr(instance, key, value)
    return instance


def seed() -> None:
    session = SessionLocal()

    try:
        # --- 1. Admin user -------------------------------------------------
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
        admin_password = os.environ.get("ADMIN_PASSWORD", "adminpass")

        admin_user = get_or_create(
            session,
            User,
            defaults={
                "name": "Administrator",
                "password_hash": hash_password(admin_password),
                "role": "ADMIN",
                "is_active": True,
                "is_verified": True,
            },
            email=admin_email,
        )

        # --- 2. Regular test user ------------------------------------------
        test_user = get_or_create(
            session,
            User,
            defaults={
                "name": "Test User",
                "password_hash": hash_password("testpassword123"),
                "role": "USER",
                "is_active": True,
                "is_verified": True,
            },
            email="test@example.com",
        )

        # --- 3. Subscription plans ------------------------------------------
        free_plan = get_or_create(
            session,
            Plan,
            defaults={
                "stripe_price_id": "price_free",
                "video_limit_monthly": 3,
                "storage_limit_gb": 1,
                "is_active": True,
                "features_json": {"watermark": True, "auto_publish": False},
            },
            name="Free",
        )

        creator_plan = get_or_create(
            session,
            Plan,
            defaults={
                "stripe_price_id": "price_creator",
                "video_limit_monthly": 25,
                "storage_limit_gb": 10,
                "is_active": True,
                "features_json": {
                    "watermark": False,
                    "auto_publish": True,
                    "youtube_publish": True,
                },
            },
            name="Creator",
        )

        pro_plan = get_or_create(
            session,
            Plan,
            defaults={
                "stripe_price_id": "price_pro",
                "video_limit_monthly": 0,  # 0 == unlimited
                "storage_limit_gb": 50,
                "is_active": True,
                "features_json": {
                    "watermark": False,
                    "auto_publish": True,
                    "youtube_publish": True,
                    "priority_queue": True,
                },
            },
            name="Pro",
        )

        # --- 4. Subscriptions ------------------------------------------------
        # Keyed on (user, plan) so repeat runs do not stack up new rows.
        get_or_create(
            session,
            Subscription,
            defaults={
                "stripe_subscription_id": f"sub_seed_{test_user.id}_{creator_plan.id}",
                "status": "active",
                "current_period_start": utcnow(),
                "current_period_end": utcnow() + timedelta(days=30),
            },
            user_id=test_user.id,
            plan_id=creator_plan.id,
        )

        get_or_create(
            session,
            Subscription,
            defaults={
                "stripe_subscription_id": f"sub_seed_{admin_user.id}_{pro_plan.id}",
                "status": "active",
                "current_period_start": utcnow(),
                "current_period_end": utcnow() + timedelta(days=365),
            },
            user_id=admin_user.id,
            plan_id=pro_plan.id,
        )

        # --- 5. System settings ----------------------------------------------
        settings_data = [
            ("site_name", "HydraClip", "string"),
            ("site_description", "AI-powered video content scheduling platform", "string"),
            ("maintenance_mode", "false", "boolean"),
            ("default_aspect_ratio", "9:16", "string"),
            ("default_video_duration", "60", "integer"),
        ]
        for key, value, value_type in settings_data:
            get_or_create(
                session,
                SystemSetting,
                defaults={"value": value, "value_type": value_type},
                key=key,
            )

        # --- 6. Prompt templates ----------------------------------------------
        templates_data = [
            (
                "short_form_script",
                "Short Form Script",
                "Generate a captivating short-form video script about {topic}. "
                "Include an engaging hook, 3 key points, and a call-to-action. "
                "Keep it under 60 seconds when spoken.",
                True,
            ),
            (
                "long_form_intro",
                "Long Form Intro",
                "Generate an introductory section for a long-form video about {topic}. "
                "Set up the problem, present the solution, and outline what viewers "
                "will learn. Keep it under 3 minutes when spoken.",
                False,
            ),
        ]
        for name, category, script, is_default in templates_data:
            get_or_create(
                session,
                PromptTemplate,
                defaults={"category": category, "script": script, "is_default": is_default},
                name=name,
            )

        # --- 7. Sample project and video --------------------------------------
        sample_project = get_or_create(
            session,
            Project,
            defaults={
                "topic": "How AI is changing video production",
                "status": "completed",
                "settings_json": {"aspect_ratio": "9:16", "target_duration": 60},
            },
            user_id=test_user.id,
            title="Demo project",
        )

        get_or_create(
            session,
            Video,
            defaults={
                "user_id": test_user.id,
                "status": "completed",
                "script_text": (
                    "Three ways AI is quietly rewriting how video gets made..."
                ),
                "duration_seconds": 58,
                "resolution": "1080x1920",
                "format": "mp4",
                "generation_params_json": {"model": "llama3.2", "voice": "piper-en-us"},
            },
            project_id=sample_project.id,
            storage_key=f"demo/{sample_project.id}/final.mp4",
        )

        # --- 8. Audit log -----------------------------------------------------
        # admin_id is NOT NULL and target_id is an Integer column.
        session.add(
            AdminAuditLog(
                admin_id=admin_user.id,
                action="seed",
                target_type="system",
                target_id=None,
                metadata_json={"seeded_at": utcnow().isoformat(), "run": uuid.uuid4().hex},
            )
        )

        session.commit()
        print("✅ Database seeded successfully!")
        print(f"   admin: {admin_email}")
        print("   user:  test@example.com / testpassword123")

    except Exception as exc:
        session.rollback()
        print(f"❌ Seeding failed: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
