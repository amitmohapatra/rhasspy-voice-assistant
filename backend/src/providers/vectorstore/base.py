"""Base vector store provider class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any
from pydantic import BaseModel

from src.providers.base import BaseProvider, ProviderType


class VectorDocument(BaseModel):
    """Document to store in vector database."""
    id: str
    content: str
    embedding: list[float]
    metadata: dict[str, Any] = {}


class SearchResult(BaseModel):
    """Search result from vector store."""
    id: str
    content: str
    score: float
    metadata: dict[str, Any] = {}


class BaseVectorStoreProvider(BaseProvider[SearchResult]):
    """Base class for vector store providers."""

    provider_type = ProviderType.VECTORSTORE

    @abstractmethod
    async def create_collection(
        self,
        name: str,
        dimensions: int,
        **kwargs,
    ) -> bool:
        """Create a new collection/index.

        Args:
            name: Collection name
            dimensions: Vector dimensions
            **kwargs: Provider-specific options

        Returns:
            True if created successfully
        """
        pass

    @abstractmethod
    async def delete_collection(self, name: str) -> bool:
        """Delete a collection/index.

        Args:
            name: Collection name

        Returns:
            True if deleted successfully
        """
        pass

    @abstractmethod
    async def list_collections(self) -> list[str]:
        """List all collections.

        Returns:
            List of collection names
        """
        pass

    @abstractmethod
    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs,
    ) -> int:
        """Insert or update documents.

        Args:
            collection: Collection name
            documents: Documents to upsert
            **kwargs: Provider-specific options

        Returns:
            Number of documents upserted
        """
        pass

    @abstractmethod
    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs,
    ) -> int:
        """Delete documents by ID.

        Args:
            collection: Collection name
            ids: Document IDs to delete
            **kwargs: Provider-specific options

        Returns:
            Number of documents deleted
        """
        pass

    @abstractmethod
    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        **kwargs,
    ) -> list[SearchResult]:
        """Search for similar documents.

        Args:
            collection: Collection name
            query_embedding: Query vector
            top_k: Number of results to return
            **kwargs: Provider-specific options (filters, etc.)

        Returns:
            List of search results
        """
        pass

    async def search_by_text(
        self,
        collection: str,
        query: str,
        embedding_fn: callable,
        top_k: int = 10,
        **kwargs,
    ) -> list[SearchResult]:
        """Search using text query (requires embedding function).

        Args:
            collection: Collection name
            query: Text query
            embedding_fn: Function to generate embeddings
            top_k: Number of results
            **kwargs: Additional options

        Returns:
            List of search results
        """
        query_embedding = await embedding_fn(query)
        return await self.search(collection, query_embedding, top_k, **kwargs)

    @abstractmethod
    async def get_collection_stats(self, collection: str) -> dict[str, Any]:
        """Get collection statistics.

        Args:
            collection: Collection name

        Returns:
            Dictionary with stats (count, dimensions, etc.)
        """
        pass
