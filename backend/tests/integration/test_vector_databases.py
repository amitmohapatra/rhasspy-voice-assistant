"""Integration tests for vector database providers.

Tests Qdrant vector database and Redis vector search.
"""

import pytest
import pytest_asyncio
import numpy as np
from typing import List
import uuid

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def generate_random_vector(dimensions: int = 1536) -> List[float]:
    """Generate a random vector for testing."""
    return np.random.rand(dimensions).tolist()


def generate_random_vectors(count: int, dimensions: int = 1536) -> List[List[float]]:
    """Generate multiple random vectors for testing."""
    return [generate_random_vector(dimensions) for _ in range(count)]


class TestQdrantIntegration:
    """Test Qdrant vector database integration."""

    def test_create_collection(self, qdrant_client):
        """Test creating a Qdrant collection."""
        from qdrant_client.models import Distance, VectorParams

        collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"

        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )

        # Verify collection exists
        collections = qdrant_client.get_collections()
        collection_names = [c.name for c in collections.collections]
        assert collection_name in collection_names

        # Cleanup
        qdrant_client.delete_collection(collection_name)

    def test_upsert_vectors(self, qdrant_client, test_qdrant_collection):
        """Test upserting vectors to Qdrant."""
        from qdrant_client.models import PointStruct

        vectors = generate_random_vectors(10)
        points = [
            PointStruct(
                id=i,
                vector=vectors[i],
                payload={"text": f"Document {i}", "source": "test"},
            )
            for i in range(len(vectors))
        ]

        qdrant_client.upsert(
            collection_name=test_qdrant_collection,
            points=points,
        )

        # Verify points were inserted
        collection_info = qdrant_client.get_collection(test_qdrant_collection)
        assert collection_info.points_count == 10

    def test_search_vectors(self, qdrant_client, test_qdrant_collection):
        """Test searching vectors in Qdrant."""
        from qdrant_client.models import PointStruct

        # Insert test vectors
        vectors = generate_random_vectors(20)
        points = [
            PointStruct(
                id=i,
                vector=vectors[i],
                payload={"text": f"Document {i}", "category": "A" if i < 10 else "B"},
            )
            for i in range(len(vectors))
        ]

        qdrant_client.upsert(
            collection_name=test_qdrant_collection,
            points=points,
        )

        # Search
        query_vector = vectors[0]  # Search for similar to first vector
        results = qdrant_client.search(
            collection_name=test_qdrant_collection,
            query_vector=query_vector,
            limit=5,
        )

        assert len(results) == 5
        # First result should be the same vector (score ~1.0)
        assert results[0].id == 0
        assert results[0].score > 0.99

    def test_search_with_filter(self, qdrant_client, test_qdrant_collection):
        """Test searching with filters in Qdrant."""
        from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

        # Insert test vectors with categories
        vectors = generate_random_vectors(20)
        points = [
            PointStruct(
                id=i,
                vector=vectors[i],
                payload={"text": f"Document {i}", "category": "A" if i < 10 else "B"},
            )
            for i in range(len(vectors))
        ]

        qdrant_client.upsert(
            collection_name=test_qdrant_collection,
            points=points,
        )

        # Search with filter
        query_vector = generate_random_vector()
        results = qdrant_client.search(
            collection_name=test_qdrant_collection,
            query_vector=query_vector,
            query_filter=Filter(
                must=[FieldCondition(key="category", match=MatchValue(value="A"))]
            ),
            limit=10,
        )

        # All results should be from category A
        for result in results:
            assert result.payload["category"] == "A"

    def test_delete_vectors(self, qdrant_client, test_qdrant_collection):
        """Test deleting vectors from Qdrant."""
        from qdrant_client.models import PointStruct

        # Insert vectors
        vectors = generate_random_vectors(5)
        points = [
            PointStruct(id=i, vector=vectors[i], payload={"text": f"Doc {i}"})
            for i in range(len(vectors))
        ]

        qdrant_client.upsert(
            collection_name=test_qdrant_collection,
            points=points,
        )

        # Delete specific points
        qdrant_client.delete(
            collection_name=test_qdrant_collection,
            points_selector=[0, 1, 2],
        )

        # Verify deletion
        collection_info = qdrant_client.get_collection(test_qdrant_collection)
        assert collection_info.points_count == 2


class TestRedisVectorIntegration:
    """Test Redis vector search integration."""

    @pytest.mark.asyncio
    async def test_create_index(self, redis_client, clean_redis):
        """Test creating a Redis vector index."""
        from redis.commands.search.field import TextField, VectorField
        from redis.commands.search.indexDefinition import IndexDefinition, IndexType

        index_name = "test_vector_idx"

        try:
            # Define schema
            schema = (
                TextField("content"),
                VectorField(
                    "embedding",
                    "HNSW",
                    {"TYPE": "FLOAT32", "DIM": 1536, "DISTANCE_METRIC": "COSINE"},
                ),
            )

            # Create index
            await redis_client.ft(index_name).create_index(
                fields=schema,
                definition=IndexDefinition(prefix=["doc:"], index_type=IndexType.HASH),
            )

            # Verify index exists
            info = await redis_client.ft(index_name).info()
            assert info is not None
        except Exception as e:
            # Redis might not have search module
            if "unknown command" in str(e).lower():
                pytest.skip("Redis Search module not available")
            raise

    @pytest.mark.asyncio
    async def test_add_vectors(self, redis_client, clean_redis):
        """Test adding vectors to Redis."""
        import struct

        # Add documents with vectors
        for i in range(10):
            vector = generate_random_vector()
            vector_bytes = struct.pack(f"{len(vector)}f", *vector)

            await redis_client.hset(
                f"doc:{i}",
                mapping={
                    "content": f"Document {i}",
                    "embedding": vector_bytes,
                },
            )

        # Verify documents exist
        keys = await redis_client.keys("doc:*")
        assert len(keys) == 10

    @pytest.mark.asyncio
    async def test_vector_search(self, redis_client, clean_redis):
        """Test vector search in Redis."""
        # This test requires Redis Stack with RediSearch module
        pytest.skip("Requires Redis Stack with vector search capabilities")


class TestVectorDBErrorHandling:
    """Test error handling for vector database operations."""

    def test_qdrant_invalid_dimension(self, qdrant_client, test_qdrant_collection):
        """Test Qdrant with wrong vector dimension."""
        from qdrant_client.models import PointStruct

        # Collection expects 1536 dimensions, try with 768
        wrong_dim_vector = generate_random_vector(768)

        with pytest.raises(Exception) as exc:
            qdrant_client.upsert(
                collection_name=test_qdrant_collection,
                points=[
                    PointStruct(id=1, vector=wrong_dim_vector, payload={"text": "test"})
                ],
            )

        assert "dimension" in str(exc.value).lower() or "size" in str(exc.value).lower()
