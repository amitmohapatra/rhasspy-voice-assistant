"""Knowledge Base service for RAG document management.

Uses fully automated best-in-class pipeline:
- Docling HybridChunker (structure-aware, auto-adapts to document type)
- Late chunking with BGE-M3 (document-context-aware embeddings, zero LLM calls)
- Parent-child retrieval (search small chunks, return parent sections)
- BGE-M3 triple embeddings (dense+sparse)
- 4-way hybrid retrieval + RRF + BGE-reranker-v2-m3 (text + visual)
- Qdrant with named vectors + Redis cache

Documents are decoupled from KBs. Files can be uploaded independently and
assigned to multiple KBs. Processing runs once per document.
"""

from __future__ import annotations

import logging
import uuid as uuid_module
from pathlib import Path
from uuid import UUID

logger = logging.getLogger(__name__)

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import NotFoundError, ValidationError, StorageError
from src.core.storage import get_storage_backend, StorageBackend
from src.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument, Document, DocumentChunk
from src.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
)


class KnowledgeBaseService:
    """Service for knowledge base and document management."""

    # Expanded supported file types (Docling handles most of these)
    SUPPORTED_TYPES = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".json": "application/json",
        ".jsonl": "application/jsonl",
        ".html": "text/html",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".epub": "application/epub+zip",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".tex": "application/x-latex",
        ".rtf": "application/rtf",
    }

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._storage: StorageBackend | None = None
        self._qdrant = None

    @property
    def storage(self) -> StorageBackend:
        """Lazy-loaded storage backend."""
        if self._storage is None:
            self._storage = get_storage_backend()
        return self._storage

    async def _get_qdrant(self):
        """Lazy-initialize QdrantStore."""
        if self._qdrant is None:
            from src.rag.vectorstores.qdrant import QdrantStore
            from src.rag.base import RAGConfig

            config = RAGConfig()
            self._qdrant = QdrantStore(
                config=config,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
            )
            await self._qdrant.initialize()
            from src.core.config import settings as app_settings
            if app_settings.colsmol_enabled:
                await self._qdrant.initialize_page_images()
        return self._qdrant

    async def _get_inference_client(self):
        """Get the inference service client."""
        from src.clients.inference_client import get_inference_client
        return get_inference_client()

    # ==================== Knowledge Base CRUD ====================

    async def create_knowledge_base(
        self,
        data: KnowledgeBaseCreate,
        user_id: UUID | None = None,
    ) -> KnowledgeBase:
        """Create a new knowledge base.

        For platform_managed KBs: All RAG config is automatic.
        For provider_managed KBs: Stores provider reference.
        """
        kb_kwargs = {
            "name": data.name,
            "description": data.description,
            "kb_type": data.kb_type,
            "settings": data.settings,
            "created_by": user_id,
        }

        if data.kb_type == "provider_managed":
            kb_kwargs.update({
                "provider_id": UUID(data.provider_id) if data.provider_id else None,
                "provider_config": data.provider_config,
            })

        kb = KnowledgeBase(**kb_kwargs)
        self.db.add(kb)
        await self.db.flush()
        await self.db.refresh(kb)

        return kb

    async def get_knowledge_base(
        self,
        kb_id: UUID,
    ) -> KnowledgeBase:
        """Get a knowledge base by ID."""
        query = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)

        result = await self.db.execute(query)
        kb = result.scalar_one_or_none()

        if not kb:
            raise NotFoundError(
                message="Knowledge base not found",
                resource="knowledge_base",
                details={"knowledge_base_id": str(kb_id)},
            )

        return kb

    async def list_knowledge_bases(
        self,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        kb_type: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[KnowledgeBase], int]:
        """List knowledge bases with total count."""
        base_query = select(KnowledgeBase)

        if user_id:
            base_query = base_query.where(KnowledgeBase.created_by == user_id)

        if kb_type:
            base_query = base_query.where(KnowledgeBase.kb_type == kb_type)

        if search:
            search_filter = f"%{search}%"
            base_query = base_query.where(
                (KnowledgeBase.name.ilike(search_filter))
                | (KnowledgeBase.description.ilike(search_filter))
            )

        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Data query
        data_query = base_query.offset(skip).limit(limit).order_by(
            KnowledgeBase.created_at.desc()
        )
        result = await self.db.execute(data_query)

        return list(result.scalars().all()), total

    async def update_knowledge_base(
        self,
        kb_id: UUID,
        data: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        """Update a knowledge base."""
        kb = await self.get_knowledge_base(kb_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(kb, field, value)

        await self.db.flush()
        await self.db.refresh(kb)

        return kb

    async def delete_knowledge_base(
        self,
        kb_id: UUID,
    ) -> bool:
        """Delete a knowledge base.

        Files survive KB deletion — only the join table entries are removed
        (via ON DELETE CASCADE). Qdrant vectors and files are NOT deleted
        because other KBs may reference the same documents.
        """
        kb = await self.get_knowledge_base(kb_id)

        await self.db.delete(kb)
        await self.db.flush()

        return True

    async def get_knowledge_base_stats(
        self,
        kb_id: UUID,
    ) -> dict:
        """Get statistics for a knowledge base."""
        kb = await self.get_knowledge_base(kb_id)

        # Count documents via join table
        doc_query = (
            select(func.count(KnowledgeBaseDocument.id))
            .where(KnowledgeBaseDocument.knowledge_base_id == kb_id)
        )
        doc_result = await self.db.execute(doc_query)
        doc_count = doc_result.scalar() or 0

        # Count chunks (excluding parent chunks) via join table
        chunk_query = (
            select(func.count(DocumentChunk.id))
            .join(Document, DocumentChunk.document_id == Document.id)
            .join(KnowledgeBaseDocument, KnowledgeBaseDocument.document_id == Document.id)
            .where(
                KnowledgeBaseDocument.knowledge_base_id == kb_id,
                DocumentChunk.is_parent == False,
            )
        )
        chunk_result = await self.db.execute(chunk_query)
        chunk_count = chunk_result.scalar() or 0

        return {
            "document_count": doc_count,
            "chunk_count": chunk_count,
            **KnowledgeBase.get_pipeline_info(),
        }

    # ==================== Document Management ====================

    async def upload_document(
        self,
        filename: str,
        content: bytes,
        metadata: dict | None = None,
        user_id: UUID | None = None,
        kb_id: UUID | None = None,
    ) -> Document:
        """Upload a document, optionally assigning it to a KB.

        If kb_id is None: file is stored as a standalone upload (status="uploaded").
        If kb_id is provided: file is stored, assigned to the KB, and queued for
        processing (status="pending").
        """
        if kb_id is not None:
            await self.get_knowledge_base(kb_id)

        # Validate file type
        file_ext = Path(filename).suffix.lower()
        if file_ext not in self.SUPPORTED_TYPES:
            raise ValidationError(
                message=f"Unsupported file type: {file_ext}",
                details={"supported_types": list(self.SUPPORTED_TYPES.keys())},
            )

        # Save file under user-scoped path
        file_path = await self._save_file(
            filename=filename,
            content=content,
            user_id=user_id,
        )

        # Create document record
        document = Document(
            filename=filename,
            file_type=file_ext,
            file_size=len(content),
            file_path=file_path,
            meta_data=metadata or {},
            status="pending" if kb_id else "uploaded",
            uploaded_by=user_id,
        )

        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)

        # If a KB was specified, create the join entry
        if kb_id is not None:
            join = KnowledgeBaseDocument(
                knowledge_base_id=kb_id,
                document_id=document.id,
            )
            self.db.add(join)
            await self.db.flush()

        return document

    async def assign_document_to_kb(
        self,
        document_id: UUID,
        kb_id: UUID,
    ) -> Document:
        """Assign an existing document to a knowledge base.

        If this is the first assignment and the document hasn't been processed
        yet, sets status to "pending" so the Celery worker picks it up.
        Returns the updated document.
        """
        document = await self.get_document(document_id)
        await self.get_knowledge_base(kb_id)

        # Check if already assigned
        existing = await self.db.execute(
            select(KnowledgeBaseDocument).where(
                KnowledgeBaseDocument.knowledge_base_id == kb_id,
                KnowledgeBaseDocument.document_id == document_id,
            )
        )
        if existing.scalar_one_or_none():
            return document  # Already assigned, no-op

        # Create join entry
        join = KnowledgeBaseDocument(
            knowledge_base_id=kb_id,
            document_id=document_id,
        )
        self.db.add(join)

        # Trigger processing if document hasn't been processed yet
        if document.status == "uploaded":
            document.status = "pending"

        await self.db.flush()
        await self.db.refresh(document)

        return document

    async def unassign_document_from_kb(
        self,
        document_id: UUID,
        kb_id: UUID,
    ) -> None:
        """Remove a document from a knowledge base.

        Chunks and Qdrant vectors are kept (other KBs may reference the same doc).
        """
        await self.get_document(document_id)
        await self.get_knowledge_base(kb_id)

        await self.db.execute(
            delete(KnowledgeBaseDocument).where(
                KnowledgeBaseDocument.knowledge_base_id == kb_id,
                KnowledgeBaseDocument.document_id == document_id,
            )
        )
        await self.db.flush()

    async def get_kb_document_ids(self, kb_ids: list[UUID]) -> list[UUID]:
        """Resolve knowledge base IDs to document IDs via the join table."""
        if not kb_ids:
            return []

        query = (
            select(KnowledgeBaseDocument.document_id)
            .where(KnowledgeBaseDocument.knowledge_base_id.in_(kb_ids))
            .distinct()
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def process_document(
        self,
        document_id: UUID,
    ) -> Document:
        """Process a document: Docling parse -> chunk -> late-chunk embed -> store.

        Pipeline:
        1. Docling parses document into structured elements (VLM enriches images/charts)
        2. DoclingHybridChunker creates structure-aware chunks
        3. Parent sections are created for parent-child retrieval
        4. Late chunking: BGE-M3 embeds full document in one pass, pools into chunk boundaries
        5. Chunks stored in Qdrant with named vectors
        6. Visual pages indexed with ColSmol-256M for visual retrieval
        7. Chunk metadata stored in PostgreSQL
        """
        doc_query = (
            select(Document)
            .where(Document.id == document_id)
        )
        result = await self.db.execute(doc_query)
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError(
                message="Document not found",
                resource="document",
            )

        # Use the uploading user's ID for metadata
        user_id_str = str(document.uploaded_by) if document.uploaded_by else None

        try:
            document.status = "processing"
            await self.db.flush()

            # Get file content from storage
            content = await self.storage.get(document.file_path)

            # Parse with Docling or handle simple formats
            from src.rag.document_processor.format_router import FormatRouter

            route = FormatRouter.get_route(document.filename)
            document_structure = None
            elements = []
            text = ""

            if route == "docling":
                # Use Docling via inference service for structured parsing
                from src.rag.models import DocumentStructure

                inference_client = await self._get_inference_client()
                processed = await inference_client.process_document(
                    content, document.filename
                )
                text = processed["text"]
                raw_elements = processed.get("elements", {})
                metadata_result = processed.get("metadata", {})

                # v2 returns elements as dict keyed by element_id;
                # convert to list for chunker compatibility
                if isinstance(raw_elements, dict):
                    elements = list(raw_elements.values())
                else:
                    elements = raw_elements

                logger.debug(
                    "Docling returned %d elements, text length=%d for %s",
                    len(elements), len(text), document.filename,
                )
                if elements:
                    # Log element types for debugging
                    etypes = {}
                    empty_count = 0
                    for el in elements:
                        et = el.get("element_type") or el.get("type", "unknown")
                        etypes[et] = etypes.get(et, 0) + 1
                        if not el.get("content", "").strip():
                            empty_count += 1
                    logger.debug(
                        "Element types: %s, empty content: %d/%d",
                        etypes, empty_count, len(elements),
                    )
                    document_structure = DocumentStructure(
                        elements=elements, metadata=metadata_result
                    )

                # Update document metadata
                document.page_count = processed.get("page_count")
                if metadata_result.get("language"):
                    document.language = metadata_result["language"]

                # Persist enriched JSON for document viewer (v2.0 format)
                import json as _json

                enriched_json = {
                    "version": processed.get("version", "2.0"),
                    "document_id": str(document.id),
                    "filename": document.filename,
                    "page_count": processed.get("page_count", 1),
                    "page_dimensions": processed.get("page_dimensions", {}),
                    "elements": processed.get("elements", {}),
                    "tables": processed.get("tables", {}),
                    "images": processed.get("images", {}),
                    "pages": processed.get("pages", {}),
                    "quality": processed.get("quality", {}),
                    "conversion_status": processed.get("conversion_status", "unknown"),
                    "timings": processed.get("timings", {}),
                    "metadata": metadata_result,
                }
                json_path = f"parsed/{document.id}/enriched.json"
                await self.storage.save(
                    key=json_path,
                    content=_json.dumps(enriched_json).encode(),
                    content_type="application/json",
                )
                document.structured_json_path = json_path

            elif route == "code":
                text = content.decode("utf-8")

                # Persist minimal enriched JSON for code files
                import json as _json

                enriched_json = {
                    "document_id": str(document.id),
                    "filename": document.filename,
                    "page_count": 1,
                    "page_dimensions": {},
                    "elements": [{"element_type": "code", "content": text, "page_number": 1, "bbox": None, "metadata": {}}],
                    "tables": [],
                    "images": [],
                    "metadata": {},
                }
                json_path = f"parsed/{document.id}/enriched.json"
                await self.storage.save(
                    key=json_path,
                    content=_json.dumps(enriched_json).encode(),
                    content_type="application/json",
                )
                document.structured_json_path = json_path
            else:
                # Text passthrough
                text = self._extract_simple_text(content, document.file_type)

                # Persist minimal enriched JSON for text files
                import json as _json

                enriched_json = {
                    "document_id": str(document.id),
                    "filename": document.filename,
                    "page_count": 1,
                    "page_dimensions": {},
                    "elements": [{"element_type": "paragraph", "content": text, "page_number": 1, "bbox": None, "metadata": {}}],
                    "tables": [],
                    "images": [],
                    "metadata": {},
                }
                json_path = f"parsed/{document.id}/enriched.json"
                await self.storage.save(
                    key=json_path,
                    content=_json.dumps(enriched_json).encode(),
                    content_type="application/json",
                )
                document.structured_json_path = json_path

            # Chunk using DoclingHybridChunker
            from src.rag.base import RAGConfig, Chunk as RAGChunk
            from src.rag.chunking.docling_hybrid import DoclingHybridChunker

            rag_config = RAGConfig()
            chunker = DoclingHybridChunker(rag_config)

            base_metadata = {
                "document_id": str(document.id),
                "filename": document.filename,
                "user_id": user_id_str,
            }

            if document_structure:
                chunks = chunker.chunk_structured(
                    structure=document_structure,
                    document_id=str(document.id),
                    base_metadata=base_metadata,
                )

                # Compute char offsets for chunks that lack them.
                # chunk_structured() doesn't set start_char/end_char, which
                # prevents late chunking from firing. Map each chunk's content
                # back to the full document text via sequential search.
                if text and chunks:
                    search_from = 0
                    for i, c in enumerate(chunks):
                        if c.start_char == c.end_char:
                            idx = text.find(c.content, search_from)
                            if idx >= 0:
                                chunks[i] = RAGChunk(
                                    id=c.id, document_id=c.document_id,
                                    content=c.content, embedding=c.embedding,
                                    metadata=c.metadata, chunk_index=c.chunk_index,
                                    start_char=idx, end_char=idx + len(c.content),
                                    page_number=c.page_number,
                                    element_type=c.element_type,
                                    bbox=c.bbox, parent_chunk_id=c.parent_chunk_id,
                                    parent_content=c.parent_content,
                                )
                                search_from = idx + len(c.content)
            else:
                chunks = chunker.chunk(text, base_metadata)
                chunks = [
                    RAGChunk(
                        id=RAGChunk.generate_id(str(document.id), i, c.content),
                        document_id=str(document.id),
                        content=c.content,
                        metadata=c.metadata,
                        chunk_index=i,
                        start_char=c.start_char,
                        end_char=c.end_char,
                        page_number=c.page_number,
                        element_type=c.element_type,
                    )
                    for i, c in enumerate(chunks)
                ]

            logger.debug(
                "Chunker produced %d chunks for %s (text len=%d, structure=%s)",
                len(chunks), document.filename, len(text),
                "yes" if document_structure else "no",
            )

            if not chunks:
                # Fallback: if Docling produced text but chunker failed, try plain text chunking
                if text and text.strip():
                    logger.warning(
                        "No chunks from structured chunking, falling back to plain text for %s",
                        document.filename,
                    )
                    chunks = chunker.chunk(text, base_metadata)
                    chunks = [
                        RAGChunk(
                            id=RAGChunk.generate_id(str(document.id), i, c.content),
                            document_id=str(document.id),
                            content=c.content,
                            metadata=c.metadata,
                            chunk_index=i,
                            start_char=c.start_char,
                            end_char=c.end_char,
                            page_number=c.page_number,
                            element_type=c.element_type,
                        )
                        for i, c in enumerate(chunks)
                    ]
                    logger.info("Fallback plain text chunking produced %d chunks", len(chunks))

            if not chunks:
                document.status = "completed"
                document.chunk_count = 0
                await self.db.flush()
                await self.db.refresh(document)
                return document

            # Create parent chunks for parent-child retrieval
            parent_map = self._create_parent_chunks(chunks, rag_config)

            # Late chunking: generate context-aware embeddings in one pass
            # Uses BGE-M3 to embed the full document, then pools into chunks.
            # Each chunk embedding has full document context — no LLM calls needed.
            inference_client = await self._get_inference_client()

            # Late chunking is only efficient when the full document fits within
            # BGE-M3's 8192-token window (~30K chars). Beyond that, the O(n²)
            # self-attention on CPU takes too long and tokens get truncated anyway.
            max_late_chunk_chars = 25000
            can_late_chunk = text and len(text) <= max_late_chunk_chars

            # Split chunks: those with valid char offsets go to late chunking,
            # the rest (tables/images with modified content, or chunks that
            # couldn't be mapped) get embedded independently.
            late_indices = []
            indep_indices = []
            for i, c in enumerate(chunks):
                if can_late_chunk and c.start_char != c.end_char:
                    late_indices.append(i)
                else:
                    indep_indices.append(i)

            if text and len(text) > max_late_chunk_chars:
                logger.info(
                    "Document %s too large for late chunking (%d chars), using independent embedding",
                    document.filename, len(text),
                )

            # Late-chunk path: single forward pass with document context
            if late_indices:
                late_chunks = [chunks[i] for i in late_indices]
                chunk_boundaries = [(c.start_char, c.end_char) for c in late_chunks]
                try:
                    triples = await inference_client.embed_late_chunk(
                        text, chunk_boundaries
                    )
                    for j, idx in enumerate(late_indices):
                        chunks[idx] = chunks[idx].with_embedding(triples[j])
                except Exception:
                    logger.warning(
                        "Late chunking failed for %s, falling back to independent embedding",
                        document.filename,
                    )
                    indep_indices = late_indices + indep_indices
                    late_indices = []

            # Independent path: embed each chunk's content separately
            if indep_indices:
                indep_texts = [chunks[i].content for i in indep_indices]
                triples = await inference_client.embed_triple(indep_texts)
                for j, idx in enumerate(indep_indices):
                    chunks[idx] = chunks[idx].with_embedding(triples[j])

            # Store in Qdrant with named vectors
            qdrant = await self._get_qdrant()
            await qdrant.add(chunks)

            # Visual indexing: render pages + embed with ColSmol for visual retrieval
            # Smart page selection: only index pages with visual elements
            from src.core.config import settings as app_settings
            page_count = document.page_count or 0
            if app_settings.colsmol_enabled and document.file_type in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif") and page_count > 0:
                visual_element_types = {"table", "figure", "chart", "image", "equation", "key_value", "form_field", "checkbox"}
                visual_pages: set[int] = set()
                if elements:
                    for el in elements:
                        et = el.get("element_type", "")
                        pn = el.get("page_number", 0)
                        if et in visual_element_types and pn > 0:
                            visual_pages.add(pn)

                if visual_pages:
                    try:
                        await self._index_page_images(
                            document=document,
                            file_bytes=content,
                            user_id=user_id_str,
                            qdrant=qdrant,
                            inference_client=inference_client,
                            visual_pages=visual_pages,
                        )
                    except Exception as e:
                        logger.warning("Visual indexing failed for %s: %s", document.filename, e)
                else:
                    logger.info("No visual elements found in %s, skipping ColSmol indexing", document.filename)

            # Create chunk records in PostgreSQL (metadata only — parent
            # content is stored in the Qdrant payload for retrieval).
            for chunk in chunks:
                db_chunk = DocumentChunk(
                    document_id=document.id,
                    content=chunk.metadata.get("original_content", chunk.content),
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    element_type=chunk.element_type or "text",
                    is_parent=False,
                    meta_data=chunk.metadata or {},
                )
                self.db.add(db_chunk)

            document.status = "completed"
            document.chunk_count = len(chunks)

            # Generate suggested prompts based on element types found
            suggested_prompts = self._generate_suggested_prompts(elements)
            if suggested_prompts:
                doc_meta = dict(document.meta_data) if document.meta_data else {}
                doc_meta["suggested_prompts"] = suggested_prompts
                document.meta_data = doc_meta

            await self.db.flush()
            await self.db.refresh(document)

            return document

        except Exception as e:
            document.status = "error"
            document.error_message = str(e)
            await self.db.flush()
            raise

    def _create_parent_chunks(
        self,
        chunks: list,
        config,
    ) -> dict[str, str]:
        """Create parent sections from consecutive chunks.

        Groups chunks into parent sections of ~parent_chunk_size tokens.
        Returns a mapping of parent_id -> parent_content.
        Also updates each chunk's parent_chunk_id.
        """
        if not config.enable_parent_child or not chunks:
            return {}

        from src.rag.base import Chunk as RAGChunk

        parent_map: dict[str, str] = {}
        parent_size = config.parent_chunk_size
        current_parent_chunks: list = []
        current_size = 0
        parent_counter = 0

        for i, chunk in enumerate(chunks):
            chunk_token_est = len(chunk.content) // 4  # Rough estimate
            current_parent_chunks.append(chunk)
            current_size += chunk_token_est

            # Create a parent when we hit the size limit or the last chunk
            if current_size >= parent_size or i == len(chunks) - 1:
                parent_id = f"parent_{chunk.document_id}_{parent_counter}"
                parent_content = "\n\n".join(c.content for c in current_parent_chunks)
                parent_map[parent_id] = parent_content

                # Update chunks with parent reference
                for j, c in enumerate(current_parent_chunks):
                    idx = i - len(current_parent_chunks) + 1 + j
                    if 0 <= idx < len(chunks):
                        chunks[idx] = RAGChunk(
                            id=c.id,
                            document_id=c.document_id,
                            content=c.content,
                            embedding=c.embedding,
                            metadata=c.metadata,
                            chunk_index=c.chunk_index,
                            start_char=c.start_char,
                            end_char=c.end_char,
                            page_number=c.page_number,
                            element_type=c.element_type,
                            bbox=c.bbox,
                            parent_chunk_id=parent_id,
                            parent_content=parent_content,
                        )

                current_parent_chunks = []
                current_size = 0
                parent_counter += 1

        return parent_map

    async def _index_page_images(
        self,
        document,
        file_bytes: bytes,
        user_id: str | None,
        qdrant,
        inference_client,
        visual_pages: set[int] | None = None,
    ) -> None:
        """Render PDF pages as images, embed with ColSmol, store in Qdrant.

        Smart page selection: only indexes pages that contain visual elements
        (tables, figures, charts, images, equations, key-value pairs, forms).
        Text-only pages are skipped — they're already covered by text search.

        Uses PyMuPDF to render each page at 144 DPI → PNG → base64.
        ColSmol-256M produces ~1030 patch vectors (128-dim each) per page.
        Capped at 200 visual pages per document.
        """
        import base64
        import fitz  # PyMuPDF

        max_visual_pages = 200

        # Detect PyMuPDF filetype from document extension
        ext = (document.file_type or "").lower()
        fitz_filetypes = {
            ".pdf": "pdf", ".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg",
            ".tiff": "tiff", ".tif": "tiff",
        }
        fitz_ft = fitz_filetypes.get(ext, "pdf")

        images_base64 = []
        page_texts = []
        page_numbers = []

        with fitz.open(stream=file_bytes, filetype=fitz_ft) as pdf_doc:
            total_pages = len(pdf_doc)

            if total_pages == 0:
                return

            # Determine which pages to index
            if visual_pages:
                # Only pages with visual elements, sorted and capped
                pages_to_index = sorted(p for p in visual_pages if 1 <= p <= total_pages)[:max_visual_pages]
            else:
                # Fallback: index all pages up to cap (e.g., single-page images)
                pages_to_index = list(range(1, min(total_pages, max_visual_pages) + 1))

            if not pages_to_index:
                return

            for page_num in pages_to_index:
                page = pdf_doc[page_num - 1]  # PyMuPDF uses 0-based index

                # Render at 144 DPI (2x default 72 DPI)
                mat = fitz.Matrix(2.0, 2.0)
                pix = page.get_pixmap(matrix=mat)
                png_bytes = pix.tobytes("png")
                images_base64.append(base64.b64encode(png_bytes).decode("ascii"))

                page_texts.append(page.get_text())
                page_numbers.append(page_num)

        if not images_base64:
            return

        # Embed page images via inference service (ColSmol-256M)
        page_embeddings = await inference_client.embed_visual(images_base64)

        if not page_embeddings or len(page_embeddings) != len(images_base64):
            logger.warning(
                "Visual embedding returned %d results for %d pages",
                len(page_embeddings) if page_embeddings else 0,
                len(images_base64),
            )
            return

        # Store in Qdrant page_images collection
        await qdrant.add_page_images(
            document_id=str(document.id),
            user_id=user_id or "",
            page_embeddings=page_embeddings,
            page_texts=page_texts,
            page_numbers=page_numbers,
        )

        logger.info(
            "Visual indexed %d/%d pages (visual elements only) for %s",
            len(page_embeddings), total_pages, document.filename,
        )

    def _extract_simple_text(self, content: bytes, file_type: str) -> str:
        """Extract text from simple file formats."""
        if file_type in (".txt", ".md"):
            return content.decode("utf-8")
        elif file_type == ".json":
            import json
            return json.dumps(json.loads(content.decode("utf-8")), indent=2)
        elif file_type == ".jsonl":
            return content.decode("utf-8")
        elif file_type == ".csv":
            return content.decode("utf-8")
        elif file_type == ".html":
            from bs4 import BeautifulSoup
            return BeautifulSoup(content.decode("utf-8"), "html.parser").get_text()

        return content.decode("utf-8", errors="replace")

    def _generate_suggested_prompts(self, elements: list[dict]) -> list[str]:
        """Generate suggested prompts based on element types found in the document.

        Analyzes which element types are present and generates relevant prompts.
        Capped at 6 prompts.
        """
        if not elements:
            return ["Summarize this document", "What are the key takeaways?"]

        # Collect element types (handle both v1 and v2 formats)
        etypes: set[str] = set()
        for el in elements:
            et = el.get("element_type") or el.get("type", "")
            if et:
                etypes.add(et)

        prompts = ["Summarize this document"]

        if etypes & {"table"}:
            prompts.append("List and describe all tables")
        if etypes & {"figure", "chart", "image"}:
            prompts.append("Describe the key figures and charts")
        if etypes & {"equation"}:
            prompts.append("Explain the equations")
        if etypes & {"code"}:
            prompts.append("Explain the code snippets")
        if etypes & {"key_value", "form_field"}:
            prompts.append("Extract all key-value pairs")
        if etypes & {"checkbox"}:
            prompts.append("List all checklist items and their status")

        prompts.append("What are the key takeaways?")

        return prompts[:6]

    async def get_document(
        self,
        document_id: UUID,
    ) -> Document:
        """Get a document by ID."""
        query = select(Document).where(Document.id == document_id)
        result = await self.db.execute(query)
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError(
                message="Document not found",
                resource="document",
            )

        return document

    async def list_documents(
        self,
        kb_id: UUID | None = None,
        user_id: UUID | None = None,
        skip: int = 0,
        limit: int = 100,
        status: str | None = None,
    ) -> list[Document]:
        """List documents, optionally filtered by KB or user."""
        query = select(Document)

        if kb_id is not None:
            await self.get_knowledge_base(kb_id)
            query = (
                query.join(
                    KnowledgeBaseDocument,
                    KnowledgeBaseDocument.document_id == Document.id,
                )
                .where(KnowledgeBaseDocument.knowledge_base_id == kb_id)
            )

        if user_id is not None:
            query = query.where(Document.uploaded_by == user_id)

        if status is not None:
            query = query.where(Document.status == status)

        query = query.offset(skip).limit(limit).order_by(Document.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_document(
        self,
        document_id: UUID,
    ) -> bool:
        """Delete a document and its chunks (from both PostgreSQL and Qdrant)."""
        document = await self.get_document(document_id)

        # Delete vectors from Qdrant (chunks + page images)
        qdrant = await self._get_qdrant()
        await qdrant.delete_by_document(str(document.id))
        await qdrant.delete_page_images_by_document(str(document.id))

        # Delete file from storage
        await self._delete_file(document.file_path)

        # Delete structured JSON if exists
        if document.structured_json_path:
            await self._delete_file(document.structured_json_path)

        await self.db.delete(document)
        await self.db.flush()

        return True

    # ==================== File Handling ====================

    async def _save_file(
        self,
        filename: str,
        content: bytes,
        user_id: UUID | None = None,
    ) -> str:
        """Save file to storage under user-scoped path."""
        unique_filename = f"{uuid_module.uuid4()}_{filename}"

        if user_id:
            key = self.storage.build_key(
                "uploads",
                str(user_id),
                unique_filename,
            )
        else:
            key = self.storage.build_key(
                "uploads",
                "anonymous",
                unique_filename,
            )

        content_type = self._get_content_type(filename)

        await self.storage.save(
            key=key,
            content=content,
            content_type=content_type,
            metadata={
                "original_filename": filename,
                "uploaded_by": str(user_id) if user_id else None,
            },
        )

        return key

    async def _delete_file(self, file_path: str) -> None:
        """Delete file from storage."""
        try:
            await self.storage.delete(file_path)
        except Exception:
            pass

    def _get_content_type(self, filename: str) -> str:
        """Get MIME type from filename."""
        ext = Path(filename).suffix.lower()
        return self.SUPPORTED_TYPES.get(ext, "application/octet-stream")
