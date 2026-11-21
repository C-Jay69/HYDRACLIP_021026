"""Seed Script for HydraClip Database."""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import AsyncSessionLocal, Base, async_engine
from app.core.security import get_password_hash
from app.models.user import User, UserRole, PlanTier
from app.models.billing import Plan
from app.models.system import SystemSetting, PromptTemplate
from app.config import get_settings

settings = get_settings()


async def create_tables():
    """Create all database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created")


async def seed():
    """Seed the database with initial data."""
    async with AsyncSessionLocal() as db:
        # Check if already seeded
        from sqlalchemy import select
        result = await db.execute(select(User).limit(1))
        if result.scalar_one_or_none():
            print("⚠ Database already seeded, skipping...")
            return

        # Create admin user
        admin = User(
            id="user_admin",
            email=settings.admin_email,
            password_hash=get_password_hash(settings.admin_password),
            name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
            plan="Pro",
            video_limit_monthly=-1,
            storage_limit_gb=50,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(admin)

        # Create test user
        test_user = User(
            id="user_test",
            email="test@example.com",
            password_hash=get_password_hash("testpassword123"),
            name="Test User",
            role=UserRole.USER,
            is_active=True,
            is_verified=True,
            plan="Creator",
            video_limit_monthly=25,
            storage_limit_gb=10,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(test_user)

        # Create plans
        plans = [
            Plan(
                id="plan_free",
                name="Free",
                stripe_price_id=None,
                video_limit_monthly=3,
                storage_limit_gb=1,
                features_json='["3 videos/month", "1GB storage", "Watermark", "Download only"]',
                price_cents=0,
                is_active=True,
            ),
            Plan(
                id="plan_creator",
                name="Creator",
                stripe_price_id=settings.stripe_creator_price_id,
                video_limit_monthly=25,
                storage_limit_gb=10,
                features_json='["25 videos/month", "10GB storage", "No watermark", "YouTube auto-publish", "HD resolution"]',
                price_cents=1900,
                is_active=True,
            ),
            Plan(
                id="plan_pro",
                name="Pro",
                stripe_price_id=settings.stripe_pro_price_id,
                video_limit_monthly=-1,
                storage_limit_gb=50,
                features_json='["Unlimited videos", "50GB storage", "No watermark", "Priority queue", "All platforms", "HD resolution"]',
                price_cents=4900,
                is_active=True,
            ),
        ]
        for plan in plans:
            db.add(plan)

        # Create system settings
        settings_data = [
            SystemSetting(
                key="maintenance_mode",
                value="false",
                value_type="boolean",
                description="Global maintenance mode toggle",
            ),
            SystemSetting(
                key="default_video_format",
                value="short",
                value_type="string",
                description="Default video format for new projects",
            ),
            SystemSetting(
                key="default_aspect_ratio",
                value="9:16",
                value_type="string",
                description="Default aspect ratio for new videos",
            ),
            SystemSetting(
                key="default_language",
                value="en",
                value_type="string",
                description="Default language for generation",
            ),
            SystemSetting(
                key="default_voice",
                value="en-US-AriaNeural",
                value_type="string",
                description="Default TTS voice",
            ),
            SystemSetting(
                key="default_tts_engine",
                value="edge",
                value_type="string",
                description="Default TTS engine (edge/piper)",
            ),
            SystemSetting(
                key="max_concurrent_jobs",
                value="3",
                value_type="integer",
                description="Maximum concurrent video generation jobs",
            ),
            SystemSetting(
                key="queue_timeout_minutes",
                value="30",
                value_type="integer",
                description="Job queue timeout in minutes",
            ),
        ]
        for s in settings_data:
            db.add(s)

        # Create prompt templates
        templates = [
            PromptTemplate(
                id="template_short_default",
                name="Short Form Default",
                category="short",
                platform_target="youtube",
                format="short",
                script_template="Create a 60-second short-form video script about {topic}. Include: 1) Hook (0-5s), 2) Main content (5-50s), 3) Call to action (50-60s). Tone: {tone}. Language: {language}.",
                title_template="How to {topic} - Quick Guide",
                description_template="Learn about {topic} in this quick 60-second video. #shorts #tutorial",
                hashtag_template="#shorts #tutorial #ai #content",
                is_default=True,
            ),
            PromptTemplate(
                id="template_long_default",
                name="Long Form Default",
                category="long",
                platform_target="youtube",
                format="long",
                script_template="Create a 5-minute long-form video script about {topic}. Include: 1) Intro (0-30s), 2) Main sections (30s-4m), 3) Conclusion (4m-5m). Tone: {tone}. Language: {language}.",
                title_template="Complete Guide to {topic}",
                description_template="Everything you need to know about {topic}. Full tutorial with examples.",
                hashtag_template="#tutorial #guide #ai #education",
                is_default=True,
            ),
        ]
        for t in templates:
            db.add(t)

        await db.commit()
        print("✓ Database seeded successfully")
        print(f"  Admin: {settings.admin_email} / {settings.admin_password}")
        print(f"  Test: test@example.com / testpassword123")


if __name__ == "__main__":
    asyncio.run(create_tables())
    asyncio.run(seed())