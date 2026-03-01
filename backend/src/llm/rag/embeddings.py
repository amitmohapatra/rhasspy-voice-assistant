"""Embedding service for RAG."""

from __future__ import annotations

import hashlib
from typing import Any

from src.core.config import settings
from src.llm.gateway import get_llm_gateway


class EmbeddingService:
    """Service for generating and caching embeddings."""

    def __init__(
        self,
        model: str | None = None,
        provider: str = "openai",
        cache: Any | None = None,
    ) -> None:
        self.model = model or settings.default_embedding_model
        self.provider = provider
        self.cache = cache  # Redis cache instance
        self.gateway = get_llm_gateway()

    async def embed_texts(
        self,
        texts: list[str],
        use_cache: bool = True,
    ) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use caching

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        # Check cache first if enabled
        if use_cache and self.cache:
            cached_embeddings, uncached_texts, uncached_indices = (
                await self._get_cached_embeddings(texts)
            )

            if not uncached_texts:
                return cached_embeddings

            # Generate embeddings for uncached texts
            new_embeddings = await self._generate_embeddings(uncached_texts)

            # Cache new embeddings
            await self._cache_embeddings(uncached_texts, new_embeddings)

            # Merge cached and new embeddings
            result = cached_embeddings.copy()
            for i, idx in enumerate(uncached_indices):
                result[idx] = new_embeddings[i]

            return result

        # No caching - generate all embeddings
        return await self._generate_embeddings(texts)

    async def embed_text(self, text: str, use_cache: bool = True) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text], use_cache=use_cache)
        return embeddings[0]

    async def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings via LLM gateway."""
        return await self.gateway.embed(
            texts=texts,
            model=self.model,
            provider=self.provider,
        )

    async def _get_cached_embeddings(
        self,
        texts: list[str],
    ) -> tuple[list[list[float] | None], list[str], list[int]]:
        """Get cached embeddings and identify uncached texts.

        Returns:
            - List of embeddings (None for uncached)
            - List of uncached texts
            - List of indices of uncached texts
        """
        import json

        embeddings: list[list[float] | None] = [None] * len(texts)
        uncached_texts = []
        uncached_indices = []

        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            cached = await self.cache.get(cache_key)

            if cached:
                embeddings[i] = json.loads(cached)
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        return embeddings, uncached_texts, uncached_indices  # type: ignore

    async def _cache_embeddings(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        ttl: int = 86400,  # 24 hours
    ) -> None:
        """Cache embeddings."""
        import json

        for text, embedding in zip(texts, embeddings):
            cache_key = self._get_cache_key(text)
            await self.cache.setex(cache_key, ttl, json.dumps(embedding))

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        return f"emb:{self.model}:{text_hash}"
