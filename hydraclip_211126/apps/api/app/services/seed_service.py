"""Seed reference data (plans, settings, templates) required by the API."""

import logging

from sqlalchemy import select

from app.config import get_settings
from app.core.database import AsyncSessionLocal
from app.models.system import PromptTemplate, SystemSetting
from app.models.user import Plan

logger = logging.getLogger(__name__)
settings = get_settings()

DEFAULT_PLANS = [
    {
        "id": "plan_free",
        "name": "Free",
        "stripe_price_id": None,
        "video_limit_monthly": 3,
        "storage_limit_gb": 1,
        "features_json": '["3 videos/month", "1GB storage", "Watermark", "Download only"]',
        "price_cents": 0,
        "is_active": True,
    },
    {
        "id": "plan_creator",
        "name": "Creator",
        "stripe_price_id": settings.stripe_creator_price_id,
        "video_limit_monthly": 25,
        "storage_limit_gb": 10,
        "features_json": '["25 videos/month", "10GB storage", "No watermark", "YouTube auto-publish", "HD resolution"]',
        "price_cents": 1900,
        "is_active": True,
    },
    {
        "id": "plan_pro",
        "name": "Pro",
        "stripe_price_id": settings.stripe_pro_price_id,
        "video_limit_monthly": -1,
        "storage_limit_gb": 50,
        "features_json": '["Unlimited videos", "50GB storage", "No watermark", "Priority queue", "All platforms", "HD resolution"]',
        "price_cents": 4900,
        "is_active": True,
    },
]

DEFAULT_SETTINGS = [
    ("maintenance_mode", "false", "boolean", "Global maintenance mode toggle"),
    ("default_video_format", "short", "string", "Default video format for new projects"),
    ("default_aspect_ratio", "9:16", "string", "Default aspect ratio for new videos"),
    ("default_language", "en", "string", "Default language for generation"),
    ("default_voice", "en-US-AriaNeural", "string", "Default TTS voice"),
    ("default_tts_engine", "edge", "string", "Default TTS engine (edge/piper)"),
    ("max_concurrent_jobs", "3", "integer", "Maximum concurrent video generation jobs"),
    ("queue_timeout_minutes", "30", "integer", "Job queue timeout in minutes"),
]

DEFAULT_TEMPLATES = [
    {
        "id": "template_short_default",
        "name": "Short Form Default",
        "category": "short",
        "platform_target": "youtube",
        "format": "short",
        "script_template": "Create a 60-second short-form video script about {topic}. Include: 1) Hook (0-5s), 2) Main content (5-50s), 3) Call to action (50-60s). Tone: {tone}. Language: {language}.",
        "title_template": "How to {topic} - Quick Guide",
        "description_template": "Learn about {topic} in this quick 60-second video. #shorts #tutorial",
        "hashtag_template": "#shorts #tutorial #ai #content",
        "is_default": True,
    },
    {
        "id": "template_long_default",
        "name": "Long Form Default",
        "category": "long",
        "platform_target": "youtube",
        "format": "long",
        "script_template": "Create a 5-minute long-form video script about {topic}. Include: 1) Intro (0-30s), 2) Main sections (30s-4m), 3) Conclusion (4m-5m). Tone: {tone}. Language: {language}.",
        "title_template": "Complete Guide to {topic}",
        "description_template": "Everything you need to know about {topic}. Full tutorial with examples.",
        "hashtag_template": "#tutorial #guide #ai #education",
        "is_default": True,
    },
]


async def seed_reference_data() -> None:
    """Insert any missing default plans, settings and templates."""
    async with AsyncSessionLocal() as db:
        existing_plans = set((await db.execute(select(Plan.id))).scalars().all())
        for plan in DEFAULT_PLANS:
            if plan["id"] not in existing_plans:
                db.add(Plan(**plan))

        existing_settings = set(
            (await db.execute(select(SystemSetting.key))).scalars().all()
        )
        for key, value, value_type, description in DEFAULT_SETTINGS:
            if key not in existing_settings:
                db.add(
                    SystemSetting(
                        id=key,
                        key=key,
                        value=value,
                        value_type=value_type,
                        description=description,
                    )
                )

        existing_templates = set(
            (await db.execute(select(PromptTemplate.id))).scalars().all()
        )
        for template in DEFAULT_TEMPLATES:
            if template["id"] not in existing_templates:
                db.add(PromptTemplate(**template))

        await db.commit()
