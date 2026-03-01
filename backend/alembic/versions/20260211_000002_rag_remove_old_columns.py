"""RAG pipeline simplification - remove old columns.

Revision ID: 20260211_000002
Revises: 20260211_000001
Create Date: 2026-02-11 00:00:02.000000

Drop legacy RAG configuration columns from knowledge_bases that are no longer
needed now that we use fixed best-in-class components (BGE-M3, BGE-reranker,
3-way hybrid retrieval, Qdrant, Redis).
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_000002"
down_revision = "20260211_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old embedding columns
    op.drop_column("knowledge_bases", "embedding_model")
    op.drop_column("knowledge_bases", "embedding_dimensions")

    # Drop old retrieval columns
    op.drop_column("knowledge_bases", "retrieval_strategy")
    op.drop_column("knowledge_bases", "score_threshold")
    op.drop_column("knowledge_bases", "hybrid_alpha")

    # Drop old reranker columns
    op.drop_column("knowledge_bases", "reranker_type")
    op.drop_column("knowledge_bases", "rerank_top_k")

    # Drop old chunking detail columns (keep chunking_strategy, chunk_size, chunk_overlap)
    op.drop_column("knowledge_bases", "min_chunk_size")
    op.drop_column("knowledge_bases", "semantic_threshold")
    op.drop_column("knowledge_bases", "breakpoint_percentile")
    op.drop_column("knowledge_bases", "hierarchical_levels")

    # Drop old cache columns
    op.drop_column("knowledge_bases", "enable_cache")
    op.drop_column("knowledge_bases", "cache_similarity_threshold")
    op.drop_column("knowledge_bases", "cache_ttl_seconds")

    # Drop RAG mode column (always pipeline now)
    op.drop_column("knowledge_bases", "rag_mode")


def downgrade() -> None:
    # Re-add RAG mode
    op.add_column(
        "knowledge_bases",
        sa.Column("rag_mode", sa.String(20), nullable=False, server_default="native"),
    )

    # Re-add cache columns
    op.add_column(
        "knowledge_bases",
        sa.Column("cache_ttl_seconds", sa.Integer(), nullable=False, server_default="3600"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("cache_similarity_threshold", sa.Float(), nullable=False, server_default="0.9"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("enable_cache", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    # Re-add chunking detail columns
    op.add_column(
        "knowledge_bases",
        sa.Column("hierarchical_levels", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("breakpoint_percentile", sa.Integer(), nullable=False, server_default="95"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("semantic_threshold", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("min_chunk_size", sa.Integer(), nullable=False, server_default="100"),
    )

    # Re-add reranker columns
    op.add_column(
        "knowledge_bases",
        sa.Column("rerank_top_k", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("reranker_type", sa.String(50), nullable=False, server_default="cross_encoder"),
    )

    # Re-add retrieval columns
    op.add_column(
        "knowledge_bases",
        sa.Column("hybrid_alpha", sa.Float(), nullable=False, server_default="0.5"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("score_threshold", sa.Float(), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("retrieval_strategy", sa.String(50), nullable=False, server_default="hybrid_rerank"),
    )

    # Re-add embedding columns
    op.add_column(
        "knowledge_bases",
        sa.Column("embedding_dimensions", sa.Integer(), nullable=False, server_default="1536"),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("embedding_model", sa.String(100), nullable=False, server_default="text-embedding-3-small"),
    )
