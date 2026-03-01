"""Remove pgvector, use Qdrant as sole vector store.

Revision ID: 20260210_000001
Revises: 20260209_000002
Create Date: 2026-02-10 00:00:01.000000

Drop the pgvector embedding column from document_chunks and the
vector_store_type/vector_store_config columns from knowledge_bases.
All vector storage now goes through Qdrant.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260210_000001"
down_revision = "20260209_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the vector embedding column and its index from document_chunks
    op.drop_index("ix_document_chunks_embedding", table_name="document_chunks", if_exists=True)
    op.drop_column("document_chunks", "embedding")

    # 2. Remove vector_store columns from knowledge_bases (always Qdrant now)
    op.drop_column("knowledge_bases", "vector_store_type")
    op.drop_column("knowledge_bases", "vector_store_config")

    # 3. Drop pgvector extension (no longer needed)
    op.execute("DROP EXTENSION IF EXISTS vector")


def downgrade() -> None:
    # Re-enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Re-add vector_store columns to knowledge_bases
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "vector_store_type",
            sa.String(50),
            nullable=False,
            server_default="pgvector",
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "vector_store_config",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
    )

    # Re-add embedding column (without data - data would need to be re-embedded)
    op.execute(
        "ALTER TABLE document_chunks ADD COLUMN embedding vector(1536)"
    )
