"""File format router for document processing.

Routes documents to the appropriate processor based on file extension:
- Text/code files -> text passthrough
- Everything else -> Docling processor (via inference service)
"""

from __future__ import annotations

from pathlib import Path


# Extensions that are simple text and don't need Docling
TEXT_PASSTHROUGH_EXTENSIONS = {
    "txt", "md", "markdown", "rst", "csv", "tsv", "json", "jsonl",
    "yaml", "yml", "toml", "ini", "cfg", "conf",
}

# Code file extensions (passthrough as code elements)
CODE_EXTENSIONS = {
    "py", "js", "ts", "jsx", "tsx", "java", "cpp", "c", "h", "hpp",
    "cs", "go", "rs", "rb", "php", "swift", "kt", "scala", "r",
    "sql", "sh", "bash", "zsh", "ps1", "lua", "perl", "pl",
    "html", "htm", "css", "scss", "sass", "less",
    "xml", "xsl", "xslt", "svg",
}

# Extensions handled by Docling (via inference service)
DOCLING_EXTENSIONS = {
    "pdf", "docx", "pptx", "xlsx",
    "png", "jpg", "jpeg", "tiff", "tif",
    "tex", "rtf", "epub",
}


class FormatRouter:
    """Routes files to the appropriate processor by extension.

    Text/code files use simple passthrough (no ML needed).
    All other formats are processed by Docling via the inference service.
    """

    @staticmethod
    def get_route(file_path: str) -> str:
        """Determine processing route for a file.

        Returns:
            "text" for text passthrough, "code" for code files, "docling" for everything else.
        """
        ext = Path(file_path).suffix.lstrip(".").lower()

        if ext in TEXT_PASSTHROUGH_EXTENSIONS:
            return "text"
        if ext in CODE_EXTENSIONS:
            return "code"
        if ext in DOCLING_EXTENSIONS:
            return "docling"

        # Default to docling for unknown formats
        return "docling"

    @staticmethod
    def is_supported(file_path: str) -> bool:
        """Check if a file format is supported."""
        ext = Path(file_path).suffix.lstrip(".").lower()
        return ext in (TEXT_PASSTHROUGH_EXTENSIONS | CODE_EXTENSIONS | DOCLING_EXTENSIONS)
