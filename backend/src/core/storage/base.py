"""Base storage backend interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator


@dataclass
class StorageFile:
    """Represents a file in storage."""

    key: str  # S3 key or local path
    size: int
    content_type: str
    last_modified: datetime
    etag: str | None = None
    metadata: dict | None = None

    @property
    def filename(self) -> str:
        """Extract filename from key."""
        return self.key.split("/")[-1]


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """
        Save content to storage.

        Args:
            key: Storage key (path)
            content: File content as bytes
            content_type: MIME type
            metadata: Optional metadata dict

        Returns:
            The storage URI (s3:// or file://)
        """
        pass

    @abstractmethod
    async def get(self, key: str) -> bytes:
        """
        Get file content from storage.

        Args:
            key: Storage key

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a file from storage.

        Args:
            key: Storage key

        Returns:
            True if deleted, False if didn't exist
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a file exists.

        Args:
            key: Storage key

        Returns:
            True if exists
        """
        pass

    @abstractmethod
    async def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """
        List files in storage.

        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of results

        Returns:
            List of StorageFile objects
        """
        pass

    @abstractmethod
    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Get a URL for accessing the file.

        Args:
            key: Storage key
            expires_in: URL expiration in seconds (for signed URLs)

        Returns:
            URL string
        """
        pass

    @abstractmethod
    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """
        Stream file content in chunks.

        Args:
            key: Storage key
            chunk_size: Chunk size in bytes

        Yields:
            Chunks of file content
        """
        pass

    async def copy(self, source_key: str, dest_key: str) -> str:
        """
        Copy a file within storage.

        Default implementation: download and re-upload.
        Override for more efficient native copy.
        """
        content = await self.get(source_key)
        return await self.save(dest_key, content)

    async def move(self, source_key: str, dest_key: str) -> str:
        """
        Move a file within storage.

        Default implementation: copy and delete.
        Override for more efficient native move.
        """
        uri = await self.copy(source_key, dest_key)
        await self.delete(source_key)
        return uri

    def build_key(
        self,
        *path_parts: str,
    ) -> str:
        """
        Build a storage key from path components.

        Args:
            *path_parts: Path components

        Returns:
            Full storage key
        """
        parts = [str(p) for p in path_parts]
        return "/".join(parts)
