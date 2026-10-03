"""Credential columns for connected publishing accounts.

Adds the fields the OAuth flow needs on ``social_accounts`` and stops the
same account being connected twice.

Revision ID: 20261002_oauth_tokens
Revises: 20260930_initial
"""

from alembic import op
import sqlalchemy as sa

revision = "20261002_oauth_tokens"
down_revision = "20260930_initial"
branch_labels = None
depends_on = None


def upgrade():
    # batch_alter_table so this also works on SQLite, which cannot ALTER a
    # table to add a constraint.
    with op.batch_alter_table("social_accounts") as batch:
        batch.add_column(
            sa.Column("token_type", sa.String(), nullable=True, server_default="Bearer")
        )
        batch.add_column(sa.Column("scope", sa.String(), nullable=True))
        batch.add_column(sa.Column("last_error", sa.Text(), nullable=True))
        batch.create_unique_constraint(
            "uq_social_account_identity", ["user_id", "platform", "account_id"]
        )


def downgrade():
    with op.batch_alter_table("social_accounts") as batch:
        batch.drop_constraint("uq_social_account_identity", type_="unique")
        batch.drop_column("last_error")
        batch.drop_column("scope")
        batch.drop_column("token_type")
