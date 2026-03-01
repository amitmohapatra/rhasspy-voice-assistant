"""Drop dead tables and add uploaded_by to documents.

Revision ID: 20260212_000003
Revises: 20260212_000002
Create Date: 2026-02-12 00:00:03.000000

Changes:
1. Drop 19 dead tables with no active UI or routes:
   - Enterprise deployments: deployments, licenses, usage_reports,
     deployment_events, cloud_connections, support_access_grants,
     support_access_logs, deployment_telemetry, black_box_configs
   - Teams/sharing: teams, team_members, resource_shares
   - Tenant RBAC: usage_records
   - Infrastructure: vector_db_configs, infrastructure_configs
   - ML config: platform_ml_providers, organization_ml_configs,
     ml_processing_jobs, ml_usage_stats
2. Add uploaded_by FK (users.id) to documents table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260212_000003"
down_revision = "20260212_000002"
branch_labels = None
depends_on = None


# Tables to drop, ordered to respect foreign key dependencies
# (child tables first, parent tables last)
TABLES_TO_DROP = [
    # Enterprise deployments — children first
    "deployment_events",
    "usage_reports",
    "support_access_logs",
    "support_access_grants",
    "deployment_telemetry",
    "black_box_configs",
    "cloud_connections",
    "licenses",
    "deployments",
    # Teams & sharing
    "resource_shares",
    "team_members",
    "teams",
    # Tenant RBAC
    "usage_records",
    # Infrastructure config
    "vector_db_configs",
    "infrastructure_configs",
    # ML config
    "ml_usage_stats",
    "ml_processing_jobs",
    "organization_ml_configs",
    "platform_ml_providers",
]


def upgrade() -> None:
    # Drop dead tables (IF EXISTS for safety)
    for table_name in TABLES_TO_DROP:
        op.execute(sa.text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))

    # Add uploaded_by FK to documents
    op.add_column(
        "documents",
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_uploaded_by", "documents", ["uploaded_by"])


def downgrade() -> None:
    # Remove uploaded_by from documents
    op.drop_index("ix_documents_uploaded_by", table_name="documents")
    op.drop_column("documents", "uploaded_by")

    # Note: downgrade does NOT recreate the dropped tables.
    # They were dead code with no active usage.
