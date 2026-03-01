"""BM25 keyword retrieval strategy.

Traditional keyword-based retrieval using BM25 algorithm.
Excellent for exact term matching and acronyms.

Complexity: O(n) for full scan, O(log n) with inverted index
"""

from __future__ import annotations

import math
import re
from typing import Optional
from collections import Counter

from src.rag.base import (
    BaseRetriever,
    Chunk,
    SearchResult,
    RAGConfig,
    normalize_score,
)


class BM25Retriever(BaseRetriever):
    """BM25 keyword-based retrieval.

    Implements the BM25 (Best Matching 25) algorithm for
    keyword-based document retrieval. Excellent for:
    - Exact term matching
    - Acronyms and proper nouns
    - Technical terminology
    - When semantic similarity fails

    BM25 Parameters:
    - k1: Term frequency saturation (default 1.5)
    - b: Length normalization (default 0.75)

    Best for:
    - Exact keyword matches
    - Technical documents with specific terms
    - Acronyms that embeddings miss
    - Complementing vector search in hybrid
    """

    def __init__(
        self,
        config: RAGConfig,
        chunks: Optional[list[Chunk]] = None,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        """Initialize BM25 retriever.

        Args:
            config: RAG configuration
            chunks: Initial chunks to index
            k1: Term frequency saturation parameter
            b: Length normalization parameter
        """
        super().__init__(config)
        self.k1 = k1
        self.b = b

        # Index structures
        self._chunks: list[Chunk] = []
        self._doc_freqs: dict[str, int] = {}  # Term -> document frequency
        self._doc_lengths: list[int] = []
        self._avg_doc_length: float = 0.0
        self._tokenized_docs: list[list[str]] = []

        if chunks:
            self.index_chunks(chunks)

    def index_chunks(self, chunks: list[Chunk]) -> None:
        """Index chunks for BM25 retrieval.

        Args:
            chunks: Chunks to index
        """
        self._chunks = chunks
        self._doc_freqs = {}
        self._doc_lengths = []
        self._tokenized_docs = []

        total_length = 0

        for chunk in chunks:
            # Tokenize
            tokens = self._tokenize(chunk.content)
            self._tokenized_docs.append(tokens)
            self._doc_lengths.append(len(tokens))
            total_length += len(tokens)

            # Update document frequencies
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1

        # Calculate average document length
        if chunks:
            self._avg_doc_length = total_length / len(chunks)

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """Add more chunks to the index.

        Args:
            chunks: Chunks to add
        """
        for chunk in chunks:
            tokens = self._tokenize(chunk.content)
            self._tokenized_docs.append(tokens)
            self._doc_lengths.append(len(tokens))
            self._chunks.append(chunk)

            # Update document frequencies
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] = self._doc_freqs.get(token, 0) + 1

        # Recalculate average length
        if self._chunks:
            self._avg_doc_length = sum(self._doc_lengths) / len(self._chunks)

    async def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_metadata: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Retrieve chunks using BM25 scoring.

        Args:
            query: Search query
            top_k: Number of results
            filter_metadata: Optional metadata filters

        Returns:
            List of search results ranked by BM25 score
        """
        if not self._chunks:
            return []

        top_k = top_k or self.config.top_k
        query_tokens = self._tokenize(query)
        n_docs = len(self._chunks)

        # Calculate BM25 scores for all documents
        scores: list[tuple[int, float]] = []

        for doc_idx, (doc_tokens, doc_length) in enumerate(
            zip(self._tokenized_docs, self._doc_lengths)
        ):
            # Apply metadata filter
            if filter_metadata:
                chunk = self._chunks[doc_idx]
                if not self._matches_filter(chunk, filter_metadata):
                    continue

            score = self._bm25_score(
                query_tokens=query_tokens,
                doc_tokens=doc_tokens,
                doc_length=doc_length,
                n_docs=n_docs,
            )

            if score > 0:
                scores.append((doc_idx, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        # Convert to SearchResult
        results = []
        max_score = scores[0][1] if scores else 1.0

        for rank, (doc_idx, score) in enumerate(scores[:top_k], 1):
            chunk = self._chunks[doc_idx]

            results.append(SearchResult(
                chunk=chunk,
                score=normalize_score(score / max_score),  # Normalize to 0-1
                rank=rank,
                retrieval_method="bm25",
            ))

        return results

    def _bm25_score(
        self,
        query_tokens: list[str],
        doc_tokens: list[str],
        doc_length: int,
        n_docs: int,
    ) -> float:
        """Calculate BM25 score for a document.

        Args:
            query_tokens: Tokenized query
            doc_tokens: Tokenized document
            doc_length: Document length in tokens
            n_docs: Total number of documents

        Returns:
            BM25 score
        """
        score = 0.0
        doc_term_freqs = Counter(doc_tokens)

        for term in query_tokens:
            if term not in self._doc_freqs:
                continue

            # Term frequency in document
            tf = doc_term_freqs.get(term, 0)
            if tf == 0:
                continue

            # Document frequency
            df = self._doc_freqs[term]

            # IDF component
            idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

            # TF component with saturation and length normalization
            length_norm = 1 - self.b + self.b * (doc_length / self._avg_doc_length)
            tf_component = (tf * (self.k1 + 1)) / (tf + self.k1 * length_norm)

            score += idf * tf_component

        return score

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text for BM25.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens (lowercase, alphanumeric)
        """
        # Simple tokenization: lowercase and split on non-alphanumeric
        text = text.lower()
        tokens = re.findall(r'\b\w+\b', text)

        # Remove very short tokens and stopwords
        stopwords = {
            'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'is', 'it', 'as', 'be', 'are', 'was',
            'were', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'we',
            'they', 'what', 'which', 'who', 'whom', 'when', 'where', 'why', 'how',
        }

        return [t for t in tokens if len(t) > 1 and t not in stopwords]

    def _matches_filter(self, chunk: Chunk, filter_metadata: dict) -> bool:
        """Check if chunk matches metadata filter.

        Supports both single values and lists (MatchAny semantics).

        Args:
            chunk: Chunk to check
            filter_metadata: Filter criteria

        Returns:
            True if matches
        """
        for key, value in filter_metadata.items():
            chunk_value = chunk.metadata.get(key)
            if key == "document_id":
                chunk_value = chunk.document_id

            if isinstance(value, list):
                if chunk_value not in value:
                    return False
            elif chunk_value != value:
                return False

        return True


