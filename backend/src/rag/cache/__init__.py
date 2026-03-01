"""Caching layer for RAG.

Redis is the sole cache backend:
- RedisSemanticCache: Cache query results by semantic similarity
"""

from src.rag.cache.redis_cache import RedisSemanticCache

__all__ = [
    "RedisSemanticCache",
]
