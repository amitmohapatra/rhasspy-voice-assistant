"""Azure Blob Storage backend."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from functools import partial
from typing import AsyncIterator

from src.core.storage.base import StorageBackend, StorageFile

# Well-known Azurite development connection string
AZURITE_CONNECTION_STRING = (
    "DefaultEndpointsProtocol=http;"
    "AccountName=devstoreaccount1;"
    "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
    "K1SZFPTOtr/KBHBeksoGMGw==;"
    "BlobEndpoint=http://azurite:10000/devstoreaccount1;"
    "QueueEndpoint=http://azurite:10001/devstoreaccount1;"
    "TableEndpoint=http://azurite:10002/devstoreaccount1;"
)


class AzureBlobStorageBackend(StorageBackend):
    """
    Azure Blob Storage backend.

    Supports:
    - Azure Blob Storage (production)
    - Azurite emulator (local development)
    """

    def __init__(
        self,
        container_name: str,
        connection_string: str | None = None,
        account_name: str | None = None,
        account_key: str | None = None,
        endpoint_url: str | None = None,
    ):
        """
        Initialize Azure Blob storage.

        Args:
            container_name: Azure Blob container name
            connection_string: Full connection string (preferred)
            account_name: Storage account name (alternative to connection_string)
            account_key: Storage account key (used with account_name)
            endpoint_url: Custom endpoint for Azurite emulator
        """
        from azure.storage.blob import BlobServiceClient

        self.container_name = container_name
        self.endpoint_url = endpoint_url
        self._is_emulator = endpoint_url is not None or (
            connection_string is not None and "devstoreaccount1" in connection_string
        )

        if connection_string:
            self._service_client = BlobServiceClient.from_connection_string(
                connection_string
            )
        elif account_name and account_key:
            if endpoint_url:
                self._service_client = BlobServiceClient(
                    account_url=endpoint_url,
                    credential=account_key,
                )
            else:
                self._service_client = BlobServiceClient(
                    account_url=f"https://{account_name}.blob.core.windows.net",
                    credential=account_key,
                )
        elif account_name and not account_key:
            # Use DefaultAzureCredential for managed identity / AAD auth
            from azure.identity import DefaultAzureCredential

            self._service_client = BlobServiceClient(
                account_url=f"https://{account_name}.blob.core.windows.net",
                credential=DefaultAzureCredential(),
            )
        else:
            raise ValueError(
                "Provide either connection_string, or account_name + account_key, "
                "or account_name alone (for DefaultAzureCredential)."
            )

        self._container_client = self._service_client.get_container_client(
            container_name
        )
        self._executor = ThreadPoolExecutor(max_workers=10)

    async def _run_sync(self, func, *args, **kwargs):
        """Run synchronous Azure SDK call in thread pool."""
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
        """Save content to Azure Blob Storage."""
        from azure.storage.blob import ContentSettings

        blob_client = self._container_client.get_blob_client(key)

        upload_kwargs = {
            "data": content,
            "overwrite": True,
            "content_settings": ContentSettings(content_type=content_type),
        }

        if metadata:
            upload_kwargs["metadata"] = {
                str(k): str(v) for k, v in metadata.items()
            }

        await self._run_sync(blob_client.upload_blob, **upload_kwargs)

        return f"azure://{self.container_name}/{key}"

    async def get(self, key: str) -> bytes:
        """Get file content from Azure Blob Storage."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = self._container_client.get_blob_client(key)

        try:
            download_stream = await self._run_sync(blob_client.download_blob)
            return download_stream.readall()
        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {key}")

    async def delete(self, key: str) -> bool:
        """Delete a file from Azure Blob Storage."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = self._container_client.get_blob_client(key)

        try:
            await self._run_sync(blob_client.delete_blob)
            return True
        except ResourceNotFoundError:
            return False

    async def exists(self, key: str) -> bool:
        """Check if a file exists in Azure Blob Storage."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = self._container_client.get_blob_client(key)

        try:
            await self._run_sync(blob_client.get_blob_properties)
            return True
        except ResourceNotFoundError:
            return False

    async def list(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[StorageFile]:
        """List files in Azure Blob container."""
        files = []

        list_kwargs = {}
        if prefix:
            list_kwargs["name_starts_with"] = prefix

        blobs = await self._run_sync(
            self._container_client.list_blobs, **list_kwargs
        )

        for blob in blobs:
            if len(files) >= max_keys:
                break
            files.append(
                StorageFile(
                    key=blob.name,
                    size=blob.size,
                    content_type=blob.content_settings.content_type
                    or self._get_content_type(blob.name),
                    last_modified=blob.last_modified or datetime.utcnow(),
                    etag=blob.etag.strip('"') if blob.etag else None,
                )
            )

        return files

    async def get_url(
        self,
        key: str,
        expires_in: int = 3600,
    ) -> str:
        """Get a URL for the blob. Returns SAS URL in production, direct URL in emulator."""
        if self._is_emulator:
            # Azurite: return direct URL without SAS token
            account_url = self._service_client.url
            return f"{account_url}{self.container_name}/{key}"

        # Production: generate SAS URL
        from datetime import timezone, timedelta

        from azure.storage.blob import generate_blob_sas, BlobSasPermissions

        blob_client = self._container_client.get_blob_client(key)
        account_name = self._service_client.account_name

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.container_name,
            blob_name=key,
            account_key=self._service_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )

        return f"{blob_client.url}?{sas_token}"

    async def stream(self, key: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file content from Azure Blob Storage in chunks."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = self._container_client.get_blob_client(key)

        try:
            download_stream = await self._run_sync(blob_client.download_blob)
            chunks_iter = download_stream.chunks()

            for chunk in chunks_iter:
                yield chunk

        except ResourceNotFoundError:
            raise FileNotFoundError(f"File not found: {key}")

    async def copy(self, source_key: str, dest_key: str) -> str:
        """Copy a blob within the container (server-side copy)."""
        source_blob = self._container_client.get_blob_client(source_key)
        dest_blob = self._container_client.get_blob_client(dest_key)

        await self._run_sync(
            dest_blob.start_copy_from_url, source_blob.url
        )

        return f"azure://{self.container_name}/{dest_key}"

    async def get_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600,
    ) -> str:
        """Get a SAS URL for direct upload to Azure Blob Storage."""
        if self._is_emulator:
            account_url = self._service_client.url
            return f"{account_url}{self.container_name}/{key}"

        from datetime import timezone, timedelta

        from azure.storage.blob import generate_blob_sas, BlobSasPermissions

        account_name = self._service_client.account_name

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=self.container_name,
            blob_name=key,
            account_key=self._service_client.credential.account_key,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in),
        )

        blob_client = self._container_client.get_blob_client(key)
        return f"{blob_client.url}?{sas_token}"

    async def create_container_if_not_exists(self) -> bool:
        """Create the container if it doesn't exist (useful for Azurite)."""
        from azure.core.exceptions import ResourceExistsError

        try:
            await self._run_sync(self._container_client.create_container)
            return True
        except ResourceExistsError:
            return False  # Already exists

    def _get_content_type(self, key: str) -> str:
        """Guess content type from key extension."""
        import mimetypes

        mime_type, _ = mimetypes.guess_type(key)
        return mime_type or "application/octet-stream"