class InMemoryBM25Retriever(BM25Retriever):
    """BM25 retriever with in-memory chunk storage.

    Convenience class that stores chunks in memory and
    provides automatic indexing.
    """

    def __init__(
        self,
        config: RAGConfig,
        k1: float = 1.5,
        b: float = 0.75,
    ):
        """Initialize in-memory BM25 retriever.

        Args:
            config: RAG configuration
            k1: BM25 k1 parameter
            b: BM25 b parameter
        """
        super().__init__(config, None, k1, b)

    def add_document(self, document_id: str, chunks: list[Chunk]) -> None:
        """Add a document's chunks to the index.

        Args:
            document_id: Document identifier
            chunks: Chunks from the document
        """
        # Set document_id on chunks if not set
        for chunk in chunks:
            if not chunk.document_id:
                chunk.document_id = document_id

        self.add_chunks(chunks)

    def remove_document(self, document_id: str) -> int:
        """Remove a document's chunks from the index.

        Args:
            document_id: Document to remove

        Returns:
            Number of chunks removed
        """
        # Find indices to remove
        indices_to_remove = [
            i for i, chunk in enumerate(self._chunks)
            if chunk.document_id == document_id
        ]

        if not indices_to_remove:
            return 0

        # Remove in reverse order to maintain indices
        for idx in reversed(indices_to_remove):
            # Update document frequencies
            tokens = self._tokenized_docs[idx]
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self._doc_freqs[token] = max(0, self._doc_freqs.get(token, 1) - 1)
                if self._doc_freqs[token] == 0:
                    del self._doc_freqs[token]

            # Remove from lists
            del self._chunks[idx]
            del self._tokenized_docs[idx]
            del self._doc_lengths[idx]

        # Recalculate average length
        if self._chunks:
            self._avg_doc_length = sum(self._doc_lengths) / len(self._chunks)
        else:
            self._avg_doc_length = 0.0

        return len(indices_to_remove)
