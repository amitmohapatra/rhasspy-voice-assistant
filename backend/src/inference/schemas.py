"""Request/response schemas for inference endpoints."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Embeddings
# ============================================================================

class EmbedTripleRequest(BaseModel):
    texts: list[str]
    max_length: int = Field(default=8192)


class SparseVector(BaseModel):
    indices: list[int]
    weights: list[float]


class TripleEmbeddingResponse(BaseModel):
    dense: list[float]
    sparse: dict[int, float] = Field(default_factory=dict)
    colbert: Optional[list[list[float]]] = None


class EmbedTripleResponse(BaseModel):
    embeddings: list[TripleEmbeddingResponse]


# ============================================================================
# Reranking
# ============================================================================

class RerankDocument(BaseModel):
    id: str
    content: str


class RerankRequest(BaseModel):
    query: str
    documents: list[RerankDocument]
    top_k: Optional[int] = None


class RankedDocument(BaseModel):
    id: str
    content: str
    score: float


class RerankResponse(BaseModel):
    documents: list[RankedDocument]


# ============================================================================
# Document Processing
# ============================================================================

class ProcessedDocumentResponse(BaseModel):
    version: str = "2.0"
    text: str
    elements: dict[str, dict[str, Any]] = Field(default_factory=dict)
    tables: dict[str, dict[str, Any]] = Field(default_factory=dict)
    images: dict[str, dict[str, Any]] = Field(default_factory=dict)
    page_count: int = 1
    page_dimensions: dict[str, dict[str, float]] = Field(default_factory=dict)
    pages: dict[str, Any] = Field(default_factory=dict)
    quality: dict[str, Any] = Field(default_factory=dict)
    conversion_status: str = "unknown"
    timings: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# Late Chunking
# ============================================================================

class LateBatchRequest(BaseModel):
    document_text: str
    chunk_boundaries: list[list[int]]  # [[start_char, end_char], ...]
    max_length: int = Field(default=8192)


class LateBatchResponse(BaseModel):
    embeddings: list[TripleEmbeddingResponse]


# ============================================================================
# Visual Embeddings (ColSmol-256M)
# ============================================================================

class VisualEmbedRequest(BaseModel):
    """Embed page images as multi-vectors."""
    images: list[str]  # Base64-encoded PNG images


class VisualEmbedResponse(BaseModel):
    """Multi-vector embeddings for each page image."""
    embeddings: list[list[list[float]]]  # [page][patch][128-dim]


class VisualQueryRequest(BaseModel):
    """Embed text query as multi-vectors for visual search."""
    query: str


class VisualQueryResponse(BaseModel):
    """Multi-vector query embedding."""
    embedding: list[list[float]]  # [token][128-dim]


# ============================================================================
# Health
# ============================================================================

class ModelStatus(BaseModel):
    loaded: bool
    name: str
    load_time_seconds: Optional[float] = None


class HealthResponse(BaseModel):
    status: str  # "healthy", "loading", "unhealthy"
    models_loaded: dict[str, ModelStatus] = Field(default_factory=dict)
    gpu_available: bool = False
    memory_usage_mb: float = 0.0
