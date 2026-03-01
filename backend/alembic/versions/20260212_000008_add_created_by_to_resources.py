"""Add created_by column to assistants, knowledge_bases, tools.

Revision ID: 20260212_000008
Revises: 20260212_000007
Create Date: 2026-02-12 00:00:08.000000

Changes:
1. Add created_by UUID FK (nullable) to assistants, knowledge_bases, tools
2. Each user only sees resources they created
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260212_000008"
down_revision = "20260212_000007"
branch_labels = None
depends_on = None

_TABLES = ["assistants", "knowledge_bases", "tools"]


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "created_by",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_column(table, "created_by")
