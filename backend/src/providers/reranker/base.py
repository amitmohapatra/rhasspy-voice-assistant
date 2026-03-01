"""Base reranker provider class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any
from pydantic import BaseModel

from src.providers.base import BaseProvider, ProviderType


class RerankedDocument(BaseModel):
    """A document with its reranking score."""
    id: str
    content: str
    score: float
    original_rank: int
    metadata: dict[str, Any] = {}


class RerankerResult(BaseModel):
    """Result of reranking operation."""
    documents: list[RerankedDocument]
    model: str
    query: str


class BaseRerankerProvider(BaseProvider[RerankerResult]):
    """Base class for reranker providers."""

    provider_type = ProviderType.EMBEDDINGS  # Reuse embeddings type for now

    @abstractmethod
    async def rerank(
        self,
        query: str,
        documents: list[dict[str, Any]],
        top_k: int = 10,
        **kwargs,
    ) -> RerankerResult:
        """Rerank documents based on relevance to query.

        Args:
            query: The search query
            documents: List of documents with 'id' and 'content' keys
            top_k: Number of top documents to return
            **kwargs: Provider-specific options

        Returns:
            RerankerResult with reranked documents
        """
        pass

    async def rerank_with_scores(
        self,
        query: str,
        documents: list[dict[str, Any]],
        **kwargs,
    ) -> list[tuple[dict[str, Any], float]]:
        """Rerank and return documents with scores.

        Returns list of (document, score) tuples.
        """
        result = await self.rerank(query, documents, top_k=len(documents), **kwargs)
        return [
            ({"id": doc.id, "content": doc.content, **doc.metadata}, doc.score)
            for doc in result.documents
        ]
