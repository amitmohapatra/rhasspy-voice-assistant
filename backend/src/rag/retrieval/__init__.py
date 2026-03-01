"""Retrieval strategies for RAG.

Primary strategy:
- TripleHybridRetriever: 4-way dense+sparse+BM25+visual with RRF fusion (sole retriever)

Supporting:
- BM25Retriever: Keyword-based BM25 search (loaded lazily from DB per query)

Reranking is handled by the inference service via RemoteReranker (see rag.factory).
"""

from src.rag.retrieval.bm25 import BM25Retriever
from src.rag.retrieval.hybrid import TripleHybridRetriever

__all__ = [
    "TripleHybridRetriever",
    "BM25Retriever",
]
