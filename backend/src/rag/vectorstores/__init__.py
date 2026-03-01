"""Vector store backends for RAG.

Qdrant is the sole vector database for the platform.
"""

from src.rag.vectorstores.qdrant import QdrantStore

__all__ = [
    "QdrantStore",
]
