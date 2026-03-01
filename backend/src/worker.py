"""Celery worker configuration for background tasks.

Includes task routing for:
- Embedding generation
- Document processing
- LLM operations

Task queues:
- embedding: Vector embedding generation
- document: Document processing and extraction
- llm: LLM chat and completion tasks
- default: General tasks
"""

from celery import Celery

from src.core.config import settings

# Create Celery app
celery_app = Celery(
    "rhasspy",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 60 minutes (PDF: Docling ~10min + enrichment ~5min + embedding ~15min on CPU)
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    worker_concurrency=settings.ml_process_pool_workers,
    result_expires=3600,  # 1 hour
    task_routes={
        # Embedding tasks
        "src.tasks.embedding.*": {"queue": "embedding"},
        "embedding.*": {"queue": "embedding"},
        # Document processing
        "src.tasks.document.*": {"queue": "document"},
        "document.*": {"queue": "document"},
        # LLM operations
        "src.tasks.llm.*": {"queue": "llm"},
        "llm.*": {"queue": "llm"},
    },
    # Queue priorities
    task_default_queue="default",
    task_queues={
        "embedding": {"exchange": "embedding", "routing_key": "embedding"},
        "document": {"exchange": "document", "routing_key": "document"},
        "llm": {"exchange": "llm", "routing_key": "llm"},
        "default": {"exchange": "default", "routing_key": "default"},
    },
    # Task rate limits to prevent overload
    task_annotations={
        "embedding.*": {"rate_limit": "100/m"},
    },
)


# Auto-discover tasks
celery_app.autodiscover_tasks(["src.tasks"])
