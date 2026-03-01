"""Local filesystem storage backend."""

from __future__ import annotations

import aiofiles
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from src.core.storage.base import StorageBackend, StorageFile


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend.

    Used for development and testing.
    """

    def __init__(self, base_path: str = "./storage"):
        """
        Initialize local storage.

        Args:
            base_path: Base directory for file storage
        """
        self.base_path = Path(base_path).resolve()
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key."""
        # Sanitize key to prevent directory traversal
        clean_key = key.lstrip("/").replace("..", "")
        return self.base_path / clean_key

    async def save(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Save content to local filesystem."""
        path = self._get_full_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(path, "wb") as f:
            await f.write(content)

        # Store metadata in a sidecar file if provided
        if metadata:
            import json

            meta_path = path.with_suffix(path.suffix + ".meta.json")
            async with aiofiles.open(meta_path, "w") as f:
                await f.write(
                    json.dumps(
                        {
                            "content_type": content_type,
                            "metadata": metadata,
                        }
                    )
                )

        return f"file://{path}"

    async def get(self, key: str) -> bytes:
        """Get file content from local filesystem."""
        path = self._get_full_path(key)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def delete(self, key: str) -> bool:
        """Delete a file from local filesystem."""
        path = self._get_full_path(key)

        if not path.exists():
            return False

        path.unlink()

        # Also delete metadata file if exists
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if meta_path.exists():
            meta_path.unlink()

        return True

    async def exists(self, key: str) -> bool:
        """Check if a file exists."""
        path = self._get_full_path(key)
        return path.exists()

    async def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """List files in local storage."""
        search_path = self._get_full_path(prefix) if prefix else self.base_path

        if not search_path.exists():
            return []

        files = []
        count = 0

        for path in search_path.rglob("*"):
            if count >= max_keys:
                break

            if path.is_file() and not path.name.endswith(".meta.json"):
                # Get relative key
                rel_path = path.relative_to(self.base_path)
                stat = path.stat()

                files.append(
                    StorageFile(
                        key=str(rel_path),
                        size=stat.st_size,
                        content_type=self._guess_content_type(path),
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                    )
                )
                count += 1

        return files

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Get a file:// URL for local files."""
        path = self._get_full_path(key)
        return f"file://{path}"

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content in chunks."""
        path = self._get_full_path(key)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        async with aiofiles.open(path, "rb") as f:
            while chunk := await f.read(chunk_size):
                yield chunk

    def _guess_content_type(self, path: Path) -> str:
        """Guess content type from file extension."""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(str(path))
        return mime_type or "application/octet-stream"
