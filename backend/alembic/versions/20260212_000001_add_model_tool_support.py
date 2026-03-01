"""Add model_tool_support join table.

Revision ID: 20260212_000001
Revises: 20260211_000004
Create Date: 2026-02-12 00:00:01.000000

Introduces an explicit FK-based join table between ai_models and
builtin_tools to replace fragile fnmatch glob pattern matching.
The old builtin_tool_model_overrides table is kept (deprecated) until
all data is migrated.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260212_000001"
down_revision = "20260211_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_tool_support",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("builtin_tool_id", sa.String(36), sa.ForeignKey("builtin_tools.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_supported", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_overrides", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("api_config_overrides", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(50), nullable=False, server_default=sa.text("'seed'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("model_id", "builtin_tool_id", name="uq_model_tool_support"),
    )

    op.create_index("ix_model_tool_support_model", "model_tool_support", ["model_id"])
    op.create_index("ix_model_tool_support_tool", "model_tool_support", ["builtin_tool_id"])
    op.create_index("ix_model_tool_support_model_supported", "model_tool_support", ["model_id", "is_supported"])


def downgrade() -> None:
    op.drop_index("ix_model_tool_support_model_supported", table_name="model_tool_support")
    op.drop_index("ix_model_tool_support_tool", table_name="model_tool_support")
    op.drop_index("ix_model_tool_support_model", table_name="model_tool_support")
    op.drop_table("model_tool_support")
