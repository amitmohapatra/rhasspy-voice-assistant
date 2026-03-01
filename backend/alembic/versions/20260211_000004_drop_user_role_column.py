"""Drop role column from users table.

Revision ID: 20260211_000004
Revises: 20260211_000003
Create Date: 2026-02-11 00:00:04.000000

Remove the role column from the users table. All authenticated users now have
equal access — there are no role distinctions (admin, super_admin, etc.).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_000004"
down_revision = "20260211_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "role")


def downgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
    )
