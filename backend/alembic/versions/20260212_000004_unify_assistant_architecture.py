"""Unify assistant architecture - drop provider-managed system.

Revision ID: 20260212_000004
Revises: 20260212_000003
Create Date: 2026-02-12 00:00:04.000000

Changes:
1. Drop 8 provider-managed assistant tables (FK dependency order):
   - vector_store_files
   - assistant_vector_stores
   - assistant_files
   - assistant_runs
   - assistant_messages
   - assistant_threads
   - provider_assistants
   - assistant_provider_configs
2. Drop assistants.execution_mode column

All assistants now use the unified platform-managed flow via LLMGateway.
The assistant.provider + assistant.model fields route to the correct LLM provider.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260212_000004"
down_revision = "20260212_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop tables in FK dependency order (children first)
    op.drop_table("vector_store_files")
    op.drop_table("assistant_vector_stores")
    op.drop_table("assistant_files")
    op.drop_table("assistant_runs")
    op.drop_table("assistant_messages")
    op.drop_table("assistant_threads")
    op.drop_table("provider_assistants")
    op.drop_table("assistant_provider_configs")

    # Drop execution_mode column from assistants
    op.drop_column("assistants", "execution_mode")


def downgrade() -> None:
    # Re-add execution_mode column
    op.add_column(
        "assistants",
        sa.Column(
            "execution_mode",
            sa.String(50),
            nullable=False,
            server_default="self_hosted",
        ),
    )

    # Re-create assistant_provider_configs
    op.create_table(
        "assistant_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_type", sa.String(50), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), default=False, nullable=False),
        sa.Column("is_enabled", sa.Boolean(), default=True, nullable=False),
        sa.Column("config", postgresql.JSONB(), default={}, nullable=False),
        sa.Column(
            "api_key_secret_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("secrets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_health_check", sa.DateTime(), nullable=True),
        sa.Column("is_healthy", sa.Boolean(), default=True, nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("total_requests", sa.BigInteger(), default=0, nullable=False),
        sa.Column("total_tokens", sa.BigInteger(), default=0, nullable=False),
        sa.Column("total_cost", sa.Float(), default=0.0, nullable=False),
        sa.Column("settings", postgresql.JSONB(), default={}, nullable=False),
    )

    # Re-create provider_assistants
    op.create_table(
        "provider_assistants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "provider_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_provider_configs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_assistant_id", sa.String(255), nullable=False, index=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("tools_enabled", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("vector_store_ids", postgresql.JSONB(), default=[], nullable=False),
        sa.Column(
            "code_interpreter_file_ids",
            postgresql.JSONB(),
            default=[],
            nullable=False,
        ),
        sa.Column("provider_metadata", postgresql.JSONB(), default={}, nullable=False),
        sa.Column("status", sa.String(50), default="active", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("sync_error", sa.Text(), nullable=True),
    )

    # Re-create assistant_threads
    op.create_table(
        "assistant_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "provider_assistant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("provider_assistants.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_thread_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("session_id", sa.String(255), nullable=True, index=True),
        sa.Column("meta_data", postgresql.JSONB(), default={}, nullable=False),
        sa.Column("status", sa.String(50), default="active", nullable=False),
        sa.Column("message_count", sa.Integer(), default=0, nullable=False),
        sa.Column("last_message_at", sa.DateTime(), nullable=True),
    )

    # Re-create assistant_messages
    op.create_table(
        "assistant_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_threads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_message_id", sa.String(255), nullable=True, index=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attachments", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("citations", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("code_outputs", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("tool_calls", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("meta_data", postgresql.JSONB(), default={}, nullable=False),
        sa.Column("provider_created_at", sa.DateTime(), nullable=True),
    )

    # Re-create assistant_runs
    op.create_table(
        "assistant_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_threads.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_run_id", sa.String(255), nullable=False, index=True),
        sa.Column("status", sa.String(50), nullable=False, index=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("additional_instructions", sa.Text(), nullable=True),
        sa.Column("tools", postgresql.JSONB(), default=[], nullable=False),
        sa.Column("required_action", postgresql.JSONB(), nullable=True),
        sa.Column("last_error", postgresql.JSONB(), nullable=True),
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(), default={}, nullable=False),
    )

    # Re-create assistant_files
    op.create_table(
        "assistant_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "provider_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_provider_configs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_file_id", sa.String(255), nullable=False, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("purpose", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), default="uploaded", nullable=False),
        sa.Column("status_details", sa.Text(), nullable=True),
        sa.Column("local_path", sa.String(512), nullable=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("meta_data", postgresql.JSONB(), default={}, nullable=False),
        sa.Column("provider_created_at", sa.DateTime(), nullable=True),
    )

    # Re-create assistant_vector_stores
    op.create_table(
        "assistant_vector_stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "provider_config_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_provider_configs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "provider_vector_store_id",
            sa.String(255),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), default="in_progress", nullable=False),
        sa.Column("file_count", sa.Integer(), default=0, nullable=False),
        sa.Column("bytes_used", sa.BigInteger(), default=0, nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("expires_after_days", sa.Integer(), nullable=True),
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("knowledge_bases.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("chunking_strategy", sa.String(50), nullable=True),
        sa.Column("chunk_size", sa.Integer(), default=512, nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), default=50, nullable=False),
        sa.Column("meta_data", postgresql.JSONB(), default={}, nullable=False),
        sa.Column("provider_created_at", sa.DateTime(), nullable=True),
    )

    # Re-create vector_store_files
    op.create_table(
        "vector_store_files",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column(
            "vector_store_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_vector_stores.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "file_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assistant_files.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("provider_association_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), default="in_progress", nullable=False),
        sa.Column("last_error", postgresql.JSONB(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=True),
    )
