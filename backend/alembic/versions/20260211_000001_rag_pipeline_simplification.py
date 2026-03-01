"""RAG pipeline simplification - add new columns.

Revision ID: 20260211_000001
Revises: 20260210_000001
Create Date: 2026-02-11 00:00:01.000000

Add columns for the simplified RAG pipeline:
- documents: structured_json_path, page_count, language
- document_chunks: page_number, element_type
- knowledge_bases: describe_images, interpret_charts, language_hint, top_n
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260211_000001"
down_revision = "20260210_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Documents: add structured content fields
    op.add_column(
        "documents",
        sa.Column("structured_json_path", sa.String(512), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("page_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("language", sa.String(10), nullable=True),
    )

    # Document chunks: add element-level fields
    op.add_column(
        "document_chunks",
        sa.Column("page_number", sa.Integer(), nullable=True),
    )
    op.add_column(
        "document_chunks",
        sa.Column(
            "element_type",
            sa.String(20),
            server_default="text",
            nullable=False,
        ),
    )

    # Knowledge bases: add simplified RAG fields
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "describe_images",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "interpret_charts",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column("language_hint", sa.String(10), nullable=True),
    )
    op.add_column(
        "knowledge_bases",
        sa.Column(
            "top_n",
            sa.Integer(),
            server_default="5",
            nullable=False,
        ),
    )


def downgrade() -> None:
    # Knowledge bases
    op.drop_column("knowledge_bases", "top_n")
    op.drop_column("knowledge_bases", "language_hint")
    op.drop_column("knowledge_bases", "interpret_charts")
    op.drop_column("knowledge_bases", "describe_images")

    # Document chunks
    op.drop_column("document_chunks", "element_type")
    op.drop_column("document_chunks", "page_number")

    # Documents
    op.drop_column("documents", "language")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "structured_json_path")
