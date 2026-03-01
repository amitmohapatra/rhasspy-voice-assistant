"""Knowledge Base and Document schemas.

No user-configurable RAG fields - the platform handles everything automatically.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, Field, model_validator

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin
from src.schemas.enums import KnowledgeBaseStatus, DocumentStatus, FileType, ElementType


class KnowledgeBaseCreate(BaseSchema):
    """Schema for creating a new knowledge base.

    A knowledge base stores documents for RAG (Retrieval-Augmented Generation).
    All RAG processing is fully automated:
    - Docling HybridChunker for structure-aware chunking
    - Contextual enrichment for improved retrieval
    - Parent-child retrieval for better context
    - BGE-M3 triple embeddings + 3-way hybrid search + BGE reranker
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the knowledge base.",
        json_schema_extra={"example": "Product Documentation"}
    )
    description: str | None = Field(
        default=None,
        description="Description of the knowledge base's purpose and content.",
        json_schema_extra={"example": "Technical documentation and user guides for our products."}
    )
    settings: dict = Field(
        default_factory=dict,
        description="Additional settings for the knowledge base.",
        json_schema_extra={"example": {}}
    )
    kb_type: str = Field(
        default="platform_managed",
        description="Knowledge base type: 'platform_managed' (default) or 'provider_managed'.",
        json_schema_extra={"example": "platform_managed"}
    )
    provider_id: str | None = Field(
        default=None,
        description="ID of the integration provider. Required when kb_type is 'provider_managed'.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    provider_config: dict | None = Field(
        default=None,
        description="Provider-specific configuration for the knowledge base.",
        json_schema_extra={"example": {"index_name": "my-index"}}
    )

    @model_validator(mode="after")
    def validate_provider_fields(self) -> KnowledgeBaseCreate:
        """Ensure provider_id is set when kb_type is provider_managed."""
        if self.kb_type == "provider_managed" and not self.provider_id:
            raise ValueError("provider_id is required when kb_type is 'provider_managed'")
        return self


