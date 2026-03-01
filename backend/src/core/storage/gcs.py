"""Google Cloud Storage backend."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import AsyncIterator

from src.core.storage.base import StorageBackend, StorageFile


class GCSStorageBackend(StorageBackend):
    """
    Google Cloud Storage backend.

    Supports:
    - Google Cloud Storage (production)
    - fake-gcs-server emulator (local development)
    """

    def __init__(
        self,
        bucket_name: str,
        project_id: str | None = None,
        credentials_json: str | None = None,
        endpoint_url: str | None = None,
    ):
        """
        Initialize GCS storage.

        Args:
            bucket_name: GCS bucket name
            project_id: GCP project ID
            credentials_json: Path to service account JSON file
            endpoint_url: Custom endpoint for fake-gcs-server emulator
        """
        from google.cloud import storage

        self.bucket_name = bucket_name
        self.project_id = project_id
        self.endpoint_url = endpoint_url
        self._is_emulator = endpoint_url is not None

        if self._is_emulator:
            from google.auth.credentials import AnonymousCredentials

            self._client = storage.Client(
                credentials=AnonymousCredentials(),
                project=project_id or "test-project",
            )
            # Override the API endpoint for the emulator
            self._client._connection.API_BASE_URL = endpoint_url
        elif credentials_json:
            self._client = storage.Client.from_service_account_json(
                credentials_json, project=project_id
            )
        else:
            # Use Application Default Credentials
            self._client = storage.Client(project=project_id)

        self._bucket = self._client.bucket(bucket_name)
        self._executor = ThreadPoolExecutor(max_workers=10)

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous GCS SDK call in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor, partial(func, *args, **kwargs)
        )

    async def save(
        self,
        key: str,
        content: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Save content to GCS."""
        blob = self._bucket.blob(key)
        blob.content_type = content_type

        if metadata:
            blob.metadata = {str(k): str(v) for k, v in metadata.items()}

        await self._run_sync(blob.upload_from_string, content, content_type=content_type)

        return f"gs://{self.bucket_name}/{key}"

    async def get(self, key: str) -> bytes:
        """Get file content from GCS."""
        from google.api_core.exceptions import NotFound

        blob = self._bucket.blob(key)

        try:
            return await self._run_sync(blob.download_as_bytes)
        except NotFound:
            raise FileNotFoundError(f"File not found: {key}")

    async def delete(self, key: str) -> bool:
        """Delete a file from GCS."""
        from google.api_core.exceptions import NotFound

        blob = self._bucket.blob(key)

        try:
            await self._run_sync(blob.delete)
            return True
        except NotFound:
            return False

    async def exists(self, key: str) -> bool:
        """Check if a file exists in GCS."""
        blob = self._bucket.blob(key)
        return await self._run_sync(blob.exists)

    async def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """List files in GCS bucket."""
        files = []

        list_kwargs = {"max_results": max_keys}
        if prefix:
            list_kwargs["prefix"] = prefix

        blobs = await self._run_sync(self._client.list_blobs, self.bucket_name, **list_kwargs)

        for blob in blobs:
            if len(files) >= max_keys:
                break
            files.append(
                StorageFile(
                    key=blob.name,
                    size=blob.size or 0,
                    content_type=blob.content_type
                    or self._get_content_type(blob.name),
                    last_modified=blob.updated or datetime.utcnow(),
                    etag=blob.etag.strip('"') if blob.etag else None,
                )
            )

        return files

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Get a URL for the GCS object. Returns direct URL in emulator, signed URL in production."""
        if self._is_emulator:
            return f"{self.endpoint_url}/storage/v1/b/{self.bucket_name}/o/{key}?alt=media"

        from datetime import timedelta

        blob = self._bucket.blob(key)
        url = await self._run_sync(
            blob.generate_signed_url,
            expiration=timedelta(seconds=expires_in),
            method="GET",
        )
        return url

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content from GCS in chunks."""
        from google.api_core.exceptions import NotFound

        blob = self._bucket.blob(key)

        try:
            content = await self._run_sync(blob.download_as_bytes)
            # Yield in chunks
            for i in range(0, len(content), chunk_size):
                yield content[i : i + chunk_size]
        except NotFound:
            raise FileNotFoundError(f"File not found: {key}")

    async def copy(self, source_key: str, dest_key: str) -> str:
        """Copy a blob within the bucket (server-side copy)."""
        source_blob = self._bucket.blob(source_key)

        await self._run_sync(
            self._bucket.copy_blob, source_blob, self._bucket, dest_key
        )

        return f"gs://{self.bucket_name}/{dest_key}"

    async def get_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
    ) -> str:
        """Get a signed URL for direct upload to GCS."""
        if self._is_emulator:
            return f"{self.endpoint_url}/storage/v1/b/{self.bucket_name}/o?uploadType=media&name={key}"

        from datetime import timedelta

        blob = self._bucket.blob(key)
        url = await self._run_sync(
            blob.generate_signed_url,
            expiration=timedelta(seconds=expires_in),
            method="PUT",
            content_type=content_type,
        )
        return url

    async def create_bucket_if_not_exists(self) -> bool:
        """Create the bucket if it doesn't exist (useful for emulator)."""
        from google.api_core.exceptions import Conflict

        try:
            await self._run_sync(self._client.create_bucket, self.bucket_name)
            return True
        except Conflict:
            return False  # Already exists

    def _get_content_type(self, key: str) -> str:
        """Guess content type from key extension."""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(key)
        return mime_type or "application/octet-stream"
