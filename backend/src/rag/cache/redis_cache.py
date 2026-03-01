"""Redis-based caching for RAG.

Provides persistent caching for:
- Semantic cache: Cache query results by semantic similarity

Redis is recommended for production deployments where cache
persistence and sharing across instances is needed.

Complexity:
- Set: O(1) for hash, O(log n) for sorted set
- Get: O(1) for hash, O(log n) for range
- Semantic lookup: O(n) for similarity scan (consider vector index)
"""

from __future__ import annotations

import json
import hashlib
import time
from typing import Optional, Any
import asyncio

from src.rag.base import BaseCache, SearchResult, Chunk, RAGConfig


class RedisSemanticCache(BaseCache):
    """Semantic cache using Redis.

    Caches query results and retrieves them when similar queries
    are made. Uses embedding similarity to determine cache hits.

    Features:
    - Semantic similarity matching (not exact)
    - Configurable similarity threshold
    - TTL-based expiration
    - Hit rate tracking

    Best for:
    - Production deployments
    - Multi-instance setups
    - When cache persistence matters

    Configuration:
    - similarity_threshold: 0.85-0.95 recommended
    - ttl: Time-to-live in seconds
    - max_entries: Maximum cache entries
    """

    def __init__(
        self,
        config: RAGConfig,
        redis_url: str = "redis://localhost:6379",
        prefix: str = "rag:semantic:",
        similarity_threshold: float = 0.90,
        ttl: int = 3600,  # 1 hour
        max_entries: int = 10000,
    ):
        """Initialize Redis semantic cache.

        Args:
            config: RAG configuration
            redis_url: Redis connection URL
            prefix: Key prefix for namespacing
            similarity_threshold: Minimum similarity for cache hit
            ttl: Cache entry TTL in seconds
            max_entries: Maximum cache entries
        """
        super().__init__(config)
        self.redis_url = redis_url
        self.prefix = prefix
        self.similarity_threshold = similarity_threshold
        self.ttl = ttl
        self.max_entries = max_entries
        self._redis = None
        self._hits = 0
        self._misses = 0

    async def _get_redis(self):
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis
            except ImportError:
                raise ImportError(
                    "redis is required for RedisSemanticCache. "
                    "Install with: pip install redis"
                )

            self._redis = redis.from_url(self.redis_url)

        return self._redis

    async def get(
        self,
        key: str,
        query_embedding: Optional[list[float]] = None,
    ) -> Optional[list[SearchResult]]:
        """Get cached results by key or semantic similarity.

        Args:
            key: Cache key (query text)
            query_embedding: Query embedding for semantic matching

        Returns:
            Cached results or None
        """
        redis = await self._get_redis()

        # First try exact match
        exact_key = self._make_key(key)
        cached = await redis.get(exact_key)

        if cached:
            self._hits += 1
            return self._deserialize_results(cached)

        # Try semantic matching if embedding provided
        if query_embedding:
            similar = await self._find_similar(query_embedding)
            if similar:
                self._hits += 1
                return similar

        self._misses += 1
        return None

    async def set(
        self,
        key: str,
        results: list[SearchResult],
        query_embedding: Optional[list[float]] = None,
        ttl: Optional[int] = None,
    ) -> None:
        """Cache query results.

        Args:
            key: Cache key (query text)
            results: Results to cache
            query_embedding: Query embedding for semantic matching
            ttl: Optional custom TTL
        """
        redis = await self._get_redis()
        cache_key = self._make_key(key)
        ttl = ttl or self.ttl

        # Serialize results
        serialized = self._serialize_results(results)

        # Store in Redis
        await redis.setex(cache_key, ttl, serialized)

        # Store embedding for semantic matching
        if query_embedding:
            embedding_key = f"{self.prefix}emb:{cache_key}"
            await redis.setex(
                embedding_key,
                ttl,
                json.dumps({
                    "embedding": query_embedding,
                    "cache_key": cache_key,
                    "timestamp": time.time(),
                })
            )

            # Add to index for similarity search
            await self._add_to_index(cache_key, query_embedding)

        # Enforce max entries
        await self._enforce_max_entries()

    async def delete(self, key: str) -> bool:
        """Delete cached entry.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted
        """
        redis = await self._get_redis()
        cache_key = self._make_key(key)

        # Delete main entry and embedding
        deleted = await redis.delete(cache_key)
        await redis.delete(f"{self.prefix}emb:{cache_key}")

        # Remove from index
        await redis.zrem(f"{self.prefix}index", cache_key)

        return deleted > 0

    async def clear(self) -> int:
        """Clear all cache entries.

        Returns:
            Number of entries cleared
        """
        redis = await self._get_redis()

        # Find all keys with prefix
        keys = []
        async for key in redis.scan_iter(f"{self.prefix}*"):
            keys.append(key)

        if keys:
            return await redis.delete(*keys)

        return 0

    def _make_key(self, key: str) -> str:
        """Create cache key from query."""
        # Hash for consistent key length
        key_hash = hashlib.sha256(key.encode()).hexdigest()[:16]
        return f"{self.prefix}{key_hash}"

    def _serialize_results(self, results: list[SearchResult]) -> str:
        """Serialize results for storage."""
        data = []
        for r in results:
            data.append({
                "chunk": {
                    "id": r.chunk.id,
                    "document_id": r.chunk.document_id,
                    "content": r.chunk.content,
                    "metadata": r.chunk.metadata,
                    "chunk_index": r.chunk.chunk_index,
                    "start_char": r.chunk.start_char,
                    "end_char": r.chunk.end_char,
                    "page_number": r.chunk.page_number,
                    "element_type": r.chunk.element_type,
                    "bbox": r.chunk.bbox,
                },
                "score": r.score,
                "rank": r.rank,
                "retrieval_method": r.retrieval_method,
            })
        return json.dumps(data)

    def _deserialize_results(self, data: bytes) -> list[SearchResult]:
        """Deserialize results from storage."""
        items = json.loads(data)
        results = []
        for item in items:
            chunk = Chunk(
                id=item["chunk"]["id"],
                document_id=item["chunk"]["document_id"],
                content=item["chunk"]["content"],
                metadata=item["chunk"].get("metadata", {}),
                chunk_index=item["chunk"].get("chunk_index", 0),
                start_char=item["chunk"].get("start_char", 0),
                end_char=item["chunk"].get("end_char", 0),
                page_number=item["chunk"].get("page_number", 0),
                element_type=item["chunk"].get("element_type", "text"),
                bbox=item["chunk"].get("bbox"),
            )
            results.append(SearchResult(
                chunk=chunk,
                score=item["score"],
                rank=item["rank"],
                retrieval_method=item.get("retrieval_method", "cached"),
            ))
        return results

    async def _find_similar(
        self,
        query_embedding: list[float],
    ) -> Optional[list[SearchResult]]:
        """Find semantically similar cached query.

        Args:
            query_embedding: Query embedding

        Returns:
            Cached results if similar enough
        """
        redis = await self._get_redis()
        import numpy as np

        # Get all cached embeddings
        # Note: For production, consider using Redis Vector Search or
        # a dedicated vector store for this
        index_key = f"{self.prefix}index"
        cache_keys = await redis.zrange(index_key, 0, -1)

        best_score = 0.0
        best_key = None

        for cache_key in cache_keys:
            if isinstance(cache_key, bytes):
                cache_key = cache_key.decode()

            emb_key = f"{self.prefix}emb:{cache_key}"
            emb_data = await redis.get(emb_key)

            if not emb_data:
                continue

            data = json.loads(emb_data)
            cached_embedding = data["embedding"]

            # Calculate cosine similarity
            similarity = self._cosine_similarity(query_embedding, cached_embedding)

            if similarity > best_score:
                best_score = similarity
                best_key = cache_key

        # Check threshold
        if best_score >= self.similarity_threshold and best_key:
            cached = await redis.get(best_key)
            if cached:
                return self._deserialize_results(cached)

        return None

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between vectors."""
        import numpy as np
        a_np = np.array(a)
        b_np = np.array(b)

        norm_a = np.linalg.norm(a_np)
        norm_b = np.linalg.norm(b_np)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return float(np.dot(a_np, b_np) / (norm_a * norm_b))

    async def _add_to_index(self, cache_key: str, embedding: list[float]) -> None:
        """Add entry to similarity index."""
        redis = await self._get_redis()
        index_key = f"{self.prefix}index"

        # Use timestamp as score for LRU ordering
        await redis.zadd(index_key, {cache_key: time.time()})

    async def _enforce_max_entries(self) -> None:
        """Remove oldest entries if over limit."""
        redis = await self._get_redis()
        index_key = f"{self.prefix}index"

        count = await redis.zcard(index_key)
        if count > self.max_entries:
            # Remove oldest entries
            to_remove = count - self.max_entries
            old_keys = await redis.zrange(index_key, 0, to_remove - 1)

            for key in old_keys:
                if isinstance(key, bytes):
                    key = key.decode()
                await self.delete(key.replace(self.prefix, ""))

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    async def stats(self) -> dict:
        """Get cache statistics."""
        redis = await self._get_redis()
        index_key = f"{self.prefix}index"

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
            "entries": await redis.zcard(index_key),
            "max_entries": self.max_entries,
        }