class KnowledgeBaseUpdate(BaseSchema):
    """Schema for updating a knowledge base."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated name.",
        json_schema_extra={"example": "Product Documentation v2"}
    )
    description: str | None = Field(
        default=None,
        description="Updated description.",
        json_schema_extra={"example": "Updated documentation including new features."}
    )
    settings: dict | None = Field(
        default=None,
        description="Updated settings.",
        json_schema_extra={"example": {}}
    )
    kb_type: str | None = Field(
        default=None,
        description="Updated knowledge base type: 'platform_managed' or 'provider_managed'.",
        json_schema_extra={"example": "platform_managed"}
    )
    provider_id: str | None = Field(
        default=None,
        description="Updated integration provider ID.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    provider_config: dict | None = Field(
        default=None,
        description="Updated provider-specific configuration.",
        json_schema_extra={"example": {"index_name": "my-index"}}
    )


class DocumentUpload(BaseSchema):
    """Schema for document upload request."""

    filename: str = Field(
        ...,
        description="Original filename of the document.",
        json_schema_extra={"example": "user_guide.pdf"}
    )
    file_type: FileType = Field(
        ...,
        description="Type of the document file.",
        json_schema_extra={"example": "pdf"}
    )
    content: str | None = Field(
        default=None,
        description="Base64-encoded file content. Required if not uploading via multipart form.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Additional metadata for the document.",
        json_schema_extra={
            "example": {
                "author": "John Doe",
                "version": "1.0",
                "category": "User Guide"
            }
        }
    )


class KnowledgeBaseSummary(BaseSchema):
    """Minimal KB info embedded in document responses."""

    id: UUID
    name: str


class DocumentResponse(BaseSchema, IDMixin):
    """Schema for document data in API responses."""

    knowledge_base_id: UUID | None = Field(
        default=None,
        description="ID of the knowledge base containing this document (legacy, use knowledge_bases list).",
    )
    knowledge_bases: list[KnowledgeBaseSummary] = Field(
        default_factory=list,
        description="Knowledge bases this document is assigned to.",
    )
    filename: str = Field(
        ...,
        description="Original filename.",
        json_schema_extra={"example": "user_guide.pdf"}
    )
    file_type: str = Field(
        ...,
        description="Type of the document.",
        json_schema_extra={"example": "pdf"}
    )
    file_size: int = Field(
        ...,
        description="File size in bytes.",
        json_schema_extra={"example": 1024000}
    )
    status: DocumentStatus = Field(
        ...,
        description="Processing status of the document.",
        json_schema_extra={"example": "completed"}
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if processing failed.",
    )
    chunk_count: int = Field(
        ...,
        description="Number of chunks extracted from the document.",
        json_schema_extra={"example": 45}
    )
    structured_json_path: str | None = Field(
        default=None,
        description="Path to Docling structured JSON output.",
    )
    page_count: int | None = Field(
        default=None,
        description="Number of pages in the document.",
        json_schema_extra={"example": 12}
    )
    language: str | None = Field(
        default=None,
        description="Detected language of the document.",
        json_schema_extra={"example": "en"}
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Document metadata.",
        json_schema_extra={"example": {"author": "John Doe"}},
        validation_alias=AliasChoices("meta_data", "metadata"),
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the document was uploaded.",
    )


class DocumentChunkResponse(BaseSchema, IDMixin):
    """Schema for document chunk data in API responses."""

    document_id: UUID = Field(
        ...,
        description="ID of the source document.",
    )
    content: str = Field(
        ...,
        description="Content of the chunk.",
    )
    chunk_index: int = Field(
        ...,
        description="Index of the chunk within the document.",
        json_schema_extra={"example": 0}
    )
    page_number: int | None = Field(
        default=None,
        description="Page number in the original document.",
        json_schema_extra={"example": 3}
    )
    element_type: str = Field(
        default="text",
        description="Type of document element (text, table, image, equation, code, heading).",
        json_schema_extra={"example": "text"}
    )
    is_parent: bool = Field(
        default=False,
        description="Whether this is a parent chunk (context only, not indexed).",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Chunk metadata.",
    )


class KnowledgeBaseResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for knowledge base data in API responses."""

    name: str = Field(
        ...,
        description="Name of the knowledge base.",
        json_schema_extra={"example": "Product Documentation"}
    )
    description: str | None = Field(
        default=None,
        description="Description of the knowledge base.",
    )
    settings: dict = Field(
        default_factory=dict,
        description="Knowledge base settings.",
    )
    status: KnowledgeBaseStatus = Field(
        ...,
        description="Overall status of the knowledge base.",
        json_schema_extra={"example": "ready"}
    )
    documents: list[DocumentResponse] = Field(
        default_factory=list,
        description="List of documents in the knowledge base."
    )
    document_count: int = Field(
        default=0,
        description="Total number of documents.",
        json_schema_extra={"example": 5}
    )
    total_chunks: int = Field(
        default=0,
        description="Total number of chunks across all documents.",
        json_schema_extra={"example": 250}
    )
    kb_type: str = Field(
        default="platform_managed",
        description="Knowledge base type: 'platform_managed' or 'provider_managed'.",
        json_schema_extra={"example": "platform_managed"}
    )
    provider_id: UUID | None = Field(
        default=None,
        description="ID of the integration provider (for provider_managed KBs).",
    )
    provider_kb_ref: str | None = Field(
        default=None,
        description="Provider-side reference ID for the knowledge base.",
    )
    provider_config: dict | None = Field(
        default=None,
        description="Provider-specific configuration.",
    )
    pipeline_info: dict = Field(
        default_factory=dict,
        description="Information about the fixed RAG pipeline.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Product Documentation",
                "description": "Technical documentation and user guides.",
                "settings": {},
                "status": "ready",
                "documents": [],
                "document_count": 5,
                "total_chunks": 250,
                "kb_type": "platform_managed",
                "provider_id": None,
                "provider_kb_ref": None,
                "provider_config": None,
                "pipeline_info": {
                    "chunking": "Docling HybridChunker",
                    "embedding": "BGE-M3 (dense+sparse+ColBERT)",
                    "retrieval": "3-way hybrid + RRF + BGE reranker",
                },
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class KnowledgeBaseListResponse(BaseSchema):
    """Schema for paginated list of knowledge bases."""

    items: list[KnowledgeBaseResponse] = Field(
        default_factory=list,
        description="List of knowledge bases."
    )
    total: int = Field(
        ...,
        description="Total number of knowledge bases.",
        json_schema_extra={"example": 10}
    )
    page: int = Field(
        ...,
        description="Current page number.",
        json_schema_extra={"example": 1}
    )
    page_size: int = Field(
        ...,
        description="Number of items per page.",
        json_schema_extra={"example": 20}
    )
    has_more: bool = Field(
        ...,
        description="Whether there are more pages.",
        json_schema_extra={"example": False}
    )


class SearchRequest(BaseSchema):
    """Schema for semantic search request."""

    query: str = Field(
        ...,
        min_length=1,
        description="Search query text.",
        json_schema_extra={"example": "How do I reset my password?"}
    )
    knowledge_base_ids: list[UUID] = Field(
        default_factory=list,
        description="List of knowledge base IDs to search. If empty, searches all accessible knowledge bases.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of results to return.",
        json_schema_extra={"example": 5}
    )
    threshold: float = Field(
        default=0.7,
        ge=0,
        le=1,
        description="Minimum relevance score (0-1).",
        json_schema_extra={"example": 0.7}
    )


class SearchResult(BaseSchema):
    """Schema for a single search result."""

    chunk_id: UUID = Field(
        ...,
        description="ID of the matching chunk.",
    )
    document_id: UUID = Field(
        ...,
        description="ID of the source document.",
    )
    knowledge_base_id: UUID = Field(
        ...,
        description="ID of the knowledge base.",
    )
    content: str = Field(
        ...,
        description="Content of the matching chunk.",
    )
    parent_content: str | None = Field(
        default=None,
        description="Content of the parent section (broader context).",
    )
    score: float = Field(
        ...,
        description="Relevance score (0-1).",
        json_schema_extra={"example": 0.92}
    )
    page_number: int | None = Field(
        default=None,
        description="Page number in the source document.",
    )
    element_type: str = Field(
        default="text",
        description="Type of document element.",
    )
    metadata: dict = Field(
        default_factory=dict,
        description="Chunk and document metadata.",
    )


class SearchResponse(BaseSchema):
    """Schema for search results response."""

    results: list[SearchResult] = Field(
        default_factory=list,
        description="List of search results ordered by relevance."
    )
    total_results: int = Field(
        ...,
        description="Total number of matching results.",
        json_schema_extra={"example": 5}
    )
    query: str = Field(
        ...,
        description="The original search query.",
        json_schema_extra={"example": "How do I reset my password?"}
    )
