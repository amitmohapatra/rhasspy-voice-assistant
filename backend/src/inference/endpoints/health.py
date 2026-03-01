"""Health check endpoint for inference service."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Request

from src.inference.schemas import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    """Check inference service health and model load status."""
    model_manager = request.app.state.model_manager

    # Check GPU availability
    gpu_available = False
    try:
        import torch
        gpu_available = torch.cuda.is_available()
    except ImportError:
        pass

    # Get memory usage
    memory_mb = 0.0
    try:
        import psutil
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / (1024 * 1024)
    except ImportError:
        pass

    models_loaded = model_manager.get_status()

    if model_manager.all_loaded:
        status = "healthy"
    else:
        # Check if any required models failed
        required = {"bge_m3", "reranker", "docling"}
        any_failed = any(
            name in models_loaded and not models_loaded[name]["loaded"]
            for name in required
        )
        status = "unhealthy" if any_failed else "loading"

    return HealthResponse(
        status=status,
        models_loaded=models_loaded,
        gpu_available=gpu_available,
        memory_usage_mb=round(memory_mb, 1),
    )
