"""RAG Pipeline info and connection testing endpoints.

The RAG pipeline is fully automated - no user configuration needed.
These endpoints provide pipeline information and connection testing.
"""

from __future__ import annotations

import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field

from src.rag.pipeline_config import (
    RestApiConfig,
    SecretReference,
    get_pipeline_info,
)
from src.rag.universal_rest_client import UniversalRestClient, test_rest_api
from src.rag.secret_resolver import SecretResolver

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class PipelineInfoResponse(BaseModel):
    """Information about the fixed RAG pipeline."""
    pipeline: dict
    message: str = "RAG pipeline is fully automated. No configuration needed."


class TestRestApiRequest(BaseModel):
    """Request to test a REST API configuration."""
    config: dict  # RestApiConfig as dict


class TestRestApiResponse(BaseModel):
    """Response from REST API test."""
    success: bool
    message: str
    status_code: Optional[int] = None
    output_preview: Optional[str] = None


class TestConnectionRequest(BaseModel):
    """Request to test a connection (vector store or redis)."""
    connection_type: str  # qdrant, redis
    config: dict


class TestConnectionResponse(BaseModel):
    """Response from connection test."""
    success: bool
    message: str
    details: Optional[dict] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.get(
    "",
    response_model=PipelineInfoResponse,
    summary="Get RAG pipeline info",
    description="Get information about the fixed RAG pipeline. All components are automated.",
)
async def get_pipeline_info_endpoint() -> PipelineInfoResponse:
    """Get the fixed pipeline information."""
    return PipelineInfoResponse(pipeline=get_pipeline_info())


@router.post(
    "/test-rest-api",
    response_model=TestRestApiResponse,
    summary="Test REST API configuration",
    description="Test a REST API configuration before saving.",
)
async def test_rest_api_endpoint(
    request: TestRestApiRequest,
) -> TestRestApiResponse:
    """Test a REST API configuration."""
    try:
        config = RestApiConfig.model_validate(request.config)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid REST API configuration: {str(e)}",
        )

    result = await test_rest_api(config)

    return TestRestApiResponse(
        success=result["success"],
        message=result["message"],
        status_code=result.get("status_code"),
        output_preview=result.get("output_preview"),
    )


@router.post(
    "/test-connection",
    response_model=TestConnectionResponse,
    summary="Test connection",
    description="Test a database/service connection (vector store, Redis, etc).",
)
async def test_connection_endpoint(
    request: TestConnectionRequest,
) -> TestConnectionResponse:
    """Test a connection configuration."""
    connection_type = request.connection_type.lower()
    config = request.config

    try:
        match connection_type:
            case "qdrant":
                return await _test_qdrant(config)
            case "redis":
                return await _test_redis(config)
            case _:
                return TestConnectionResponse(
                    success=False,
                    message=f"Unknown connection type: {connection_type}. Supported: qdrant, redis",
                )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection test failed: {str(e)}",
        )


async def _test_qdrant(config: dict) -> TestConnectionResponse:
    """Test Qdrant connection."""
    from qdrant_client import QdrantClient

    api_key = config.get("api_key")
    if isinstance(api_key, dict):
        resolver = SecretResolver()
        api_key = await resolver.resolve(SecretReference(**api_key))

    try:
        client = QdrantClient(
            url=config.get("url"),
            api_key=api_key,
            prefer_grpc=config.get("prefer_grpc", False),
        )
        collections = client.get_collections()
        return TestConnectionResponse(
            success=True,
            message="Qdrant connection successful",
            details={
                "url": config.get("url"),
                "collections_count": len(collections.collections),
            },
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Qdrant connection failed: {str(e)}",
        )


async def _test_redis(config: dict) -> TestConnectionResponse:
    """Test Redis connection."""
    import redis.asyncio as redis

    password = config.get("password")
    if isinstance(password, dict):
        resolver = SecretResolver()
        password = await resolver.resolve(SecretReference(**password))

    try:
        url = config.get("url", "redis://localhost:6379")
        client = redis.from_url(
            url,
            password=password,
            ssl=config.get("use_ssl", False),
        )
        await client.ping()
        await client.close()
        return TestConnectionResponse(
            success=True,
            message="Redis connection successful",
            details={"url": url},
        )
    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Redis connection failed: {str(e)}",
        )


