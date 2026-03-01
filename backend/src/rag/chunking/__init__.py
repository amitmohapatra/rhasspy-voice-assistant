"""Chunking module for RAG.

Primary chunker:
- DoclingHybridChunker: Unified structure-aware chunker for all document types.
  Uses Docling's HybridChunker for structured documents, falls back to
  token-based recursive splitting for plain text.

Embedding:
- Late chunking via BGE-M3 replaces LLM-based contextual enrichment.
  Zero API calls — document context baked into embeddings via single forward pass.
"""

from src.rag.chunking.docling_hybrid import DoclingHybridChunker

__all__ = [
    "DoclingHybridChunker",
]
