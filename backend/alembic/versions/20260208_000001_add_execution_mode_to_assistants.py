"""Add execution_mode to assistants

Revision ID: 20260208_000001
Revises: 20260203_000001
Create Date: 2026-02-08 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260208_000001"
down_revision: Union[str, None] = "20260203_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "assistants",
        sa.Column(
            "execution_mode",
            sa.String(50),
            nullable=False,
            server_default="self_hosted",
        ),
    )


def downgrade() -> None:
    op.drop_column("assistants", "execution_mode")
