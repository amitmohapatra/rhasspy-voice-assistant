"""Add kb_type to knowledge_bases, create integration_catalog and user_integrations.

Revision ID: 20260211_000003
Revises: 20260211_000002
Create Date: 2026-02-11 00:00:03.000000

Add kb_type column (platform_managed vs provider-backed) to knowledge_bases with
optional foreign key to ai_providers for provider-backed KBs.

Create integration_catalog table for registering third-party service integrations
and user_integrations table for per-organization credential/config storage.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260211_000003"
down_revision = "20260211_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- knowledge_bases: add kb_type and provider columns ---
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "kb_type",
            sa.String(50),
            nullable=False,
            server_default="platform_managed",
        ),
    )
    op.create_index("ix_knowledge_bases_kb_type", "knowledge_bases", ["kb_type"])

    op.add_column(
        "knowledge_bases",
        sa.Column(
            "provider_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_knowledge_bases_provider_id",
        "knowledge_bases",
        "ai_providers",
        ["provider_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "knowledge_bases",
        sa.Column("provider_kb_ref", sa.String(255), nullable=True),
    )

    op.add_column(
        "knowledge_bases",
        sa.Column("provider_config", postgresql.JSONB, nullable=True),
    )

    # --- integration_catalog table ---
    op.create_table(
        "integration_catalog",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column(
            "category",
            sa.String(50),
            nullable=False,
            server_default="custom",
        ),
        sa.Column("auth_type", sa.String(50), nullable=False),
        sa.Column("auth_schema", postgresql.JSONB, nullable=False),
        sa.Column("test_endpoint", sa.String(512), nullable=True),
        sa.Column(
            "test_method",
            sa.String(10),
            nullable=False,
            server_default="GET",
        ),
        sa.Column(
            "test_headers",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "tool_schemas",
            postgresql.JSONB,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("setup_instructions", sa.Text, nullable=True),
        sa.Column("docs_url", sa.String(512), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_featured",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # --- user_integrations table ---
    op.create_table(
        "user_integrations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "integration_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("integration_catalog.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credentials",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "config",
            postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "is_verified",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("last_tested_at", sa.String(50), nullable=True),
        sa.Column("test_error", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "organization_id",
            "integration_id",
            name="uq_user_integrations_org_integration",
        ),
    )
    op.create_index(
        "ix_user_integrations_organization_id",
        "user_integrations",
        ["organization_id"],
    )
    op.create_index(
        "ix_user_integrations_integration_id",
        "user_integrations",
        ["integration_id"],
    )


def downgrade() -> None:
    # Drop user_integrations table (indexes and constraints dropped automatically)
    op.drop_table("user_integrations")

    # Drop integration_catalog table
    op.drop_table("integration_catalog")

    # Remove knowledge_bases columns (drop FK first)
    op.drop_constraint(
        "fk_knowledge_bases_provider_id",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_column("knowledge_bases", "provider_config")
    op.drop_column("knowledge_bases", "provider_kb_ref")
    op.drop_column("knowledge_bases", "provider_id")
    op.drop_index("ix_knowledge_bases_kb_type", table_name="knowledge_bases")
    op.drop_column("knowledge_bases", "kb_type")
