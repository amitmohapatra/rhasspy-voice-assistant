"""ABBYY Vantage OCR provider."""

from .client import AbbyyVantageClient
from .adapter import AbbyyVantageAdapter
from .merger import AbbyyDoclingMerger

__all__ = ["AbbyyVantageClient", "AbbyyVantageAdapter", "AbbyyDoclingMerger"]