@router.post(
    "/test",
    summary="Test pipeline end-to-end",
    description="Test the fixed RAG pipeline with a sample document and query.",
)
async def test_pipeline(
    file: UploadFile = File(..., description="Test document"),
    query: str = Form(..., description="Test query"),
) -> dict:
    """Test the pipeline end-to-end with sample input."""
    import time

    start = time.time()
    timings = {}

    try:
        content = await file.read()

        # 1. Parse document via inference service
        parse_start = time.time()
        from src.rag.document_processor.format_router import FormatRouter
        from src.clients.inference_client import get_inference_client as _get_client
        from src.rag.models import DocumentStructure

        route = FormatRouter.get_route(file.filename or "test.txt")
        document_structure = None
        text = ""

        if route == "docling":
            client = _get_client()
            processed = await client.process_document(content, file.filename or "test.txt")
            text = processed["text"]
            elements = processed.get("elements", [])
            if elements:
                document_structure = DocumentStructure(elements=elements, metadata=processed.get("metadata", {}))
        else:
            text = content.decode("utf-8", errors="replace")

        timings["parse_ms"] = (time.time() - parse_start) * 1000

        # 2. Chunk with DoclingHybridChunker
        chunk_start = time.time()
        from src.rag.base import RAGConfig, Chunk as RAGChunk
        from src.rag.chunking.docling_hybrid import DoclingHybridChunker

        config = RAGConfig()
        chunker = DoclingHybridChunker(config)

        if document_structure:
            chunks = chunker.chunk_structured(
                structure=document_structure,
                document_id="test",
                base_metadata={},
            )
        else:
            raw_chunks = chunker.chunk(text, {})
            chunks = [
                RAGChunk(
                    id=RAGChunk.generate_id("test", i, c.content),
                    document_id="test",
                    content=c.content,
                    metadata=c.metadata,
                    chunk_index=i,
                )
                for i, c in enumerate(raw_chunks)
            ]

        timings["chunk_ms"] = (time.time() - chunk_start) * 1000

        # 3. Embed with BGE-M3 via inference service
        embed_start = time.time()
        from src.clients.inference_client import get_inference_client

        inference_client = get_inference_client()

        chunk_texts = [c.content for c in chunks]
        triples = await inference_client.embed_triple(chunk_texts)

        embedded_chunks = [c.with_embedding(t) for c, t in zip(chunks, triples)]
        query_triples = await inference_client.embed_triple([query])
        query_triple = query_triples[0]

        timings["embed_ms"] = (time.time() - embed_start) * 1000

        # 4. Store in temp Qdrant collection
        store_start = time.time()
        from src.rag.vectorstores.qdrant import QdrantStore
        from src.core.config import settings as app_settings

        temp_collection = f"test_{uuid.uuid4().hex[:8]}"
        qdrant = QdrantStore(
            config=config,
            url=app_settings.qdrant_url,
            api_key=app_settings.qdrant_api_key or None,
            collection_name=temp_collection,
        )
        await qdrant.initialize()
        await qdrant.add(embedded_chunks)

        timings["store_ms"] = (time.time() - store_start) * 1000

        # 5. Query
        retrieve_start = time.time()
        search_results = await qdrant.search(query_triple, top_k=config.top_k)
        timings["retrieve_ms"] = (time.time() - retrieve_start) * 1000

        # 6. Rerank via inference service
        rerank_start = time.time()
        from src.rag.factory import RemoteReranker
        reranker = RemoteReranker(config=config)
        reranked = await reranker.rerank(query, search_results, config.top_n)
        timings["rerank_ms"] = (time.time() - rerank_start) * 1000

        # 7. Cleanup
        try:
            await qdrant.close()
            from qdrant_client import QdrantClient
            client = QdrantClient(
                url=app_settings.qdrant_url,
                api_key=app_settings.qdrant_api_key or None,
            )
            client.delete_collection(temp_collection)
        except Exception:
            pass

        total_time = (time.time() - start) * 1000

        return {
            "success": True,
            "document_name": file.filename,
            "query": query,
            "chunks_created": len(chunks),
            "results": [
                {
                    "content": r.chunk.content[:500],
                    "score": round(r.score, 4),
                    "element_type": r.chunk.element_type,
                    "page_number": r.chunk.page_number,
                }
                for r in reranked
            ],
            "timings": {
                **{k: round(v, 1) for k, v in timings.items()},
                "total_ms": round(total_time, 1),
            },
            "pipeline": get_pipeline_info(),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "document_name": file.filename,
            "query": query,
            "timings": {
                **{k: round(v, 1) for k, v in timings.items()},
                "total_ms": round((time.time() - start) * 1000, 1),
            },
        }
