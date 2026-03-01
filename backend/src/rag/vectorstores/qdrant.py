"""Qdrant vector database backend with named vectors.

Uses named vectors for dense (1024d COSINE) and sparse (IDF-weighted)
storage. Dense+sparse search results are fused via RRF internally.

Features:
- Named vectors: "dense" + "sparse"
- Payload indexes on document_id, element_type, page_number
- RRF fusion of dense and sparse search results
"""

from __future__ import annotations

import uuid
from typing import Optional
import logging

from src.rag.base import (
    BaseVectorStore,
    Chunk,
    SearchResult,
    RAGConfig,
    normalize_score,
    reciprocal_rank_fusion,
)
from src.rag.models import TripleEmbedding

logger = logging.getLogger(__name__)


class QdrantStore(BaseVectorStore):
    """Qdrant vector database with named vectors (dense + sparse).

    Collection schema:
    - Named vector "dense": VectorParams(size=1024, distance=COSINE)
    - Named vector "sparse": SparseVectorParams(modifier=IDF)
    - Payload: document_id, user_id, content, chunk_index, page_number, element_type, bbox, parent_chunk_id, parent_content
    - Payload indexes: document_id (keyword), user_id (keyword), element_type (keyword), page_number (integer)
    """

    def __init__(
        self,
        config: RAGConfig,
        url: str = "http://localhost:6333",
        collection_name: str = "chunks",
        api_key: Optional[str] = None,
        prefer_grpc: bool = True,
        on_disk: bool = False,
    ):
        super().__init__(config, collection_name=collection_name)
        self.url = url
        self.api_key = api_key
        self.prefer_grpc = prefer_grpc
        self.on_disk = on_disk
        self._client = None

    async def initialize(self) -> None:
        """Initialize connection and create collection with named vectors."""
        try:
            from qdrant_client import QdrantClient, models
        except ImportError:
            raise ImportError(
                "qdrant-client is required for QdrantStore. "
                "Install with: pip install qdrant-client"
            )

        self._client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            prefer_grpc=self.prefer_grpc,
            timeout=300,
        )

        collections = self._client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)

        if not exists:
            self._client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(
                        size=1024,
                        distance=models.Distance.COSINE,
                        on_disk=self.on_disk,
                    ),
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    ),
                },
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=20000,
                ),
                hnsw_config=models.HnswConfigDiff(
                    m=16,
                    ef_construct=100,
                    full_scan_threshold=10000,
                    on_disk=self.on_disk,
                ),
            )

            # Create payload indexes
            for field_name, schema_type in [
                ("document_id", models.PayloadSchemaType.KEYWORD),
                ("user_id", models.PayloadSchemaType.KEYWORD),
                ("element_type", models.PayloadSchemaType.KEYWORD),
                ("page_number", models.PayloadSchemaType.INTEGER),
                ("element_id", models.PayloadSchemaType.KEYWORD),
                ("confidence", models.PayloadSchemaType.FLOAT),
            ]:
                self._client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )

    async def add(self, chunks: list[Chunk]) -> None:
        """Add chunks with TripleEmbedding to the store.

        Stores dense vector in named "dense" vector, sparse in "sparse".
        """
        if not chunks:
            return

        from qdrant_client import models

        points = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue

            triple = chunk.embedding
            point_id = self._ensure_uuid(chunk.id)

            # Build named vectors
            vectors: dict = {
                "dense": triple.dense,
            }

            # Build sparse vector
            sparse_vector = None
            if triple.sparse:
                indices = list(triple.sparse.keys())
                values = list(triple.sparse.values())
                if indices:
                    sparse_vector = models.SparseVector(
                        indices=indices,
                        values=values,
                    )

            # Build payload
            payload = {
                "document_id": chunk.document_id,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "element_type": chunk.element_type,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "original_id": chunk.id,
                **chunk.metadata,
            }

            if chunk.bbox:
                payload["bbox"] = chunk.bbox

            # v2 enriched fields
            if chunk.metadata.get("element_id"):
                payload["element_id"] = chunk.metadata["element_id"]
            if chunk.metadata.get("label"):
                payload["label"] = chunk.metadata["label"]
            if chunk.metadata.get("charspan"):
                payload["charspan"] = chunk.metadata["charspan"]
            if chunk.metadata.get("confidence") is not None:
                payload["confidence"] = chunk.metadata["confidence"]

            # Store parent-child data for parent-child retrieval
            if chunk.parent_chunk_id:
                payload["parent_chunk_id"] = chunk.parent_chunk_id
            if chunk.parent_content:
                payload["parent_content"] = chunk.parent_content

            point = models.PointStruct(
                id=point_id,
                vector={
                    "dense": triple.dense,
                    **({"sparse": sparse_vector} if sparse_vector else {}),
                },
                payload=payload,
            )
            points.append(point)

        if not points:
            return

        # Batch upsert
        batch_size = 50
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self._client.upsert(
                collection_name=self.collection_name,
                points=batch,
                wait=True,
            )

    async def search(
        self,
        query_embedding: TripleEmbedding | list[float],
        top_k: int = 10,
        filter_metadata: Optional[dict] = None,
        score_threshold: Optional[float] = None,
    ) -> list[SearchResult]:
        """Search using dense + sparse with RRF fusion.

        If query_embedding is a TripleEmbedding, runs both dense and sparse
        searches and fuses results. Otherwise, runs dense search only.
        """
        from qdrant_client import models

        qdrant_filter = self._build_filter(filter_metadata)

        # Determine embedding type
        if isinstance(query_embedding, TripleEmbedding):
            triple = query_embedding
        else:
            triple = TripleEmbedding(dense=query_embedding)

        result_lists = []

        # Dense search
        dense_results = self._client.query_points(
            collection_name=self.collection_name,
            query=triple.dense,
            using="dense",
            query_filter=qdrant_filter,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        )
        result_lists.append(self._convert_results(dense_results.points, "dense"))

        # Sparse search (if sparse weights available)
        if triple.sparse:
            indices = list(triple.sparse.keys())
            values = list(triple.sparse.values())
            if indices:
                sparse_query = models.SparseVector(indices=indices, values=values)
                sparse_results = self._client.query_points(
                    collection_name=self.collection_name,
                    query=sparse_query,
                    using="sparse",
                    query_filter=qdrant_filter,
                    limit=top_k,
                    with_payload=True,
                )
                result_lists.append(self._convert_results(sparse_results.points, "sparse"))

        # Fuse results via RRF if multiple result lists
        if len(result_lists) > 1:
            weights = [0.6, 0.4]  # dense weighted higher
            fused = reciprocal_rank_fusion(result_lists, weights=weights)
            return fused[:top_k]
        elif result_lists:
            return result_lists[0][:top_k]
        else:
            return []

    def _convert_results(self, points, method: str) -> list[SearchResult]:
        """Convert Qdrant points to SearchResult list."""
        results = []
        for i, hit in enumerate(points):
            payload = hit.payload or {}
            original_id = payload.get("original_id", str(hit.id))

            chunk = Chunk(
                id=original_id,
                document_id=payload.get("document_id", ""),
                content=payload.get("content", ""),
                metadata={
                    k: v for k, v in payload.items()
                    if k not in (
                        "document_id", "content", "chunk_index", "start_char",
                        "end_char", "original_id", "page_number", "element_type",
                        "bbox", "user_id",
                        "parent_chunk_id", "parent_content",
                    )
                },
                chunk_index=payload.get("chunk_index", 0),
                start_char=payload.get("start_char", 0),
                end_char=payload.get("end_char", 0),
                page_number=payload.get("page_number", 0),
                element_type=payload.get("element_type", "text"),
                bbox=payload.get("bbox"),
                parent_chunk_id=payload.get("parent_chunk_id"),
                parent_content=payload.get("parent_content"),
            )

            results.append(SearchResult(
                chunk=chunk,
                score=normalize_score(hit.score) if hit.score is not None else 0.0,
                rank=i + 1,
                retrieval_method=method,
            ))

        return results

    def _build_filter(self, filter_metadata: Optional[dict]):
        """Build Qdrant filter from metadata dict."""
        if not filter_metadata:
            return None

        from qdrant_client import models

        conditions = []
        for key, value in filter_metadata.items():
            if isinstance(value, list):
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchAny(any=value),
                    )
                )
            else:
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                )

        return models.Filter(must=conditions)

    def _ensure_uuid(self, id_str: str) -> str:
        """Convert any string ID to a valid UUID."""
        try:
            uuid.UUID(id_str)
            return id_str
        except ValueError:
            namespace = uuid.NAMESPACE_DNS
            return str(uuid.uuid5(namespace, id_str))

    async def delete(self, chunk_ids: list[str]) -> None:
        """Delete chunks by ID."""
        if not chunk_ids:
            return

        from qdrant_client import models

        uuid_ids = [self._ensure_uuid(id_str) for id_str in chunk_ids]
        self._client.delete(
            collection_name=self.collection_name,
            points_selector=models.PointIdsList(points=uuid_ids),
            wait=True,
        )

    async def delete_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        from qdrant_client import models

        count_before = await self.count({"document_id": document_id})

        self._client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
            wait=True,
        )

        return count_before

    async def count(self, filter_metadata: Optional[dict] = None) -> int:
        """Count chunks."""
        from qdrant_client import models

        if filter_metadata:
            conditions = [
                models.FieldCondition(
                    key=key,
                    match=models.MatchValue(value=value),
                )
                for key, value in filter_metadata.items()
            ]
            result = self._client.count(
                collection_name=self.collection_name,
                count_filter=models.Filter(must=conditions),
                exact=True,
            )
        else:
            result = self._client.count(
                collection_name=self.collection_name,
                exact=True,
            )

        return result.count

    async def close(self) -> None:
        """Close client connection."""
        if self._client:
            self._client.close()
            self._client = None

    # ========================================================================
    # Page Images (ColSmol-256M visual retrieval)
    # ========================================================================

    async def initialize_page_images(self) -> None:
        """Create the page_images collection with multi-vector config (MaxSim)."""
        from qdrant_client import models

        if not self._client:
            return

        collection_name = "page_images"
        collections = self._client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)

        if not exists:
            self._client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "visual": models.VectorParams(
                        size=128,
                        distance=models.Distance.COSINE,
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM,
                        ),
                    ),
                },
                optimizers_config=models.OptimizersConfigDiff(
                    indexing_threshold=20000,
                ),
            )

            for field_name, schema_type in [
                ("document_id", models.PayloadSchemaType.KEYWORD),
                ("user_id", models.PayloadSchemaType.KEYWORD),
                ("page_number", models.PayloadSchemaType.INTEGER),
            ]:
                self._client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=schema_type,
                )
            logger.info("Created page_images collection with MaxSim multi-vector config")

    async def add_page_images(
        self,
        document_id: str,
        user_id: str,
        page_embeddings: list[list[list[float]]],
        page_texts: list[str],
        page_numbers: list[int],
    ) -> None:
        """Store page image multi-vector embeddings in Qdrant.

        Each page is stored as a point with its multi-vector embedding
        (~1030 patches x 128-dim) and payload containing page text.
        """
        from qdrant_client import models

        if not self._client or not page_embeddings:
            return

        points = []
        for embedding, text, page_num in zip(
            page_embeddings, page_texts, page_numbers
        ):
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}_page_{page_num}"))
            points.append(models.PointStruct(
                id=point_id,
                vector={"visual": embedding},
                payload={
                    "document_id": document_id,
                    "user_id": user_id,
                    "page_number": page_num,
                    "page_text": text,
                },
            ))

        batch_size = 10
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self._client.upsert(
                collection_name="page_images",
                points=batch,
                wait=True,
            )

        logger.info(
            "Added %d page images for document %s to Qdrant", len(points), document_id
        )

    async def search_page_images(
        self,
        query_embedding: list[list[float]],
        top_k: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> list[SearchResult]:
        """Search page images using MaxSim multi-vector similarity.

        Returns SearchResult objects where content = page_text from payload.
        """
        from qdrant_client import models

        if not self._client:
            return []

        qdrant_filter = self._build_filter(filter_metadata)

        results = self._client.query_points(
            collection_name="page_images",
            query=query_embedding,
            using="visual",
            query_filter=qdrant_filter,
            limit=top_k,
            with_payload=True,
        )

        search_results = []
        for i, hit in enumerate(results.points):
            payload = hit.payload or {}
            chunk = Chunk(
                id=str(hit.id),
                document_id=payload.get("document_id", ""),
                content=payload.get("page_text", ""),
                page_number=payload.get("page_number", 0),
                element_type="page",
            )
            search_results.append(SearchResult(
                chunk=chunk,
                score=normalize_score(hit.score) if hit.score is not None else 0.0,
                rank=i + 1,
                retrieval_method="visual",
            ))

        return search_results

    async def delete_page_images_by_document(self, document_id: str) -> None:
        """Delete all page image points for a document."""
        from qdrant_client import models

        if not self._client:
            return

        try:
            self._client.delete(
                collection_name="page_images",
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except Exception as e:
            logger.warning("Failed to delete page images for %s: %s", document_id, e)

    async def health_check(self) -> bool:
        """Check if Qdrant is reachable."""
        if not self._client:
            return False
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False


