import os
import sys

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# add model's directory to sys.path so autogenerate can find models
sys.path.insert(0, os.path.realpath("apps/api"))

# Import Base from the central models package
from apps.api.models import Base  # noqa: F401

target_metadata = Base.metadata

# Prefer the application's configured DATABASE_URL over the static value in
# alembic.ini, which was hardcoded with mismatched credentials and used the
# legacy "postgres://" scheme that SQLAlchemy 2.x rejects.
from apps.api.core.config import settings  # noqa: E402

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

# The previous version of this file defined both functions but never called
# either of them, so `alembic upgrade head` completed without running a single
# migration.
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
