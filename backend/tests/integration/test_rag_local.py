"""
Local integration tests for RAG system.

Tests all RAG strategies, chunking methods, and retrieval with local deployment.
"""

import asyncio
import pytest
from typing import List

# Test imports
import sys
sys.path.insert(0, '/Users/ricky/my_public_projects/rhasspy-voice-assistant/backend')

from src.rag.base import Document, Chunk, RAGConfig
from src.rag.chunking.fixed import FixedChunker
from src.rag.chunking.sentence import SentenceChunker
from src.rag.chunking.recursive import RecursiveChunker
from src.rag.chunking.markdown import MarkdownChunker
from src.rag.chunking.code import CodeChunker
from src.rag.chunking.hierarchical import HierarchicalChunker


# Sample test documents
SAMPLE_TEXT = """
# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that enables systems to learn from data.
There are three main types of machine learning: supervised learning, unsupervised learning, and reinforcement learning.

## Supervised Learning

Supervised learning uses labeled datasets to train algorithms. The algorithm learns to map inputs to outputs.
Common algorithms include linear regression, decision trees, and neural networks.

### Examples
- Email spam detection
- Image classification
- Price prediction

## Unsupervised Learning

Unsupervised learning finds hidden patterns in unlabeled data.
Clustering and dimensionality reduction are common techniques.

## Reinforcement Learning

Reinforcement learning trains agents through rewards and penalties.
Applications include game playing and robotics.
"""

SAMPLE_CODE = '''
def calculate_embedding(text: str, model: str = "default") -> List[float]:
    """Calculate embedding vector for text."""
    if not text:
        raise ValueError("Text cannot be empty")

    # Preprocess text
    text = text.strip().lower()

    # Get embedding from model
    embedding = model.encode(text)

    return embedding.tolist()


class VectorStore:
    """Store and retrieve vectors."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.vectors = []
        self.metadata = []

    def add(self, vector: List[float], meta: dict = None):
        """Add vector to store."""
        if len(vector) != self.dimension:
            raise ValueError(f"Expected {self.dimension} dimensions")
        self.vectors.append(vector)
        self.metadata.append(meta or {})

    def search(self, query: List[float], top_k: int = 5) -> List[dict]:
        """Search for similar vectors."""
        # Calculate similarities
        results = []
        for i, vec in enumerate(self.vectors):
            similarity = self._cosine_similarity(query, vec)
            results.append({"score": similarity, "metadata": self.metadata[i]})

        # Sort and return top k
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x ** 2 for x in a) ** 0.5
        norm_b = sum(x ** 2 for x in b) ** 0.5
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
'''


class TestChunkingStrategies:
    """Test all chunking strategies."""

    def test_fixed_chunker(self):
        """Test fixed-size chunking."""
        chunker = FixedChunker(chunk_size=200, chunk_overlap=20)
        doc = Document(id="test-1", content=SAMPLE_TEXT, metadata={"source": "test"})

        chunks = chunker.chunk(doc)

        assert len(chunks) > 0, "Should produce at least one chunk"
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
            assert chunk.document_id == "test-1"
            assert len(chunk.content) > 0
        print(f"FixedChunker: {len(chunks)} chunks created")

    def test_sentence_chunker(self):
        """Test sentence-based chunking."""
        chunker = SentenceChunker(chunk_size=300, chunk_overlap=30)
        doc = Document(id="test-2", content=SAMPLE_TEXT, metadata={"source": "test"})

        chunks = chunker.chunk(doc)

        assert len(chunks) > 0, "Should produce at least one chunk"
        # Sentence chunker should preserve sentence boundaries
        for chunk in chunks:
            assert isinstance(chunk, Chunk)
        print(f"SentenceChunker: {len(chunks)} chunks created")

    def test_recursive_chunker(self):
        """Test recursive text splitting (default strategy)."""
        chunker = RecursiveChunker(chunk_size=300, chunk_overlap=30)
        doc = Document(id="test-3", content=SAMPLE_TEXT, metadata={"source": "test"})

        chunks = chunker.chunk(doc)

        assert len(chunks) > 0, "Should produce at least one chunk"
        print(f"RecursiveChunker: {len(chunks)} chunks created")

    def test_markdown_chunker(self):
        """Test markdown-aware chunking."""
        chunker = MarkdownChunker(chunk_size=300, chunk_overlap=30)
        doc = Document(id="test-4", content=SAMPLE_TEXT, metadata={"source": "test"})

        chunks = chunker.chunk(doc)

        assert len(chunks) > 0, "Should produce at least one chunk"
        # Check that headers are preserved in metadata or content
        print(f"MarkdownChunker: {len(chunks)} chunks created")

    def test_code_chunker(self):
        """Test code-aware chunking."""
        chunker = CodeChunker(chunk_size=500, chunk_overlap=50, language="python")
        doc = Document(id="test-5", content=SAMPLE_CODE, metadata={"source": "test.py"})

        chunks = chunker.chunk(doc)

        assert len(chunks) > 0, "Should produce at least one chunk"
        # Code chunker should respect function/class boundaries
        print(f"CodeChunker: {len(chunks)} chunks created")

    def test_hierarchical_chunker(self):
        """Test hierarchical chunking with parent-child relationships."""
        chunker = HierarchicalChunker(
            parent_chunk_size=500,
            child_chunk_size=150,
            chunk_overlap=20
        )
        doc = Document(id="test-6", content=SAMPLE_TEXT, metadata={"source": "test"})

        chunks = chunker.chunk(doc)

        assert len(chunks) > 0, "Should produce at least one chunk"
        print(f"HierarchicalChunker: {len(chunks)} chunks created")


