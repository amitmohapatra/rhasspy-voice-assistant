"""Create voice_presets table.

Revision ID: 20260212_000007
Revises: 20260212_000006
Create Date: 2026-02-12 00:00:07.000000

Changes:
1. Create voice_presets table for storing user TTS/STT presets
2. Add index on (user_id, type) for efficient lookups
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260212_000007"
down_revision = "20260212_000006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_presets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_voice_presets_user_type", "voice_presets", ["user_id", "type"])


def downgrade() -> None:
    op.drop_index("ix_voice_presets_user_type", table_name="voice_presets")
    op.drop_table("voice_presets")
