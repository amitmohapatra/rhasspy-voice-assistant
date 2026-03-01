"""Storage backend factory."""

from __future__ import annotations

from functools import lru_cache

from src.core.config import settings
from src.core.storage.base import StorageBackend
from src.core.storage.local import LocalStorageBackend


def get_storage_backend() -> StorageBackend:
    """
    Get the configured storage backend.

    Supported storage types:
    - "local"      : Local filesystem (development default)
    - "s3"         : AWS S3 or LocalStack emulation
    - "azure_blob" : Azure Blob Storage or Azurite emulation
    - "gcs"        : Google Cloud Storage or fake-gcs-server emulation
    """
    if settings.storage_type == "s3":
        from src.core.storage.s3 import S3StorageBackend

        if not settings.s3_bucket:
            raise ValueError(
                "S3_BUCKET must be set when STORAGE_TYPE=s3. "
                "For local development, use LocalStack with S3_ENDPOINT_URL=http://localhost:4566"
            )

        return S3StorageBackend(
            bucket=settings.s3_bucket,
            region=settings.aws_region,
            access_key_id=settings.aws_access_key_id,
            secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            use_ssl=settings.s3_use_ssl,
        )

    elif settings.storage_type == "azure_blob":
        from src.core.storage.azure_blob import AzureBlobStorageBackend

        if not settings.azure_storage_container:
            raise ValueError(
                "AZURE_STORAGE_CONTAINER must be set when STORAGE_TYPE=azure_blob. "
                "For local development, use Azurite with AZURE_STORAGE_CONNECTION_STRING."
            )

        return AzureBlobStorageBackend(
            container_name=settings.azure_storage_container,
            connection_string=settings.azure_storage_connection_string,
            account_name=settings.azure_storage_account_name,
            account_key=settings.azure_storage_account_key,
            endpoint_url=settings.azure_storage_endpoint_url,
        )

    elif settings.storage_type == "gcs":
        from src.core.storage.gcs import GCSStorageBackend

        if not settings.gcp_storage_bucket:
            raise ValueError(
                "GCP_STORAGE_BUCKET must be set when STORAGE_TYPE=gcs. "
                "For local development, use fake-gcs-server with GCP_STORAGE_ENDPOINT_URL."
            )

        return GCSStorageBackend(
            bucket_name=settings.gcp_storage_bucket,
            project_id=settings.gcp_project_id,
            credentials_json=settings.gcp_credentials_json,
            endpoint_url=settings.gcp_storage_endpoint_url,
        )

    elif settings.storage_type == "local":
        return LocalStorageBackend(base_path=settings.storage_path)

    else:
        raise ValueError(
            f"Unknown storage type: {settings.storage_type}. "
            "Use 'local', 's3', 'azure_blob', or 'gcs'."
        )


# Singleton instance
@lru_cache(maxsize=1)
def _get_cached_storage() -> StorageBackend:
    """Get cached storage backend instance."""
    return get_storage_backend()


# Default storage instance (lazy-loaded singleton)
class _StorageProxy:
    """Lazy proxy for storage backend."""

    _instance: StorageBackend | None = None

    def _get_backend(self) -> StorageBackend:
        if self._instance is None:
            self._instance = get_storage_backend()
        return self._instance

    def __getattr__(self, name):
        return getattr(self._get_backend(), name)


storage = _StorageProxy()
