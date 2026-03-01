"""RAG architecture overhaul - automated pipeline, no user config.

Revision ID: 20260212_000002
Revises: 20260212_000001
Create Date: 2026-02-12 00:00:02.000000

Changes:
1. Remove user-configurable RAG columns from knowledge_bases:
   - chunking_strategy, chunk_size, chunk_overlap, top_k, top_n
   - describe_images, interpret_charts, language_hint
   - rag_pipeline_id (FK to rag_pipelines)
2. Add parent-child retrieval columns to document_chunks:
   - parent_chunk_id (self-referencing FK)
   - is_parent (bool)
3. Drop RAG pipeline tables:
   - rag_pipelines, rag_pipeline_versions, knowledge_base_pipelines
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260212_000002"
down_revision = "20260212_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === 1. Add parent-child columns to document_chunks ===
    op.add_column(
        "document_chunks",
        sa.Column(
            "parent_chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("document_chunks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "document_chunks",
        sa.Column("is_parent", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_document_chunks_parent_chunk_id",
        "document_chunks",
        ["parent_chunk_id"],
    )

    # === 2. Remove user-configurable RAG columns from knowledge_bases ===
    # Drop FK constraint to rag_pipelines first
    op.drop_constraint(
        "knowledge_bases_rag_pipeline_id_fkey",
        "knowledge_bases",
        type_="foreignkey",
    )
    op.drop_index("ix_knowledge_bases_rag_pipeline_id", table_name="knowledge_bases")

    columns_to_drop = [
        "chunking_strategy",
        "chunk_size",
        "chunk_overlap",
        "top_k",
        "top_n",
        "describe_images",
        "interpret_charts",
        "language_hint",
        "rag_pipeline_id",
    ]
    for col in columns_to_drop:
        op.drop_column("knowledge_bases", col)

    # === 3. Drop RAG pipeline tables ===
    # Drop knowledge_base_pipelines first (has FKs to rag_pipelines)
    op.drop_table("knowledge_base_pipelines")
    # Drop rag_pipeline_versions (has FK to rag_pipelines)
    op.drop_table("rag_pipeline_versions")
    # Drop rag_pipelines
    op.drop_table("rag_pipelines")


def downgrade() -> None:
    # === 3. Recreate RAG pipeline tables ===
    op.create_table(
        "rag_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("is_shared", sa.Boolean(), server_default="false"),
        sa.Column("is_default", sa.Boolean(), server_default="false"),
        sa.Column("is_template", sa.Boolean(), server_default="false"),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("template_name", sa.String(100), nullable=True),
        sa.Column("template_category", sa.String(50), nullable=True),
        sa.Column("usage_count", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "rag_pipeline_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rag_pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=True),
        sa.Column("config_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("changed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "knowledge_base_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rag_pipelines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("config_overrides", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # === 2. Re-add user-configurable RAG columns to knowledge_bases ===
    op.add_column("knowledge_bases", sa.Column("rag_pipeline_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "knowledge_bases_rag_pipeline_id_fkey",
        "knowledge_bases",
        "rag_pipelines",
        ["rag_pipeline_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_knowledge_bases_rag_pipeline_id", "knowledge_bases", ["rag_pipeline_id"])

    op.add_column("knowledge_bases", sa.Column("chunking_strategy", sa.String(50), server_default="recursive", nullable=False))
    op.add_column("knowledge_bases", sa.Column("chunk_size", sa.Integer(), server_default="512", nullable=False))
    op.add_column("knowledge_bases", sa.Column("chunk_overlap", sa.Integer(), server_default="50", nullable=False))
    op.add_column("knowledge_bases", sa.Column("top_k", sa.Integer(), server_default="10", nullable=False))
    op.add_column("knowledge_bases", sa.Column("top_n", sa.Integer(), server_default="5", nullable=False))
    op.add_column("knowledge_bases", sa.Column("describe_images", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("knowledge_bases", sa.Column("interpret_charts", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("knowledge_bases", sa.Column("language_hint", sa.String(10), nullable=True))

    # === 1. Remove parent-child columns from document_chunks ===
    op.drop_index("ix_document_chunks_parent_chunk_id", table_name="document_chunks")
    op.drop_column("document_chunks", "is_parent")
    op.drop_column("document_chunks", "parent_chunk_id")
