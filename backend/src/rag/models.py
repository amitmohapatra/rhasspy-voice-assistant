"""Shared data types for the RAG pipeline.

Defines core types used across all RAG components to avoid circular imports.
All types are frozen dataclasses for thread safety.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ElementType(str, Enum):
    """Document element types produced by Docling parsing."""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    EQUATION = "equation"
    CODE = "code"
    HEADING = "heading"


@dataclass(frozen=True)
class BoundingBox:
    """Bounding box for a document element on a page.

    Coordinates are normalized to [0, 1] relative to page dimensions.
    """
    x0: float
    y0: float
    x1: float
    y1: float
    page: int

    def to_dict(self) -> dict[str, float | int]:
        return {"x0": self.x0, "y0": self.y0, "x1": self.x1, "y1": self.y1, "page": self.page}

    @classmethod
    def from_dict(cls, d: dict) -> BoundingBox:
        return cls(x0=d["x0"], y0=d["y0"], x1=d["x1"], y1=d["y1"], page=d["page"])


@dataclass(frozen=True)
class TripleEmbedding:
    """Triple embedding from BGE-M3: dense + sparse + optional ColBERT vectors.

    Attributes:
        dense: 1024-dimensional dense embedding vector.
        sparse: Sparse lexical weights as {token_id: weight}.
        colbert: Optional list of ColBERT token-level vectors.
    """
    dense: list[float]
    sparse: dict[int, float] = field(default_factory=dict)
    colbert: Optional[list[list[float]]] = None

    @property
    def dense_dim(self) -> int:
        return len(self.dense)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "dense": self.dense,
            "sparse": self.sparse,
        }
        if self.colbert is not None:
            d["colbert"] = self.colbert
        return d

    @classmethod
    def from_dict(cls, d: dict) -> TripleEmbedding:
        return cls(
            dense=d["dense"],
            sparse={int(k): v for k, v in d.get("sparse", {}).items()},
            colbert=d.get("colbert"),
        )


@dataclass(frozen=True)
class DocumentStructure:
    """Structured document output from Docling parsing.

    Attributes:
        elements: List of parsed elements with type, content, and position info.
        metadata: Document-level metadata (title, author, language, etc.).
        format_version: Schema version for forward compatibility.
    """
    elements: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)
    format_version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "elements": self.elements,
            "metadata": self.metadata,
            "format_version": self.format_version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DocumentStructure:
        return cls(
            elements=d.get("elements", []),
            metadata=d.get("metadata", {}),
            format_version=d.get("format_version", "1.0"),
        )
