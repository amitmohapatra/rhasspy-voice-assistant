"""File management routes — list, upload, assign, and manage documents.

Documents are decoupled from knowledge bases. Files can be uploaded
independently and later assigned to one or more KBs.
"""

import logging
import mimetypes
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.core.config import settings
from src.core.exceptions import NotFoundError, ValidationError
from src.models.knowledge_base import Document, KnowledgeBase, KnowledgeBaseDocument
from src.models.user import User
from src.schemas.knowledge_base import DocumentResponse, KnowledgeBaseSummary
from src.services.knowledge_base_service import KnowledgeBaseService

logger = logging.getLogger(__name__)


def _dispatch_processing(document_id: str) -> None:
    """Dispatch document processing task to Celery (fire-and-forget).

    Fails silently if the Celery broker is unavailable — the document
    stays in 'pending' status and can be reprocessed later.
    """
    try:
        from src.tasks.document_tasks import process_document as task
        task.delay(document_id)
    except Exception as e:
        logger.warning("Failed to dispatch document processing for %s: %s", document_id, e)

router = APIRouter()

# Allowed file types and their MIME types
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".json": "application/json",
    ".csv": "text/csv",
    ".epub": "application/epub+zip",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".tex": "application/x-latex",
    ".rtf": "application/rtf",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


# =============================================================================
# Response schemas for file listing
# =============================================================================


class KBInfo(BaseModel):
    """Minimal KB info for file listing."""
    id: UUID
    name: str


class FileItem(BaseModel):
    """A single file/document in the listing."""
    id: UUID
    filename: str
    file_type: str
    file_size: int
    file_path: str
    status: str
    knowledge_bases: list[KBInfo] = []
    uploaded_by_email: str | None = None
    uploaded_by_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FileListResponse(BaseModel):
    """Paginated file listing."""
    items: list[FileItem]
    total: int


class AssignRequest(BaseModel):
    """Body for assigning a file to a knowledge base."""
    knowledge_base_id: UUID


# =============================================================================
# File listing endpoint
# =============================================================================


@router.get("", response_model=FileListResponse)
async def list_files(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    search: str | None = Query(None, description="Search by filename"),
    file_type: str | None = Query(None, description="Filter by file type"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
) -> FileListResponse:
    """List all documents uploaded by the current user.

    Supports pagination, search by filename, and filtering by file type / status.
    """
    base = (
        select(Document)
        .outerjoin(User, Document.uploaded_by == User.id)
        .where(Document.uploaded_by == current_user.id)
    )

    if search:
        base = base.where(Document.filename.ilike(f"%{search}%"))
    if file_type:
        base = base.where(Document.file_type == file_type)
    if status_filter:
        base = base.where(Document.status == status_filter)

    # Count
    count_q = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    # Fetch page with eager-loaded relations
    query = (
        base
        .options(
            selectinload(Document.knowledge_bases),
            selectinload(Document.uploader),
        )
        .order_by(Document.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    docs = result.scalars().unique().all()

    items = [
        FileItem(
            id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            file_path=doc.file_path,
            status=doc.status,
            knowledge_bases=[
                KBInfo(id=kb.id, name=kb.name)
                for kb in (doc.knowledge_bases or [])
            ],
            uploaded_by_email=doc.uploader.email if doc.uploader else None,
            uploaded_by_name=doc.uploader.name if doc.uploader else None,
            created_at=doc.created_at,
        )
        for doc in docs
    ]

    return FileListResponse(items=items, total=total)


# =============================================================================
# File upload endpoints
# =============================================================================


def validate_file(file: UploadFile) -> None:
    """Validate uploaded file."""
    if not file.filename:
        raise ValidationError("Filename is required")

    # Check extension
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(
            f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS.keys())}"
        )

    # Check content type
    content_type = file.content_type or mimetypes.guess_type(file.filename)[0]
    if content_type and content_type not in ALLOWED_EXTENSIONS.values():
        # Allow if extension is valid but MIME type is generic
        if content_type not in ("application/octet-stream", "binary/octet-stream"):
            raise ValidationError(f"Invalid content type: {content_type}")


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    knowledge_base_id: str | None = Form(None),
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> DocumentResponse:
    """Upload a file, optionally assigning it to a knowledge base.

    Without knowledge_base_id: file is stored as a standalone upload.
    With knowledge_base_id: file is stored, assigned, and processing is dispatched.
    """
    # Parse optional KB ID
    kb_id: UUID | None = None
    if knowledge_base_id:
        try:
            kb_id = UUID(knowledge_base_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid knowledge_base_id format",
            )

    # Validate file
    try:
        validate_file(file)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)

    # Read file content
    content = await file.read()

    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    try:
        service = KnowledgeBaseService(db)

        if kb_id:
            await service.get_knowledge_base(kb_id)

        document = await service.upload_document(
            filename=file.filename,
            content=content,
            user_id=current_user.id,
            kb_id=kb_id,
        )

        # Commit so the Celery worker can see the document
        await db.commit()

        # Dispatch async processing only if assigned to a KB
        if kb_id:
            _dispatch_processing(str(document.id))

        # Refresh to get relationships
        await db.refresh(document)

        return _build_doc_response(document)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/upload-text", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_text(
    knowledge_base_id: str | None = Form(None),
    title: str = Form(...),
    content: str = Form(...),
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> DocumentResponse:
    """Upload raw text content, optionally to a knowledge base."""
    kb_id: UUID | None = None
    if knowledge_base_id:
        try:
            kb_id = UUID(knowledge_base_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid knowledge_base_id format",
            )

    if not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content cannot be empty",
        )

    try:
        service = KnowledgeBaseService(db)

        document = await service.upload_document(
            filename=f"{title}.txt",
            content=content.encode("utf-8"),
            user_id=current_user.id,
            kb_id=kb_id,
        )

        await db.commit()

        if kb_id:
            _dispatch_processing(str(document.id))

        await db.refresh(document)
        return _build_doc_response(document)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/upload-url", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_from_url(
    knowledge_base_id: str | None = Form(None),
    url: str = Form(...),
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> DocumentResponse:
    """Fetch and upload content from a URL."""
    import httpx

    kb_id: UUID | None = None
    if knowledge_base_id:
        try:
            kb_id = UUID(knowledge_base_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid knowledge_base_id format",
            )

    if not url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL. Must start with http:// or https://",
        )

    try:
        service = KnowledgeBaseService(db)

        if kb_id:
            await service.get_knowledge_base(kb_id)

        # Fetch URL content
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            url_content = response.content

        # Generate filename from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        filename = parsed.path.split("/")[-1] or parsed.netloc
        if not filename.endswith((".html", ".htm", ".txt", ".md")):
            filename += ".html"

        document = await service.upload_document(
            filename=filename,
            content=url_content,
            metadata={"source_url": url},
            user_id=current_user.id,
            kb_id=kb_id,
        )

        await db.commit()

        if kb_id:
            _dispatch_processing(str(document.id))

        await db.refresh(document)
        return _build_doc_response(document)

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch URL: {str(e)}",
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


