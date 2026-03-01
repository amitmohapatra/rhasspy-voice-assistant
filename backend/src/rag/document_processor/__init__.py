"""Document processor module for multimodal RAG.

Powered by:
- Docling (document parsing)
- PaddleOCR PP-OCRv5 (traditional OCR)
- PaddleOCR-VL-1.5 (vision-language for images/charts/tables)

All ML models run in the inference container; this module calls them via HTTP.

Supported formats: PDF, DOCX, PPTX, XLSX, HTML, images, LaTeX, code files
"""

from src.rag.document_processor.format_router import FormatRouter

__all__ = [
    "FormatRouter",
]
