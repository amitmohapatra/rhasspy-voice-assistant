"""Knowledge Base routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.api.deps import DbSession, CurrentUser
from src.core.exceptions import NotFoundError, ValidationError
from src.models.knowledge_base import KnowledgeBase
from src.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseSummary,
    DocumentResponse,
)
from src.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter()


def _doc_to_response(doc) -> DocumentResponse:
    """Convert a Document model to DocumentResponse."""
    kbs = []
    if hasattr(doc, "knowledge_bases") and doc.knowledge_bases:
        kbs = [KnowledgeBaseSummary(id=kb.id, name=kb.name) for kb in doc.knowledge_bases]
    return DocumentResponse(
        id=doc.id,
        knowledge_base_id=kbs[0].id if kbs else None,
        knowledge_bases=kbs,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        status=doc.status,
        error_message=doc.error_message,
        chunk_count=doc.chunk_count,
        structured_json_path=doc.structured_json_path,
        page_count=doc.page_count,
        language=doc.language,
        metadata=doc.meta_data,
        created_at=doc.created_at,
    )


def _kb_to_response(kb, stats: dict, documents: list | None = None) -> KnowledgeBaseResponse:
    """Convert a KnowledgeBase model to response schema."""
    return KnowledgeBaseResponse(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        settings=kb.settings,
        status=kb.status,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        documents=documents or [],
        document_count=stats.get("document_count", 0),
        total_chunks=stats.get("chunk_count", 0),
        kb_type=kb.kb_type,
        provider_id=kb.provider_id,
        provider_kb_ref=kb.provider_kb_ref,
        provider_config=kb.provider_config,
        pipeline_info=KnowledgeBase.get_pipeline_info(),
    )


@router.post("", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    """Create a new knowledge base."""
    service = KnowledgeBaseService(db)
    kb = await service.create_knowledge_base(data, user_id=current_user.id)

    return _kb_to_response(kb, {"document_count": 0, "chunk_count": 0})


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    search: str | None = Query(None, description="Search by name or description"),
    kb_type: str | None = Query(None, description="Filter by type: platform_managed or provider_managed"),
) -> KnowledgeBaseListResponse:
    """List knowledge bases."""
    service = KnowledgeBaseService(db)
    knowledge_bases, total = await service.list_knowledge_bases(
        skip=skip,
        limit=limit,
        search=search,
        kb_type=kb_type,
        user_id=current_user.id,
    )

    items = []
    for kb in knowledge_bases:
        stats = await service.get_knowledge_base_stats(kb.id)
        items.append(_kb_to_response(kb, stats))

    page = (skip // limit) + 1 if limit > 0 else 1
    return KnowledgeBaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=limit,
        has_more=(skip + limit) < total,
    )


@router.get("/{kb_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    kb_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    """Get a knowledge base by ID."""
    try:
        service = KnowledgeBaseService(db)
        kb = await service.get_knowledge_base(kb_id)
        stats = await service.get_knowledge_base_stats(kb_id)

        documents = await service.list_documents(kb_id=kb_id)
        doc_responses = [
            _doc_to_response(d) for d in documents
        ]

        return _kb_to_response(kb, stats, doc_responses)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.put("/{kb_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    kb_id: UUID,
    data: KnowledgeBaseUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> KnowledgeBaseResponse:
    """Update a knowledge base."""
    try:
        service = KnowledgeBaseService(db)
        kb = await service.update_knowledge_base(
            kb_id, data
        )
        stats = await service.get_knowledge_base_stats(kb_id)

        return _kb_to_response(kb, stats)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a knowledge base."""
    try:
        service = KnowledgeBaseService(db)
        await service.delete_knowledge_base(kb_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# Document endpoints
@router.get("/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
) -> list[DocumentResponse]:
    """List documents in a knowledge base."""
    try:
        service = KnowledgeBaseService(db)
        documents = await service.list_documents(
            kb_id=kb_id,
            skip=skip,
            limit=limit,
        )
        return [_doc_to_response(d) for d in documents]
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/{kb_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: UUID,
    document_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a document."""
    try:
        service = KnowledgeBaseService(db)
        await service.delete_document(document_id)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
