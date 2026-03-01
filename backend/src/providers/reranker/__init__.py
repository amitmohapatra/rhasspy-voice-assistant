"""Reranker providers for RAG retrieval enhancement.

Reranking is handled by the inference service via RemoteReranker (see rag.factory).
"""

from src.providers.reranker.base import BaseRerankerProvider, RerankerResult, RerankedDocument

__all__ = [
    "BaseRerankerProvider",
    "RerankerResult",
    "RerankedDocument",
]
