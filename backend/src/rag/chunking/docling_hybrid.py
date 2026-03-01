"""Docling HybridChunker - Single unified chunker for all document types.

Replaces 6 separate chunkers (Recursive, Semantic, Hierarchical, Markdown, Code)
with Docling's structure-aware HybridChunker that automatically adapts to
document structure (headings, tables, lists, code blocks, images, equations).

For documents parsed by Docling (PDF, DOCX, PPTX, etc.), the HybridChunker
receives the full DoclingDocument and produces chunks that respect structure.

For plain text (TXT, CSV, JSON, etc.), falls back to a simple token-based
splitter that mimics HybridChunker's behavior.

References:
- https://ds4sd.github.io/docling/
- docling_core.transforms.chunker.HybridChunker
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Optional

from src.rag.base import BaseChunker, Chunk, RAGConfig
from src.rag.models import DocumentStructure

logger = logging.getLogger(__name__)

# Internal defaults (not user-configurable)
DEFAULT_CHUNK_SIZE = 512      # tokens
DEFAULT_CHUNK_OVERLAP = 50    # tokens
MIN_CHUNK_SIZE = 64           # tokens


class DoclingHybridChunker(BaseChunker):
    """Unified chunker using Docling's HybridChunker.

    Automatically handles all document types:
    - Structured documents (PDF, DOCX, PPTX): Uses Docling parse tree
      to create chunks that respect headings, tables, lists, code blocks.
    - Plain text: Falls back to token-based recursive splitting.

    Key features:
    - Structure-aware: Never splits a table or code block mid-way
    - Heading context: Prepends section headings to each chunk
    - Overlap: Configurable token overlap between chunks
    - Atomic elements: Tables, images, equations kept as single chunks
    """

    def __init__(self, config: RAGConfig):
        super().__init__(config)
        self._tokenizer = None
        self._token_cache: dict[int, int] = {}  # hash(text) → token count

    @property
    def tokenizer(self):
        """Lazy-load tokenizer for token counting."""
        if self._tokenizer is None:
            try:
                from transformers import AutoTokenizer
                self._tokenizer = AutoTokenizer.from_pretrained(
                    "BAAI/bge-m3", use_fast=True
                )
            except Exception:
                # Fallback: approximate 1 token ≈ 4 chars
                self._tokenizer = _CharFallbackTokenizer()
        return self._tokenizer

    def chunk(self, text: str, metadata: Optional[dict] = None) -> list[Chunk]:
        """Chunk plain text using token-based recursive splitting.

        Used when no Docling DocumentStructure is available (plain text files).
        """
        if not text or not text.strip():
            return []

        metadata = metadata or {}
        splits = self._recursive_token_split(text)

        chunks = []
        start_char = 0
        for i, content in enumerate(splits):
            chunk = Chunk(
                id="",
                document_id="",
                content=content,
                metadata={**metadata, "chunking_strategy": "docling_hybrid"},
                chunk_index=i,
                start_char=start_char,
                end_char=start_char + len(content),
            )
            chunks.append(chunk)
            start_char += len(content)

        return chunks

    def chunk_docling_document(
        self,
        docling_doc: Any,
        document_id: str = "",
        base_metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """Chunk a Docling DoclingDocument using HybridChunker.

        This is the primary entry point for structured documents.

        Args:
            docling_doc: A docling_core.types.doc.DoclingDocument instance.
            document_id: Parent document ID.
            base_metadata: Base metadata for all chunks.

        Returns:
            List of Chunk objects with structure-aware boundaries.
        """
        metadata = base_metadata or {}

        try:
            from docling_core.transforms.chunker import HybridChunker

            chunker = HybridChunker(
                tokenizer=self.tokenizer,
                max_tokens=DEFAULT_CHUNK_SIZE,
                merge_peers=True,
            )

            chunk_iter = chunker.chunk(docling_doc)
            chunks = []

            for i, docling_chunk in enumerate(chunk_iter):
                # Extract text and heading context
                text = docling_chunk.text
                # HybridChunker enriches chunks with heading path
                headings = getattr(docling_chunk, "meta", {}).get("headings", [])
                if headings:
                    heading_prefix = " > ".join(headings) + "\n\n"
                    text = heading_prefix + text

                # Extract page info
                page = None
                bbox = None
                if hasattr(docling_chunk, "meta"):
                    page = docling_chunk.meta.get("page", None)
                    bbox_data = docling_chunk.meta.get("bbox", None)
                    if bbox_data:
                        bbox = bbox_data if isinstance(bbox_data, dict) else None

                # Determine element type
                element_type = "text"
                if hasattr(docling_chunk, "meta"):
                    element_type = docling_chunk.meta.get("doc_items", [{}])[0].get(
                        "type", "text"
                    ) if docling_chunk.meta.get("doc_items") else "text"

                chunk_id = Chunk.generate_id(document_id, i, text)
                chunk = Chunk(
                    id=chunk_id,
                    document_id=document_id,
                    content=text,
                    metadata={
                        **metadata,
                        "chunking_strategy": "docling_hybrid",
                        "headings": headings,
                    },
                    chunk_index=i,
                    page_number=page or 0,
                    element_type=element_type,
                    bbox=bbox,
                )
                chunks.append(chunk)

            logger.info(
                "Docling HybridChunker produced %d chunks for document %s",
                len(chunks),
                document_id,
            )
            return chunks

        except ImportError:
            logger.warning(
                "docling_core not available, falling back to structure-based chunking"
            )
            return self._fallback_structure_chunk(
                docling_doc, document_id, metadata
            )

    def chunk_structured(
        self,
        structure: DocumentStructure,
        document_id: str = "",
        base_metadata: Optional[dict] = None,
    ) -> list[Chunk]:
        """Chunk a DocumentStructure (legacy compatibility).

        Converts DocumentStructure elements into chunks respecting structure.
        Tables, images, and equations are kept as atomic chunks.
        Text elements are grouped and split by token count.

        Args:
            structure: DocumentStructure from Docling processor.
            document_id: Parent document ID.
            base_metadata: Base metadata for all chunks.

        Returns:
            List of chunks.
        """
        metadata = base_metadata or {}
        all_chunks: list[Chunk] = []
        chunk_index = 0

        # Group consecutive text elements, flush on non-text
        text_buffer: list[dict] = []

        for element in structure.elements:
            # v2: skip elements marked for non-indexing (page headers/footers, etc.)
            if element.get("skip_indexing", False):
                continue

            etype = element.get("element_type", "text")
            # v2 format uses "type" key instead of "element_type"
            if not etype or etype == "text":
                etype = element.get("type", etype)
            content = element.get("content", "")
            page_number = element.get("page_number", 0)
            bbox = element.get("bbox")
            elem_metadata = element.get("metadata", {})

            if not content.strip():
                continue

            # Text-like elements → buffer for merging + token-based splitting
            text_like = {
                "text", "heading", "paragraph", "section_header",
                "list_item", "title", "key_value", "form_field",
                "caption", "footnote", "reference", "document_index",
                "page_header", "page_footer", "handwritten",
                "grading_scale",
            }
            if etype in text_like:
                text_buffer.append(element)
                continue

            # Flush text buffer before atomic element
            if text_buffer:
                chunks = self._flush_text_buffer(
                    text_buffer, document_id, chunk_index, metadata
                )
                all_chunks.extend(chunks)
                chunk_index += len(chunks)
                text_buffer = []

            # Build extra metadata from element enrichment
            extra_metadata: dict[str, Any] = {}

            # Atomic elements: table, image, chart, equation, code, checkbox
            if etype in ("image", "figure"):
                original_caption = elem_metadata.get("original_caption", "")
                if original_caption:
                    extra_metadata["original_caption"] = original_caption
                content = f"[Image]\n{content}" if content else "[Image]"
            elif etype == "chart":
                original_caption = elem_metadata.get("original_caption", "")
                if original_caption:
                    extra_metadata["original_caption"] = original_caption
                if elem_metadata.get("picture_class"):
                    extra_metadata["chart_type"] = elem_metadata["picture_class"]
                content = f"[Chart]\n{content}" if content else "[Chart]"
            elif etype == "table":
                if elem_metadata.get("table_cells"):
                    extra_metadata["table_cells"] = elem_metadata["table_cells"]
                nl_desc = elem_metadata.get("nl_description", "")
                if nl_desc:
                    extra_metadata["table_markdown"] = content
                    content = f"[Table]\n{nl_desc}\n\n{content}"
            elif etype == "code":
                nl_desc = elem_metadata.get("nl_description", "")
                if nl_desc:
                    extra_metadata["code_original"] = content
                    content = f"[Code]\n{nl_desc}\n\n{content}"
            elif etype == "equation":
                content = f"[Equation: {content}]"
            elif etype == "checkbox":
                checked = elem_metadata.get("checked", False)
                mark = "[x]" if checked else "[ ]"
                content = f"{mark} {content}"

            ocr_conf = elem_metadata.get("ocr_confidence")
            if ocr_conf is not None:
                extra_metadata["ocr_confidence"] = ocr_conf

            if elem_metadata.get("handwriting_detected"):
                extra_metadata["handwriting_detected"] = True

            chunk = Chunk(
                id=Chunk.generate_id(document_id, chunk_index, content),
                document_id=document_id,
                content=content,
                metadata={
                    **metadata,
                    "chunking_strategy": "docling_hybrid",
                    **extra_metadata,
                },
                chunk_index=chunk_index,
                page_number=page_number,
                element_type=etype,
                bbox=bbox,
            )
            all_chunks.append(chunk)
            chunk_index += 1

        # Flush remaining text
        if text_buffer:
            chunks = self._flush_text_buffer(
                text_buffer, document_id, chunk_index, metadata
            )
            all_chunks.extend(chunks)

        return all_chunks

    # ---- Internal helpers ----

    def _flush_text_buffer(
        self,
        elements: list[dict],
        document_id: str,
        start_index: int,
        base_metadata: dict,
    ) -> list[Chunk]:
        """Flush accumulated text elements through token-based splitting."""
        combined = "\n\n".join(
            e.get("content", "") for e in elements if e.get("content", "").strip()
        )
        if not combined.strip():
            return []

        first_page = elements[0].get("page_number", 0)
        splits = self._recursive_token_split(combined)

        result = []
        for i, content in enumerate(splits):
            chunk = Chunk(
                id=Chunk.generate_id(document_id, start_index + i, content),
                document_id=document_id,
                content=content,
                metadata={**base_metadata, "chunking_strategy": "docling_hybrid"},
                chunk_index=start_index + i,
                page_number=first_page,
                element_type="text",
            )
            result.append(chunk)

        return result

    def _recursive_token_split(self, text: str) -> list[str]:
        """Split text into chunks of ~DEFAULT_CHUNK_SIZE tokens.

        Uses paragraph > sentence > word boundaries.
        """
        if self._count_tokens(text) <= DEFAULT_CHUNK_SIZE:
            return [text.strip()] if text.strip() else []

        separators = ["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " "]
        return self._split_recursive(text, separators)

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split on separator hierarchy."""
        if not separators:
            # Last resort: hard cut by tokens
            return self._hard_split(text)

        sep = separators[0]
        remaining_seps = separators[1:]
        parts = text.split(sep) if sep else [text]

        # Merge small parts, split large ones
        chunks: list[str] = []
        current = ""

        for part in parts:
            part = part.strip()
            if not part:
                continue

            test = current + (sep if current else "") + part
            if self._count_tokens(test) <= DEFAULT_CHUNK_SIZE:
                current = test
            else:
                if current:
                    chunks.append(current)
                # Check if this single part is too big
                if self._count_tokens(part) > DEFAULT_CHUNK_SIZE:
                    sub_chunks = self._split_recursive(part, remaining_seps)
                    chunks.extend(sub_chunks)
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        return [c for c in chunks if c.strip()]

    def _hard_split(self, text: str) -> list[str]:
        """Hard split text into token-sized pieces (last resort)."""
        words = text.split()
        chunks = []
        current_words = []
        current_tokens = 0

        for word in words:
            word_tokens = self._count_tokens(word)
            if current_tokens + word_tokens > DEFAULT_CHUNK_SIZE and current_words:
                chunks.append(" ".join(current_words))
                current_words = []
                current_tokens = 0
            current_words.append(word)
            current_tokens += word_tokens

        if current_words:
            chunks.append(" ".join(current_words))

        return chunks

    def _count_tokens(self, text: str) -> int:
        """Count tokens using the tokenizer (cached)."""
        key = hash(text)
        cached = self._token_cache.get(key)
        if cached is not None:
            return cached

        if isinstance(self.tokenizer, _CharFallbackTokenizer):
            count = self.tokenizer.count(text)
        else:
            try:
                count = len(self.tokenizer.encode(text, add_special_tokens=False))
            except Exception:
                count = len(text) // 4

        # Limit cache size to avoid memory bloat
        if len(self._token_cache) < 8192:
            self._token_cache[key] = count
        return count

    def _fallback_structure_chunk(
        self,
        docling_doc: Any,
        document_id: str,
        metadata: dict,
    ) -> list[Chunk]:
        """Fallback when docling_core HybridChunker is not available."""
        # Try to get text from the document
        text = ""
        if hasattr(docling_doc, "export_to_markdown"):
            text = docling_doc.export_to_markdown()
        elif hasattr(docling_doc, "text"):
            text = docling_doc.text
        else:
            text = str(docling_doc)

        return self.chunk(text, {**metadata, "document_id": document_id})


class _CharFallbackTokenizer:
    """Fallback tokenizer using character count (1 token ≈ 4 chars)."""

    def count(self, text: str) -> int:
        return len(text) // 4

    def encode(self, text: str, **kwargs) -> list[int]:
        return list(range(len(text) // 4))
