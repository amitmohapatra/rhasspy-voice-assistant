"""Add builtin_tools tables

Revision ID: 20260209_000001
Revises: 20260208_000001
Create Date: 2026-02-09 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "20260209_000001"
down_revision: Union[str, None] = "20260208_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create builtin_tools table
    op.create_table(
        "builtin_tools",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("ai_providers.id"), nullable=False),
        sa.Column("capability_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), server_default="tools"),
        sa.Column("config_schema", JSONB, server_default="{}"),
        sa.Column("default_config", JSONB, server_default="{}"),
        sa.Column("api_config", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_preview", sa.Boolean, server_default="false"),
        sa.Column("is_beta", sa.Boolean, server_default="false"),
        sa.Column("is_deprecated", sa.Boolean, server_default="false"),
        sa.Column("is_always_on", sa.Boolean, server_default="false"),
        sa.Column("supported_model_patterns", JSONB, server_default="[]"),
        sa.Column("excluded_model_patterns", JSONB, server_default="[]"),
        sa.Column("docs_url", sa.String(500), nullable=True),
        sa.Column("examples", JSONB, server_default="{}"),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider_id", "name", name="uq_provider_builtin_tool"),
    )
    op.create_index("idx_builtin_tools_provider", "builtin_tools", ["provider_id"])
    op.create_index("idx_builtin_tools_capability", "builtin_tools", ["capability_type"])
    op.create_index("idx_builtin_tools_active", "builtin_tools", ["is_active"])

    # Create builtin_tool_model_overrides table
    op.create_table(
        "builtin_tool_model_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "builtin_tool_id",
            sa.String(36),
            sa.ForeignKey("builtin_tools.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("model_pattern", sa.String(200), nullable=False),
        sa.Column("is_enabled", sa.Boolean, server_default="true"),
        sa.Column("config_overrides", JSONB, server_default="{}"),
        sa.Column("api_config_overrides", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "builtin_tool_id", "model_pattern", name="uq_builtin_tool_model_override"
        ),
    )

    # Create tool_capability_requirements table (for custom tools)
    op.create_table(
        "tool_capability_requirements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tool_id", sa.String(36), nullable=False),
        sa.Column("capability_type", sa.String(50), nullable=False),
        sa.Column("is_required", sa.Boolean, server_default="true"),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "tool_id", "capability_type", name="uq_tool_capability_requirement"
        ),
    )
    op.create_index(
        "idx_tool_capability_req_tool", "tool_capability_requirements", ["tool_id"]
    )


def downgrade() -> None:
    op.drop_table("tool_capability_requirements")
    op.drop_table("builtin_tool_model_overrides")
    op.drop_table("builtin_tools")
