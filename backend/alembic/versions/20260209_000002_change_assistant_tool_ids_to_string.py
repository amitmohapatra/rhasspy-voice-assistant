"""Change assistant tool_ids from UUID[] to String[]

Revision ID: 20260209_000002
Revises: 20260209_000001
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, UUID

revision = "20260209_000002"
down_revision = "20260209_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Change tool_ids column from UUID[] to String[]
    # Existing UUIDs will be cast to their string representation
    op.execute(
        "ALTER TABLE assistants "
        "ALTER COLUMN tool_ids TYPE VARCHAR[] "
        "USING tool_ids::text[]::varchar[]"
    )


def downgrade() -> None:
    # Change back to UUID[] (will fail if non-UUID strings are present)
    op.execute(
        "ALTER TABLE assistants "
        "ALTER COLUMN tool_ids TYPE UUID[] "
        "USING tool_ids::uuid[]"
    )
