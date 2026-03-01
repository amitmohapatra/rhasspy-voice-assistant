"""Background tasks."""

from src.tasks.document_tasks import process_document
from src.tasks.embedding_tasks import generate_embeddings

__all__ = ["process_document", "generate_embeddings"]
