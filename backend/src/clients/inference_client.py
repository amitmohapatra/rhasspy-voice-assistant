"""Async HTTP client for the inference service.

Used by the API container and Celery workers to call the
inference service for embeddings, reranking, and document processing.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Optional

import httpx

from src.rag.models import TripleEmbedding

logger = logging.getLogger(__name__)

# Module-level singleton with thread-safe initialization
_client: Optional["InferenceClient"] = None
_client_lock = threading.Lock()


class InferenceServiceError(Exception):
    """Raised when the inference service returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class InferenceClient:
    """Async HTTP client for the ML inference service."""

    def __init__(self, base_url: str, timeout: int = 300):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(timeout),
                write=30.0,
                pool=10.0,
            ),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
            ),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> dict:
        """Make a request to the inference service."""
        try:
            response = await self._client.request(method, path, **kwargs)
            if response.status_code >= 400:
                detail = response.text
                try:
                    detail = response.json().get("detail", detail)
                except Exception:
                    pass
                raise InferenceServiceError(
                    f"Inference service error: {detail}",
                    status_code=response.status_code,
                )
            return response.json()
        except httpx.ConnectError as e:
            raise InferenceServiceError(
                f"Cannot connect to inference service at {self.base_url}: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise InferenceServiceError(
                f"Inference service request timed out: {e}"
            ) from e

    # ========================================================================
    # Embeddings
    # ========================================================================

    async def embed_triple(
        self,
        texts: list[str],
        max_length: int = 1024,
        batch_size: int = 4,
    ) -> list[TripleEmbedding]:
        """Generate BGE-M3 triple embeddings via the inference service.

        Args:
            texts: Texts to embed.
            max_length: Maximum sequence length (1024 is sufficient for chunks).
            batch_size: Process texts in batches to avoid long single requests.

        Returns:
            List of TripleEmbedding instances.
        """
        if not texts:
            return []

        # Process in batches to avoid timeout on large chunk sets
        all_results = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            data = await self._request(
                "POST",
                "/embed-triple",
                json={"texts": batch, "max_length": max_length},
            )
            all_results.extend(data.get("embeddings", []))

        data = {"embeddings": all_results}

        return [
            TripleEmbedding(
                dense=emb["dense"],
                sparse={int(k): v for k, v in emb.get("sparse", {}).items()},
                colbert=emb.get("colbert"),
            )
            for emb in data["embeddings"]
        ]

    # ========================================================================
    # Reranking
    # ========================================================================

    async def rerank(
        self,
        query: str,
        documents: list[dict[str, str]],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Rerank documents via the inference service.

        Args:
            query: Search query.
            documents: List of {"id": ..., "content": ...} dicts.
            top_k: Number of results to return.

        Returns:
            List of {"id": ..., "content": ..., "score": ...} dicts, sorted by score.
        """
        if not documents:
            return []

        data = await self._request(
            "POST",
            "/rerank",
            json={
                "query": query,
                "documents": documents,
                "top_k": top_k,
            },
        )

        return data["documents"]

    # ========================================================================
    # Document Processing
    # ========================================================================

    async def process_document(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> dict[str, Any]:
        """Process a document via the inference service.

        Args:
            file_bytes: Raw file content.
            filename: Original filename (for extension detection).

        Returns:
            Dict with text, elements, tables, images, page_count, metadata.
        """
        return await self._request(
            "POST",
            "/process-document",
            files={"file": (filename, file_bytes)},
        )

    # ========================================================================
    # Late Chunking
    # ========================================================================

    async def embed_late_chunk(
        self,
        document_text: str,
        chunk_boundaries: list[tuple[int, int]],
        max_length: int = 8192,
    ) -> list[TripleEmbedding]:
        """Generate context-aware embeddings via late chunking.

        Args:
            document_text: Full document text.
            chunk_boundaries: List of (start_char, end_char) per chunk.
            max_length: Maximum sequence length.

        Returns:
            List of TripleEmbedding instances (one per chunk).
        """
        if not chunk_boundaries:
            return []

        data = await self._request(
            "POST",
            "/embed-late-chunk",
            json={
                "document_text": document_text,
                "chunk_boundaries": [list(b) for b in chunk_boundaries],
                "max_length": max_length,
            },
        )

        return [
            TripleEmbedding(
                dense=emb["dense"],
                sparse={int(k): v for k, v in emb.get("sparse", {}).items()},
                colbert=emb.get("colbert"),
            )
            for emb in data["embeddings"]
        ]

    # ========================================================================
    # Visual Embeddings (ColSmol-256M)
    # ========================================================================

    async def embed_visual(
        self,
        images_base64: list[str],
        batch_size: int = 2,
    ) -> list[list[list[float]]]:
        """Embed page images as multi-vectors via inference service.

        Returns: list of multi-vectors (one per image, each ~1030 x 128-dim).
        """
        all_results: list[list[list[float]]] = []
        for i in range(0, len(images_base64), batch_size):
            batch = images_base64[i:i + batch_size]
            data = await self._request(
                "POST", "/embed-visual",
                json={"images": batch},
            )
            all_results.extend(data.get("embeddings", []))
        return all_results

    async def embed_visual_query(self, query: str) -> list[list[float]]:
        """Embed text query as multi-vectors for visual page search.

        Returns: multi-vector (N tokens x 128-dim).
        """
        data = await self._request(
            "POST", "/embed-visual-query",
            json={"query": query},
        )
        return data.get("embedding", [])

    # ========================================================================
    # Health
    # ========================================================================

    async def health(self) -> dict[str, Any]:
        """Check inference service health.

        Returns:
            Dict with status, models_loaded, gpu_available, memory_usage_mb.
        """
        return await self._request("GET", "/health")


def get_inference_client() -> InferenceClient:
    """Get or create the module-level inference client singleton (thread-safe)."""
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:  # Double-check locking
                from src.core.config import settings

                _client = InferenceClient(
                    base_url=settings.inference_service_url,
                    timeout=settings.inference_service_timeout,
                )
    return _client


def reset_inference_client() -> None:
    """Reset the singleton so the next call creates a fresh client.

    Must be called from Celery tasks before ``asyncio.run()`` because
    each ``asyncio.run()`` creates a new event loop, and the old
    ``httpx.AsyncClient`` is bound to the previous (now-closed) loop.
    """
    global _client
    with _client_lock:
        _client = None
