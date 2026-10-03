"""Initial migration - create all tables for HydraClip MVP.

Revision ID: 20260930_initial
Revises:
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic requires these module-level identifiers to build the migration
# chain. Without them `alembic upgrade head` aborts before running anything,
# which is what happened to every `make migrate` until now.
revision = "20260930_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types once, then tell the table-bound enum objects not to
    # emit CREATE TYPE again.  PostgreSQL's normal table-create event does not
    # use checkfirst, so pre-creating a plain sa.Enum and then using another
    # plain sa.Enum in a column fails with DuplicateObject.
    user_role = postgresql.ENUM("USER", "ADMIN", name="user_role", create_type=False)
    subscription_status = postgresql.ENUM(
        "active", "cancelled", "past_due", name="subscription_status", create_type=False
    )
    schedule_status = postgresql.ENUM(
        "pending",
        "running",
        "completed",
        "cancelled",
        "failed",
        name="schedule_status",
        create_type=False,
    )
    published_post_status = postgresql.ENUM(
        "pending", "published", "failed", name="published_post_status", create_type=False
    )
    video_job_status = postgresql.ENUM(
        "pending", "running", "completed", "failed", name="video_job_status", create_type=False
    )

    bind = op.get_bind()
    for enum_type in (
        user_role,
        subscription_status,
        schedule_status,
        published_post_status,
        video_job_status,
    ):
        enum_type.create(bind, checkfirst=True)

    # Create tables
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String()),
        sa.Column("role", sa.String(), nullable=False, server_default="USER"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("stripe_customer_id", sa.String(), unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("stripe_price_id", sa.String(), nullable=False),
        sa.Column("video_limit_monthly", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("storage_limit_gb", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("features_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plans_name"), "plans", ["name"], unique=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stripe_subscription_id", sa.String(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("status", subscription_status, nullable=False, server_default="active"),
        sa.Column("current_period_start", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("current_period_end", sa.DateTime(), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_subscriptions_stripe_subscription_id"), "subscriptions", ["stripe_subscription_id"], unique=True)

    op.create_table(
        "usage_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("topic", sa.String()),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("settings_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("storage_key", sa.String()),
        sa.Column("script_text", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("resolution", sa.String()),
        sa.Column("format", sa.String()),
        sa.Column("generation_params_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "video_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("status", video_job_status, nullable=False, server_default="pending"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("celery_task_id", sa.String()),
        sa.Column("error_message", sa.Text()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "schedules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("status", schedule_status, nullable=False, server_default="pending"),
        sa.Column("platform_post_id", sa.String()),
        sa.Column("platform_url", sa.String()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "published_posts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("video_id", sa.Integer(), nullable=False),
        sa.Column("schedule_id", sa.Integer()),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("platform_post_id", sa.String()),
        sa.Column("platform_url", sa.String()),
        sa.Column("title", sa.String()),
        sa.Column("description", sa.Text()),
        sa.Column("tags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", published_post_status, nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime()),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "social_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("account_name", sa.String(), nullable=False),
        sa.Column("account_id", sa.String()),
        sa.Column("access_token_encrypted", sa.String(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("connected_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "platform_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("social_account_id", sa.Integer(), nullable=False),
        sa.Column("access_token_encrypted", sa.String(), nullable=False),
        sa.Column("refresh_token_encrypted", sa.String()),
        sa.Column("token_type", sa.String(), nullable=False, server_default="Bearer"),
        sa.Column("scope", sa.String()),
        sa.Column("expires_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["social_account_id"], ["social_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("target_id", sa.Integer()),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String()),
        sa.Column("user_agent", sa.String()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["admin_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(), nullable=False, unique=True),
        sa.Column("value", sa.String()),
        sa.Column("value_type", sa.String(), nullable=False, server_default="string"),
        sa.Column("description", sa.String()),
        sa.Column("updated_by", sa.Integer()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "billing_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stripe_event_id", sa.String(), unique=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer()),
        sa.Column("currency", sa.String(), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create default plans
    op.bulk_insert(
        sa.table(
            "plans",
            sa.column("name", sa.String()),
            sa.column("stripe_price_id", sa.String()),
            sa.column("video_limit_monthly", sa.Integer()),
            sa.column("storage_limit_gb", sa.Integer()),
            sa.column("is_active", sa.Boolean()),
            # Supplying the JSON type makes SQLAlchemy serialize each dict
            # before psycopg2 sees it.  An untyped sa.column has NullType and
            # sends the raw dict, which psycopg2 cannot adapt.
            sa.column("features_json", sa.JSON()),
        ),
        [
            {
                "name": "Free",
                "stripe_price_id": "price_free",
                "video_limit_monthly": 3,
                "storage_limit_gb": 1,
                "is_active": True,
                "features_json": {"watermark": True, "auto_publish": False},
            },
            {
                "name": "Creator",
                "stripe_price_id": "price_creator",
                "video_limit_monthly": 25,
                "storage_limit_gb": 10,
                "is_active": True,
                "features_json": {"watermark": False, "auto_publish": True, "youtube_publish": True},
            },
            {
                "name": "Pro",
                "stripe_price_id": "price_pro",
                "video_limit_monthly": 0,
                "storage_limit_gb": 50,
                "is_active": True,
                "features_json": {"watermark": False, "auto_publish": True, "youtube_publish": True, "priority_queue": True},
            },
        ],
    )

    # Create default system settings
    op.bulk_insert(
        sa.table(
            "system_settings",
            sa.column("key", sa.String()),
            sa.column("value", sa.String()),
            sa.column("value_type", sa.String()),
            sa.column("description", sa.String()),
        ),
        [
            {"key": "site_name", "value": "HydraClip", "value_type": "string", "description": "Site name"},
            {"key": "site_description", "value": "AI-powered video content scheduling platform", "value_type": "string", "description": "Site description"},
            {"key": "maintenance_mode", "value": "false", "value_type": "boolean", "description": "Maintenance mode toggle"},
            {"key": "default_aspect_ratio", "value": "9:16", "value_type": "string", "description": "Default aspect ratio"},
            {"key": "default_video_duration", "value": "60", "value_type": "integer", "description": "Default video duration in seconds"},
        ],
    )

    # Create default prompt templates
    op.bulk_insert(
        sa.table(
            "prompt_templates",
            sa.column("name", sa.String()),
            sa.column("category", sa.String()),
            sa.column("script", sa.Text()),
            sa.column("is_default", sa.Boolean()),
        ),
        [
            {
                "name": "short_form_script",
                "category": "Short Form",
                "script": "Generate a captivating short-form video script about {topic}. Include an engaging hook, 3 key points, and a call-to-action. Keep it under 60 seconds when spoken.",
                "is_default": True,
            },
            {
                "name": "long_form_intro",
                "category": "Long Form",
                "script": "Generate an introductory section for a long-form video about {topic}. Set up the problem, present the solution, and outline what viewers will learn. Keep it under 3 minutes when spoken.",
                "is_default": False,
            },
        ],
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table("billing_events")
    op.drop_table("prompt_templates")
    op.drop_table("system_settings")
    op.drop_table("admin_audit_logs")
    op.drop_table("platform_tokens")
    op.drop_table("social_accounts")
    op.drop_table("published_posts")
    op.drop_table("schedules")
    op.drop_table("video_jobs")
    op.drop_table("videos")
    op.drop_table("projects")
    op.drop_table("usage_events")
    op.drop_table("subscriptions")
    op.drop_table("plans")
    op.drop_table("users")

    # Drop enum types
    for enum_name in ["user_role", "subscription_status", "schedule_status", "published_post_status", "video_job_status"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name} CASCADE")