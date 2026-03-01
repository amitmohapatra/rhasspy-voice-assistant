"""Add user_llm_keys table for encrypted vendor API keys.

Revision ID: 20260221_000010
Revises: 20260219_000009
Create Date: 2026-02-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "20260221_000010"
down_revision = "20260219_000009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_llm_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("encrypted_key", sa.Text, nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_llm_key_provider"),
    )


def downgrade() -> None:
    op.drop_table("user_llm_keys")
