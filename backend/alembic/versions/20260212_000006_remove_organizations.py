"""Remove organization layer — single-tenant system.

Revision ID: 20260212_000006
Revises: 20260212_000005
Create Date: 2026-02-12 00:00:06.000000

Changes:
1. Drop organization_capability_configs table
2. Drop organization_id FK + column from 14 child tables
3. Drop organizations table
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260212_000006"
down_revision = "20260212_000005"
branch_labels = None
depends_on = None

# Tables that have organization_id FK → organizations.id
_CHILD_TABLES = [
    "users",
    "assistants",
    "knowledge_bases",
    "tools",
    "projects",
    "conversations",
    "responses",
    "usage_logs",
    "avatars",
    "api_keys",
    "user_integrations",
    "model_usage_stats",
]


def upgrade() -> None:
    # 1. Drop organization_capability_configs (has FK to organizations)
    op.drop_table("organization_capability_configs")

    # 2. Drop organization_id FK + column from each child table
    for table in _CHILD_TABLES:
        # Drop the FK constraint first
        # Convention: fk name = {table}_organization_id_fkey
        op.drop_constraint(
            f"{table}_organization_id_fkey", table, type_="foreignkey"
        )
        # Drop index if exists (some tables have ix_{table}_organization_id)
        try:
            op.drop_index(f"ix_{table}_organization_id", table_name=table)
        except Exception:
            pass
        # Drop the column
        op.drop_column(table, "organization_id")

    # Also handle the unique constraint on user_integrations that includes organization_id
    op.drop_constraint("uq_org_integration", "user_integrations", type_="unique")

    # 3. Drop index on model_usage_stats
    try:
        op.drop_index("ix_model_usage_org", table_name="model_usage_stats")
    except Exception:
        pass

    # 4. Drop organizations table
    op.drop_table("organizations")


def downgrade() -> None:
    # 1. Recreate organizations table
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="free"),
        sa.Column("subscription_status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # 2. Re-add organization_id to child tables
    for table in _CHILD_TABLES:
        nullable = table == "users"  # users had nullable=True
        op.add_column(
            table,
            sa.Column(
                "organization_id",
                postgresql.UUID(as_uuid=True),
                nullable=True,  # nullable initially to allow backfill
            ),
        )
        op.create_foreign_key(
            f"{table}_organization_id_fkey",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE" if table != "users" else "SET NULL",
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])

    # 3. Recreate unique constraint on user_integrations
    op.create_unique_constraint(
        "uq_org_integration", "user_integrations", ["organization_id", "integration_id"]
    )

    # 4. Recreate organization_capability_configs
    op.create_table(
        "organization_capability_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("capability_type", sa.String(50), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True, nullable=False),
        sa.Column("config_overrides", postgresql.JSONB(), default={}),
        sa.Column("daily_limit", sa.Integer(), nullable=True),
        sa.Column("monthly_limit", sa.Integer(), nullable=True),
        sa.Column("current_daily_usage", sa.Integer(), default=0),
        sa.Column("current_monthly_usage", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "capability_type", name="uq_org_capability"),
    )
