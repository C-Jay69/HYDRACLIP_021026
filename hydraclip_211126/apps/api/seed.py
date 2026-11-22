"""Seed Script for HydraClip Database.

Run inside the API container: `make seed` (or `docker-compose exec api python seed.py`).
Because the API image only contains this directory, this is the copy that the
Makefile actually executes.

Idempotent: users are only created when missing, and reference data (plans,
settings, templates) is inserted by `seed_reference_data`.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import get_settings
from app.core.database import AsyncSessionLocal, Base, async_engine
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.services.seed_service import seed_reference_data

settings = get_settings()


async def create_tables() -> None:
    """Create all database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✓ Database tables created")


async def seed() -> None:
    """Seed users and reference data if they do not exist."""
    async with AsyncSessionLocal() as db:
        admin_email = settings.admin_email
        admin = (
            await db.execute(select(User).where(User.email == admin_email))
        ).scalar_one_or_none()
        if admin is None:
            db.add(
                User(
                    id="user_admin",
                    email=admin_email,
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
            )
            print(f"✓ Admin user created: {admin_email}")

        test_user = (
            await db.execute(select(User).where(User.email == "test@example.com"))
        ).scalar_one_or_none()
        if test_user is None:
            db.add(
                User(
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
            )
            print("✓ Test user created: test@example.com")

        await db.commit()

    await seed_reference_data()
    print("✓ Database seeded successfully")
    print(f"  Admin: {settings.admin_email} / {settings.admin_password}")
    print("  Test: test@example.com / testpassword123")


async def main() -> None:
    """Run table creation and seeding on a single event loop."""
    await create_tables()
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
