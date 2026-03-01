"""Embedding providers.

BGE-M3 is the sole embedding engine for the platform.
"""

from src.providers.embeddings.base import BaseEmbeddingsProvider, EmbeddingResult
from src.providers.embeddings.bge_m3_embeddings import BGEM3EmbeddingsProvider

__all__ = [
    "BaseEmbeddingsProvider",
    "EmbeddingResult",
    "BGEM3EmbeddingsProvider",
]