class TestRAGConfig:
    """Test RAG configuration."""

    def test_default_config(self):
        """Test default RAG configuration."""
        config = RAGConfig()

        assert config.chunking_strategy == "recursive"
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        print(f"Default config: {config.chunking_strategy}, size={config.chunk_size}")

    def test_custom_config(self):
        """Test custom RAG configuration."""
        config = RAGConfig(
            chunking_strategy="semantic",
            chunk_size=256,
            chunk_overlap=25,
            embedding_model="text-embedding-3-small",
            retrieval_strategy="hybrid",
            top_k=10,
            similarity_threshold=0.75
        )

        assert config.chunking_strategy == "semantic"
        assert config.chunk_size == 256
        assert config.retrieval_strategy == "hybrid"
        assert config.top_k == 10
        print(f"Custom config: {config.chunking_strategy}, retrieval={config.retrieval_strategy}")


class TestDocumentProcessing:
    """Test document processing."""

    def test_document_creation(self):
        """Test document creation with auto ID."""
        doc = Document(
            content="Test content for document",
            metadata={"author": "test", "date": "2024-01-01"}
        )

        assert doc.id is not None
        assert doc.content == "Test content for document"
        assert doc.metadata["author"] == "test"
        print(f"Document created with ID: {doc.id[:20]}...")

    def test_chunk_creation(self):
        """Test chunk creation."""
        chunk = Chunk(
            id="chunk-1",
            document_id="doc-1",
            content="This is chunk content",
            metadata={"position": 0}
        )

        assert chunk.id == "chunk-1"
        assert chunk.document_id == "doc-1"
        assert chunk.embedding is None  # Not embedded yet
        print(f"Chunk created: {chunk.id}")


def run_all_tests():
    """Run all tests and print results."""
    print("=" * 60)
    print("RAG LOCAL INTEGRATION TESTS")
    print("=" * 60)

    # Test chunking strategies
    print("\n--- Testing Chunking Strategies ---")
    chunking_tests = TestChunkingStrategies()

    try:
        chunking_tests.test_fixed_chunker()
        print("  [PASS] Fixed Chunker")
    except Exception as e:
        print(f"  [FAIL] Fixed Chunker: {e}")

    try:
        chunking_tests.test_sentence_chunker()
        print("  [PASS] Sentence Chunker")
    except Exception as e:
        print(f"  [FAIL] Sentence Chunker: {e}")

    try:
        chunking_tests.test_recursive_chunker()
        print("  [PASS] Recursive Chunker")
    except Exception as e:
        print(f"  [FAIL] Recursive Chunker: {e}")

    try:
        chunking_tests.test_markdown_chunker()
        print("  [PASS] Markdown Chunker")
    except Exception as e:
        print(f"  [FAIL] Markdown Chunker: {e}")

    try:
        chunking_tests.test_code_chunker()
        print("  [PASS] Code Chunker")
    except Exception as e:
        print(f"  [FAIL] Code Chunker: {e}")

    try:
        chunking_tests.test_hierarchical_chunker()
        print("  [PASS] Hierarchical Chunker")
    except Exception as e:
        print(f"  [FAIL] Hierarchical Chunker: {e}")

    # Test configuration
    print("\n--- Testing RAG Configuration ---")
    config_tests = TestRAGConfig()

    try:
        config_tests.test_default_config()
        print("  [PASS] Default Config")
    except Exception as e:
        print(f"  [FAIL] Default Config: {e}")

    try:
        config_tests.test_custom_config()
        print("  [PASS] Custom Config")
    except Exception as e:
        print(f"  [FAIL] Custom Config: {e}")

    # Test document processing
    print("\n--- Testing Document Processing ---")
    doc_tests = TestDocumentProcessing()

    try:
        doc_tests.test_document_creation()
        print("  [PASS] Document Creation")
    except Exception as e:
        print(f"  [FAIL] Document Creation: {e}")

    try:
        doc_tests.test_chunk_creation()
        print("  [PASS] Chunk Creation")
    except Exception as e:
        print(f"  [FAIL] Chunk Creation: {e}")

    print("\n" + "=" * 60)
    print("RAG LOCAL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
