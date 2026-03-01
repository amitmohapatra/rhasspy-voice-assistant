"""Knowledge Base, Document, and DocumentChunk models.

Fixed RAG pipeline with best-in-class components:
- Docling HybridChunker (structure-aware, auto-adapts to document type)
- Late chunking with BGE-M3 (document-context-aware, zero LLM calls)
- Parent-child retrieval (search small, return big)
- BGE-M3 ONNX int8 (embedding: dense+sparse+ColBERT)
- 4-way hybrid retrieval (dense+sparse+BM25+visual with RRF)
- BGE-reranker-v2-m3 (reranking)
- Qdrant with named vectors (vector store)
- Redis (cache)

No user-configurable RAG fields. The platform handles everything.

Documents are decoupled from KBs via knowledge_base_documents join table.
A document can belong to multiple KBs. Processing happens once per document.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, Boolean, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.ai_model import AIProvider
    from src.models.user import User

# NOTE: User import is used by both KnowledgeBase.creator and Document.uploader


class KnowledgeBaseDocument(Base):
    """Many-to-many join table between knowledge bases and documents.

    A document can be assigned to multiple KBs. Processing runs once per
    document (when first assigned); subsequent assignments just create a
    join entry.
    """

    __tablename__ = "knowledge_base_documents"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "document_id", name="uq_kb_document"),
    )

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships (for eager loading when needed)
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase", lazy="selectin",
    )
    document: Mapped["Document"] = relationship(
        "Document", lazy="selectin",
    )


class KnowledgeBase(Base):
    """Knowledge Base with fully automated RAG pipeline.

    All RAG internals are fixed to best-in-class components.
    No user-configurable RAG parameters - the platform handles everything.
    """

    __tablename__ = "knowledge_bases"

    # Owner — each user sees only their own KBs
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # KB type: provider_managed (OpenAI/Azure file search) or platform_managed (our RAG)
    kb_type: Mapped[str] = mapped_column(
        String(50), default="platform_managed", nullable=False, index=True,
    )

    # Provider-managed fields (only used when kb_type=provider_managed)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_kb_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )  # External vector store ID from provider
    provider_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )  # Provider-specific config (assistant_id, vector_store_id, etc.)

    # Additional Settings (JSON for flexibility)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Status: active, processing, failed
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)

    # Relationships
    creator: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by], lazy="selectin",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        secondary="knowledge_base_documents",
        lazy="selectin",
        viewonly=True,
    )
    provider: Mapped["AIProvider | None"] = relationship(
        "AIProvider", foreign_keys=[provider_id], lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase(id={self.id}, name={self.name})>"

    @property
    def is_provider_managed(self) -> bool:
        return self.kb_type == "provider_managed"

    def to_rag_config(self) -> "RAGConfig":
        """Get the fixed RAGConfig for this knowledge base.

        Returns:
            RAGConfig with fixed best-in-class defaults.

        Raises:
            ValueError: If this is a provider-managed KB.
        """
        if self.kb_type == "provider_managed":
            raise ValueError("Provider-managed KBs don't use local RAG config")

        from src.rag.base import RAGConfig
        return RAGConfig()

    @classmethod
    def get_pipeline_info(cls) -> dict:
        """Get information about the fixed RAG pipeline."""
        return {
            "chunking": "Docling HybridChunker (structure-aware, auto-adapts)",
            "embedding": "Late chunking with BGE-M3 (document-context-aware, zero LLM calls)",
            "parent_child_retrieval": "Search small chunks, return parent sections",
            "retrieval": "3-way hybrid (dense+sparse+BM25 with RRF)",
            "reranker": "BGE-reranker-v2-m3",
            "vector_store": "Qdrant (named vectors)",
            "cache": "Redis",
            "document_enrichment": "Docling (PP-DocBee VLM + RapidOCR PP-OCRv5) + img2table",
        }


class Document(Base):
    """Document model — standalone, user-scoped.

    Documents are decoupled from knowledge bases. They can exist
    independently and be assigned to zero or more KBs via the
    knowledge_base_documents join table.

    Status lifecycle:
      uploaded → pending → processing → completed | error
    """

    __tablename__ = "documents"

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)

    # Docling structured output path
    structured_json_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Document metadata
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Metadata (author, created date, etc.)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Processing status: uploaded, pending, processing, completed, error
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Chunk count
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        "KnowledgeBase",
        secondary="knowledge_base_documents",
        lazy="selectin",
        viewonly=True,
    )
    uploader: Mapped["User | None"] = relationship(
        "User", foreign_keys=[uploaded_by], lazy="selectin",
    )
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        "DocumentChunk",
        back_populates="document",
        lazy="selectin",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename})>"


class DocumentChunk(Base):
    """Document Chunk - text stored here, vectors stored in Qdrant.

    Supports parent-child retrieval: child chunks (small, precise) link
    to parent chunks (large, contextual) via parent_chunk_id.
    """

    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Chunk position in document
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # Element-level fields from Docling
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    element_type: Mapped[str] = mapped_column(String(20), default="text", nullable=False)

    # Parent-child retrieval: self-referencing FK
    parent_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Whether this is a parent chunk (not indexed in Qdrant, only returned as context)
    is_parent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata (section, contextual enrichment, etc.)
    meta_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
    parent_chunk: Mapped["DocumentChunk | None"] = relationship(
        "DocumentChunk", remote_side="DocumentChunk.id", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, index={self.chunk_index})>"
