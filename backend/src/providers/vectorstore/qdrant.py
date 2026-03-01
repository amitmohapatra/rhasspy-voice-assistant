"""Qdrant vector store provider.

Qdrant is a high-performance vector similarity search engine optimized for:
- Memory-mapped storage (reduces RAM usage)
- Scalar quantization (4x memory reduction)
- Horizontal scaling
- Production-ready deployments

This is the recommended vector store for the RAG system.
"""

from __future__ import annotations

import os
from typing import Any
import httpx
import uuid

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.vectorstore.base import (
    BaseVectorStoreProvider,
    VectorDocument,
    SearchResult,
)


@ProviderRegistry.register
class QdrantProvider(BaseVectorStoreProvider):
    """Qdrant vector database (recommended).

    Features:
    - Memory-mapped storage for large datasets
    - Scalar/binary quantization for 4x memory reduction
    - HNSW indexing for fast approximate search
    - Filtering with payload conditions
    - Horizontal scaling with sharding
    """

    provider_name = "qdrant"
    display_name = "Qdrant (Recommended)"
    description = "High-performance vector similarity search engine"
    requires_api_key = False  # Optional for cloud

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        # Use environment variable, then settings, then default
        self.url = config.settings.get(
            "url",
            os.environ.get("QDRANT_URL", "http://localhost:6333")
        )
        # API key from config or environment
        if not self.config.api_key:
            self.config.api_key = os.environ.get("QDRANT_API_KEY")

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["api-key"] = self.config.api_key
        return headers

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "qdrant-local",
                "name": "Qdrant Local",
                "description": "Self-hosted Qdrant instance",
            },
            {
                "id": "qdrant-cloud",
                "name": "Qdrant Cloud",
                "description": "Managed Qdrant service",
            },
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "default": "http://localhost:6333",
                    "description": "Qdrant instance URL",
                },
                "distance": {
                    "type": "string",
                    "enum": ["Cosine", "Euclid", "Dot"],
                    "default": "Cosine",
                    "description": "Distance metric",
                },
                "on_disk": {
                    "type": "boolean",
                    "default": False,
                    "description": "Store vectors on disk",
                },
                "hnsw_m": {
                    "type": "integer",
                    "default": 16,
                    "description": "HNSW M parameter",
                },
                "hnsw_ef_construct": {
                    "type": "integer",
                    "default": 100,
                    "description": "HNSW ef_construct parameter",
                },
            },
        }

    async def create_collection(
        self,
        name: str,
        dimensions: int,
        **kwargs,
    ) -> bool:
        """Create a Qdrant collection."""
        distance = kwargs.get("distance", "Cosine")
        on_disk = kwargs.get("on_disk", False)

        collection_config = {
            "vectors": {
                "size": dimensions,
                "distance": distance,
                "on_disk": on_disk,
            },
            "hnsw_config": {
                "m": kwargs.get("hnsw_m", 16),
                "ef_construct": kwargs.get("hnsw_ef_construct", 100),
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.url}/collections/{name}",
                headers=self._get_headers(),
                json=collection_config,
                timeout=30.0,
            )
            response.raise_for_status()

        return True

    async def delete_collection(self, name: str) -> bool:
        """Delete a Qdrant collection."""
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.url}/collections/{name}",
                headers=self._get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
        return True

    async def list_collections(self) -> list[str]:
        """List all Qdrant collections."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/collections",
                headers=self._get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        return [col["name"] for col in result.get("result", {}).get("collections", [])]

    async def upsert(
        self,
        collection: str,
        documents: list[VectorDocument],
        **kwargs,
    ) -> int:
        """Upsert points to Qdrant."""
        points = []
        for doc in documents:
            # Convert string ID to UUID if needed
            try:
                point_id = str(uuid.UUID(doc.id))
            except ValueError:
                # Generate deterministic UUID from string
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc.id))

            points.append({
                "id": point_id,
                "vector": doc.embedding,
                "payload": {
                    "content": doc.content,
                    "original_id": doc.id,
                    **doc.metadata,
                },
            })

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.url}/collections/{collection}/points",
                headers=self._get_headers(),
                json={"points": points},
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        return len(points) if result.get("status") == "ok" else 0

    async def delete(
        self,
        collection: str,
        ids: list[str],
        **kwargs,
    ) -> int:
        """Delete points by ID."""
        # Convert string IDs to UUIDs
        point_ids = []
        for id_str in ids:
            try:
                point_ids.append(str(uuid.UUID(id_str)))
            except ValueError:
                point_ids.append(str(uuid.uuid5(uuid.NAMESPACE_DNS, id_str)))

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/collections/{collection}/points/delete",
                headers=self._get_headers(),
                json={"points": point_ids},
                timeout=30.0,
            )
            response.raise_for_status()

        return len(ids)

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 10,
        **kwargs,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        search_params = {
            "vector": query_embedding,
            "limit": top_k,
            "with_payload": True,
        }

        # Add filter if provided
        if "filter" in kwargs:
            filter_conditions = []
            for key, value in kwargs["filter"].items():
                filter_conditions.append({
                    "key": key,
                    "match": {"value": value},
                })
            search_params["filter"] = {"must": filter_conditions}

        # Score threshold
        if "score_threshold" in kwargs:
            search_params["score_threshold"] = kwargs["score_threshold"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.url}/collections/{collection}/points/search",
                headers=self._get_headers(),
                json=search_params,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        results = []
        for hit in result.get("result", []):
            payload = hit.get("payload", {})
            content = payload.pop("content", "")
            original_id = payload.pop("original_id", hit["id"])

            results.append(
                SearchResult(
                    id=str(original_id),
                    content=content,
                    score=hit["score"],
                    metadata=payload,
                )
            )

        return results

    async def get_collection_stats(self, collection: str) -> dict[str, Any]:
        """Get collection info."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.url}/collections/{collection}",
                headers=self._get_headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        info = result.get("result", {})
        vectors_config = info.get("config", {}).get("params", {}).get("vectors", {})

        return {
            "count": info.get("points_count", 0),
            "dimensions": vectors_config.get("size"),
            "distance": vectors_config.get("distance"),
            "status": info.get("status"),
            "indexed_vectors_count": info.get("indexed_vectors_count", 0),
        }
