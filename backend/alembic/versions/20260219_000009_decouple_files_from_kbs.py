"""Decouple files from knowledge bases — many-to-many via join table.

Revision ID: 20260219_000009
Revises: 20260212_000008
Create Date: 2026-02-19 00:00:09.000000

Changes:
1. Create knowledge_base_documents join table (many-to-many)
2. Migrate existing documents.knowledge_base_id data into the join table
3. Drop knowledge_base_id column from documents
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20260219_000009"
down_revision = "20260212_000008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create knowledge_base_documents join table
    op.create_table(
        "knowledge_base_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("knowledge_base_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("knowledge_base_id", "document_id", name="uq_kb_document"),
    )
    op.create_index("ix_kbdoc_knowledge_base_id", "knowledge_base_documents", ["knowledge_base_id"])
    op.create_index("ix_kbdoc_document_id", "knowledge_base_documents", ["document_id"])

    # 2. Migrate existing FK data into the join table
    op.execute(
        """
        INSERT INTO knowledge_base_documents (id, knowledge_base_id, document_id, created_at)
        SELECT gen_random_uuid(), knowledge_base_id, id, created_at
        FROM documents
        WHERE knowledge_base_id IS NOT NULL
        """
    )

    # 3. Drop the old FK column from documents
    op.drop_constraint("documents_knowledge_base_id_fkey", "documents", type_="foreignkey")
    op.drop_index("ix_documents_knowledge_base_id", table_name="documents")
    op.drop_column("documents", "knowledge_base_id")


def downgrade() -> None:
    # Re-add the knowledge_base_id column
    op.add_column(
        "documents",
        sa.Column(
            "knowledge_base_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_index("ix_documents_knowledge_base_id", "documents", ["knowledge_base_id"])

    # Migrate data back from join table (take the first KB if multiple)
    op.execute(
        """
        UPDATE documents d
        SET knowledge_base_id = (
            SELECT kbd.knowledge_base_id
            FROM knowledge_base_documents kbd
            WHERE kbd.document_id = d.id
            ORDER BY kbd.created_at ASC
            LIMIT 1
        )
        """
    )

    # Re-add the FK constraint
    op.create_foreign_key(
        "documents_knowledge_base_id_fkey",
        "documents",
        "knowledge_bases",
        ["knowledge_base_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Make it NOT NULL again
    op.alter_column("documents", "knowledge_base_id", nullable=False)

    # Drop the join table
    op.drop_index("ix_kbdoc_document_id", table_name="knowledge_base_documents")
    op.drop_index("ix_kbdoc_knowledge_base_id", table_name="knowledge_base_documents")
    op.drop_table("knowledge_base_documents")
