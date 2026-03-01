"""Inference service FastAPI application.

Dedicated ML inference service with model preloading via lifespan.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.inference.config import inference_settings
from src.inference.model_manager import ModelManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load all ML models on startup, clean up on shutdown."""
    logging.basicConfig(level=getattr(logging, inference_settings.log_level.upper()))

    logger.info("Starting inference service...")
    logger.info("Device: %s", inference_settings.device)
    logger.info(
        "Loading 4 models: BGE-M3, reranker, "
        "Docling (RapidOCR PP-OCRv5 + PP-DocBee VLM), img2table"
    )

    # Load all models
    manager = ModelManager(inference_settings)
    app.state.model_manager = manager

    try:
        await manager.load_all()
    except Exception:
        logger.exception("Failed to load critical models — inference service cannot start")
        raise
    logger.info("Inference service ready")

    yield

    logger.info("Shutting down inference service")


app = FastAPI(
    title="Rhasspy Inference Service",
    description="ML model inference service for embeddings, reranking, and document processing",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routes
from src.inference.endpoints.embed import router as embed_router
from src.inference.endpoints.rerank import router as rerank_router
from src.inference.endpoints.document import router as document_router
from src.inference.endpoints.health import router as health_router

app.include_router(embed_router)
app.include_router(rerank_router)
app.include_router(document_router)
app.include_router(health_router)
