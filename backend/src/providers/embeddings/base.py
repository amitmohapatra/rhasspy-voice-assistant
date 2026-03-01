"""Base embeddings provider class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any
from pydantic import BaseModel

from src.providers.base import BaseProvider, ProviderType


class EmbeddingResult(BaseModel):
    """Result of embedding generation."""
    embeddings: list[list[float]]
    model: str
    dimensions: int
    tokens_used: int | None = None


class BaseEmbeddingsProvider(BaseProvider[EmbeddingResult]):
    """Base class for embedding providers."""

    provider_type = ProviderType.EMBEDDINGS

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> EmbeddingResult:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            **kwargs: Provider-specific options

        Returns:
            EmbeddingResult with embedding vectors
        """
        pass

    async def embed_single(self, text: str, **kwargs) -> list[float]:
        """Embed a single text."""
        result = await self.embed([text], **kwargs)
        return result.embeddings[0]

    @classmethod
    @abstractmethod
    def get_dimensions(cls, model: str) -> int:
        """Get embedding dimensions for a model."""
        pass

    @classmethod
    def get_max_tokens(cls, model: str) -> int:
        """Get max tokens for a model."""
        return 8192  # Default
