"""Text chunking utilities for RAG."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Chunk:
    """A text chunk with metadata."""

    content: str
    index: int
    metadata: dict


class TextChunker:
    """Split text into chunks for embedding."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        separators: list[str] | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def chunk_text(
        self,
        text: str,
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Split text into overlapping chunks.

        Uses a recursive splitting approach:
        1. Try to split on paragraph breaks
        2. Fall back to sentence breaks
        3. Fall back to word breaks
        4. Fall back to character breaks
        """
        metadata = metadata or {}

        # Clean the text
        text = self._clean_text(text)

        if not text:
            return []

        # Split into chunks
        chunks = self._split_text(text, self.separators)

        # Create Chunk objects with metadata
        return [
            Chunk(
                content=chunk_text,
                index=i,
                metadata={**metadata, "chunk_index": i},
            )
            for i, chunk_text in enumerate(chunks)
        ]

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Replace multiple whitespace with single space
        text = re.sub(r"\s+", " ", text)
        # Remove leading/trailing whitespace
        text = text.strip()
        return text

    def _split_text(
        self,
        text: str,
        separators: list[str],
    ) -> list[str]:
        """Recursively split text into chunks."""
        if not separators:
            # Last resort: split by characters
            return self._split_by_size(text)

        separator = separators[0]
        remaining_separators = separators[1:]

        # Split by current separator
        if separator:
            splits = text.split(separator)
        else:
            # Empty separator means split by character
            splits = list(text)

        chunks = []
        current_chunk = ""

        for split in splits:
            # Add separator back (except for empty separator)
            piece = split + separator if separator else split

            # Check if adding this piece would exceed chunk size
            if len(current_chunk) + len(piece) <= self.chunk_size:
                current_chunk += piece
            else:
                # Current chunk is full
                if current_chunk:
                    # Check if current chunk is too large and needs further splitting
                    if len(current_chunk) > self.chunk_size and remaining_separators:
                        sub_chunks = self._split_text(
                            current_chunk.rstrip(separator), remaining_separators
                        )
                        chunks.extend(sub_chunks)
                    else:
                        chunks.append(current_chunk.rstrip(separator))

                # Start new chunk with overlap
                if chunks and self.chunk_overlap > 0:
                    # Get overlap from previous chunk
                    overlap = self._get_overlap(chunks[-1])
                    current_chunk = overlap + piece
                else:
                    current_chunk = piece

        # Don't forget the last chunk
        if current_chunk:
            current_chunk = current_chunk.rstrip(separator)
            if len(current_chunk) > self.chunk_size and remaining_separators:
                sub_chunks = self._split_text(current_chunk, remaining_separators)
                chunks.extend(sub_chunks)
            else:
                chunks.append(current_chunk)

        return [c for c in chunks if c.strip()]

    def _split_by_size(self, text: str) -> list[str]:
        """Split text by character size with overlap."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start = end - self.chunk_overlap

        return chunks

    def _get_overlap(self, text: str) -> str:
        """Get the overlap portion from the end of text."""
        if len(text) <= self.chunk_overlap:
            return text
        return text[-self.chunk_overlap :]

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count (rough approximation)."""
        # Rough estimate: 1 token ≈ 4 characters for English text
        return len(text) // 4