# =============================================================================
# File assignment endpoints
# =============================================================================


@router.post("/{file_id}/assign", response_model=DocumentResponse)
async def assign_file_to_kb(
    file_id: UUID,
    body: AssignRequest,
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> DocumentResponse:
    """Assign a file to a knowledge base.

    If this is the first assignment and the document hasn't been processed,
    processing is dispatched automatically.
    """
    try:
        service = KnowledgeBaseService(db)
        document = await service.assign_document_to_kb(file_id, body.knowledge_base_id)

        await db.commit()

        # Dispatch processing if status was set to pending
        if document.status == "pending":
            _dispatch_processing(str(document.id))

        await db.refresh(document)
        return _build_doc_response(document)

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/{file_id}/assign/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_file_from_kb(
    file_id: UUID,
    kb_id: UUID,
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> None:
    """Remove a file from a knowledge base.

    The file and its processed data are kept (other KBs may use them).
    """
    try:
        service = KnowledgeBaseService(db)
        await service.unassign_document_from_kb(file_id, kb_id)
        await db.commit()

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    db: DbSession = None,
    current_user: CurrentUser = None,
) -> None:
    """Delete a file permanently (removes from all KBs, Qdrant, and storage)."""
    try:
        service = KnowledgeBaseService(db)
        document = await service.get_document(file_id)

        # Ownership check
        if document.uploaded_by and document.uploaded_by != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only delete your own files",
            )

        await service.delete_document(file_id)
        await db.commit()

    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=e.message)


# =============================================================================
# Helpers
# =============================================================================


def _build_doc_response(document: Document) -> DocumentResponse:
    """Build a DocumentResponse from a Document model."""
    kbs = []
    if hasattr(document, "knowledge_bases") and document.knowledge_bases:
        kbs = [
            KnowledgeBaseSummary(id=kb.id, name=kb.name)
            for kb in document.knowledge_bases
        ]

    return DocumentResponse(
        id=document.id,
        knowledge_base_id=kbs[0].id if kbs else None,
        knowledge_bases=kbs,
        filename=document.filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        error_message=document.error_message,
        chunk_count=document.chunk_count,
        structured_json_path=document.structured_json_path,
        page_count=document.page_count,
        language=document.language,
        metadata=document.meta_data,
        created_at=document.created_at,
    )
