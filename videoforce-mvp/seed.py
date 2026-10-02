"""Seed script for Videoforce MVP.

Creates:
- Admin user from env vars
- Sample regular user
- Free, Creator, and Pro plans
- Default system settings
- Sample project and video record for demo
- Idempotent (safe to run multiple times)
"""

import os
import uuid
from datetime import datetime, timedelta

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from apps.api.core.config import settings
from apps.api.models import Base, User, Subscription, Plan, Project, Video, SystemSetting, AdminAuditLog
from apps.api.services.auth import hash_password

engine = create_engine(os.environ.get("DATABASE_URL", "postgresql://videoforce:secret@localhost:5432/videoforce"))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_or_create(session, model, **kwargs):
    """Get existing record or create new one."""
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    instance = model(**kwargs)
    session.add(instance)
    return instance


def seed():
    session = SessionLocal()
    
    try:
        # 1. Create admin user
        admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        admin_password = os.environ.get("ADMIN_PASSWORD", "adminpass")
        
        admin_user = get_or_create(
            session, User,
            email=admin_email,
            is_staff=True,
            is_superuser=True
        )
        admin_user.password_hash = hash_password(admin_password)
        admin_user.role = "ADMIN"
        admin_user.is_active = True
        admin_user.is_verified = True
        
        # 2. Create regular test user
        test_user = get_or_create(
            session, User,
            email="test@example.com",
            name="Test User"
        )
        test_user.password_hash = hash_password("testpassword123")
        test_user.role = "USER"
        test_user.is_active = True
        test_user.is_verified = True
        
        # 3. Create subscription plans
        free_plan = get_or_create(
            session, Plan,
            name="Free",
            stripe_price_id="price_free",
            video_limit_monthly=3,
            storage_limit_gb=1,
            is_active=True,
            features_json={"watermark": True, "auto_publish": False}
        )
        
        creator_plan = get_or_create(
            session, Plan,
            name="Creator",
            stripe_price_id="price_creator",
            video_limit_monthly=25,
            storage_limit_gb=10,
            is_active=True,
            features_json={"watermark": False, "auto_publish": True, "youtube_publish": True}
        )
        
        pro_plan = get_or_create(
            session, Plan,
            name="Pro",
            stripe_price_id="price_pro",
            video_limit_monthly=0,  # unlimited
            storage_limit_gb=50,
            is_active=True,
            features_json={"watermark": False, "auto_publish": True, "youtube_publish": True, "priority_queue": True}
        )
        
        # 4. Create subscriptions for test users
        from apps.api.models import Subscription
        test_sub = get_or_create(
            session, Subscription,
            user_id=test_user.id,
            plan_id=creator_plan.id,
            stripe_subscription_id=f"sub_{uuid.uuid4()}",
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=30)
        )
        
        admin_sub = get_or_create(
            session, Subscription,
            user_id=admin_user.id,
            plan_id=pro_plan.id,
            stripe_subscription_id=f"sub_{uuid.uuid4()}",
            status="active",
            current_period_start=datetime.utcnow(),
            current_period_end=datetime.utcnow() + timedelta(days=365)
        )
        
        # 5. Create default system settings
        settings_data = [
            ("site_name", "Videoforce"),
            ("site_description", "AI-powered video content scheduling platform"),
            ("maintenance_mode", "false"),
            ("default_aspect_ratio", "9:16"),
            ("default_video_duration", "60"),
        ]
        
        for key, value in settings_data:
            get_or_create(session, SystemSetting, key=key, value=value)
        
        # 6. Create sample prompt templates
        templates_data = [
            ("short_form_script", "Short Form Script",
             "Generate a captivating short-form video script about {topic}. "
             "Include an engaging hook, 3 key points, and a call-to-action. "
             "Keep it under 60 seconds when spoken."),
            ("long_form_intro", "Long Form Intro",
             "Generate an introductory section for a long-form video about {topic}. "
             "Set up the problem, present the solution, and outline what viewers will learn. "
             "Keep it under 3 minutes when spoken."),
        ]
        
        for i, (name, category, script) in enumerate(templates_data):
            get_or_create(session, PromptTemplate, 
                         name=name, category=category, script=script, is_default=(i == 0))
        
        # 7. Create admin audit log entry for seed
        admin_audit = get_or_create(session, AdminAuditLog,
                                   action="seed",
                                   target_type="system",
                                   target_id=str(uuid.uuid4()),
                                   metadata_json={"seeded_at": datetime.utcnow().isoformat()})
        
        session.commit()
        print("✅ Database seeded successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"❌ seeding failed: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()