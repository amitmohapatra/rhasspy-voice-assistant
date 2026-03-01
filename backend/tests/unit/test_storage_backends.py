"""Unit tests for storage backends with mocked cloud clients."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.core.storage.base import StorageBackend, StorageFile


# =============================================================================
# Factory Tests
# =============================================================================


class TestStorageFactory:
    """Test storage backend factory routing."""

    def test_local_storage_default(self):
        """Factory returns LocalStorageBackend by default."""
        with patch("src.core.storage.factory.settings") as mock_settings:
            mock_settings.storage_type = "local"
            mock_settings.storage_path = "/tmp/test-storage"

            from src.core.storage.factory import get_storage_backend
            from src.core.storage.local import LocalStorageBackend

            backend = get_storage_backend()
            assert isinstance(backend, LocalStorageBackend)

    def test_s3_storage_requires_bucket(self):
        """Factory raises ValueError when S3 bucket is missing."""
        with patch("src.core.storage.factory.settings") as mock_settings:
            mock_settings.storage_type = "s3"
            mock_settings.s3_bucket = None

            from src.core.storage.factory import get_storage_backend

            with pytest.raises(ValueError, match="S3_BUCKET must be set"):
                get_storage_backend()

    def test_azure_storage_requires_container(self):
        """Factory raises ValueError when Azure container is missing."""
        with patch("src.core.storage.factory.settings") as mock_settings:
            mock_settings.storage_type = "azure_blob"
            mock_settings.azure_storage_container = None

            from src.core.storage.factory import get_storage_backend

            with pytest.raises(ValueError, match="AZURE_STORAGE_CONTAINER must be set"):
                get_storage_backend()

    def test_gcs_storage_requires_bucket(self):
        """Factory raises ValueError when GCS bucket is missing."""
        with patch("src.core.storage.factory.settings") as mock_settings:
            mock_settings.storage_type = "gcs"
            mock_settings.gcp_storage_bucket = None

            from src.core.storage.factory import get_storage_backend

            with pytest.raises(ValueError, match="GCP_STORAGE_BUCKET must be set"):
                get_storage_backend()

    def test_unknown_storage_type(self):
        """Factory raises ValueError for unknown storage type."""
        with patch("src.core.storage.factory.settings") as mock_settings:
            mock_settings.storage_type = "unknown"

            from src.core.storage.factory import get_storage_backend

            with pytest.raises(ValueError, match="Unknown storage type"):
                get_storage_backend()


# =============================================================================
# Azure Blob Storage Backend Tests
# =============================================================================


class TestAzureBlobStorageBackend:
    """Unit tests for AzureBlobStorageBackend with mocked Azure SDK."""

    @pytest.fixture
    def mock_azure(self):
        """Create mocked Azure Blob service client."""
        with patch("src.core.storage.azure_blob.AzureBlobStorageBackend.__init__", return_value=None) as _:
            from src.core.storage.azure_blob import AzureBlobStorageBackend

            backend = AzureBlobStorageBackend.__new__(AzureBlobStorageBackend)
            backend.container_name = "test-container"
            backend.endpoint_url = None
            backend._is_emulator = False
            backend._service_client = MagicMock()
            backend._container_client = MagicMock()

            from concurrent.futures import ThreadPoolExecutor
            backend._executor = ThreadPoolExecutor(max_workers=2)

            yield backend

    @pytest.mark.asyncio
    async def test_save(self, mock_azure):
        """Test saving content to Azure Blob."""
        blob_client = MagicMock()
        mock_azure._container_client.get_blob_client.return_value = blob_client

        result = await mock_azure.save(
            "test/file.txt", b"hello world", content_type="text/plain"
        )

        assert result == "azure://test-container/test/file.txt"
        blob_client.upload_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_get(self, mock_azure):
        """Test getting content from Azure Blob."""
        blob_client = MagicMock()
        download_stream = MagicMock()
        download_stream.readall.return_value = b"hello world"
        blob_client.download_blob.return_value = download_stream
        mock_azure._container_client.get_blob_client.return_value = blob_client

        result = await mock_azure.get("test/file.txt")
        assert result == b"hello world"

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_azure):
        """Test getting non-existent blob raises FileNotFoundError."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = MagicMock()
        blob_client.download_blob.side_effect = ResourceNotFoundError("Not found")
        mock_azure._container_client.get_blob_client.return_value = blob_client

        with pytest.raises(FileNotFoundError):
            await mock_azure.get("nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_delete(self, mock_azure):
        """Test deleting a blob."""
        blob_client = MagicMock()
        mock_azure._container_client.get_blob_client.return_value = blob_client

        result = await mock_azure.delete("test/file.txt")
        assert result is True
        blob_client.delete_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_azure):
        """Test deleting non-existent blob returns False."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = MagicMock()
        blob_client.delete_blob.side_effect = ResourceNotFoundError("Not found")
        mock_azure._container_client.get_blob_client.return_value = blob_client

        result = await mock_azure.delete("nonexistent/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_azure):
        """Test checking existence of existing blob."""
        blob_client = MagicMock()
        mock_azure._container_client.get_blob_client.return_value = blob_client

        result = await mock_azure.exists("test/file.txt")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, mock_azure):
        """Test checking existence of non-existent blob."""
        from azure.core.exceptions import ResourceNotFoundError

        blob_client = MagicMock()
        blob_client.get_blob_properties.side_effect = ResourceNotFoundError("Not found")
        mock_azure._container_client.get_blob_client.return_value = blob_client

        result = await mock_azure.exists("nonexistent/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_url_emulator(self, mock_azure):
        """Test URL generation in emulator mode."""
        mock_azure._is_emulator = True
        mock_azure._service_client.url = "http://azurite:10000/devstoreaccount1/"

        url = await mock_azure.get_url("test/file.txt")
        assert "test-container/test/file.txt" in url

    @pytest.mark.asyncio
    async def test_create_container_if_not_exists(self, mock_azure):
        """Test creating container when it doesn't exist."""
        result = await mock_azure.create_container_if_not_exists()
        assert result is True
        mock_azure._container_client.create_container.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_container_already_exists(self, mock_azure):
        """Test creating container when it already exists."""
        from azure.core.exceptions import ResourceExistsError

        mock_azure._container_client.create_container.side_effect = ResourceExistsError("Exists")

        result = await mock_azure.create_container_if_not_exists()
        assert result is False


# =============================================================================
# GCS Storage Backend Tests
# =============================================================================


class TestGCSStorageBackend:
    """Unit tests for GCSStorageBackend with mocked GCS SDK."""

    @pytest.fixture
    def mock_gcs(self):
        """Create mocked GCS client."""
        with patch("src.core.storage.gcs.GCSStorageBackend.__init__", return_value=None) as _:
            from src.core.storage.gcs import GCSStorageBackend

            backend = GCSStorageBackend.__new__(GCSStorageBackend)
            backend.bucket_name = "test-bucket"
            backend.project_id = "test-project"
            backend.endpoint_url = None
            backend._is_emulator = False
            backend._client = MagicMock()
            backend._bucket = MagicMock()

            from concurrent.futures import ThreadPoolExecutor
            backend._executor = ThreadPoolExecutor(max_workers=2)

            yield backend

    @pytest.mark.asyncio
    async def test_save(self, mock_gcs):
        """Test saving content to GCS."""
        blob = MagicMock()
        mock_gcs._bucket.blob.return_value = blob

        result = await mock_gcs.save(
            "test/file.txt", b"hello world", content_type="text/plain"
        )

        assert result == "gs://test-bucket/test/file.txt"
        blob.upload_from_string.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_with_metadata(self, mock_gcs):
        """Test saving content with metadata."""
        blob = MagicMock()
        mock_gcs._bucket.blob.return_value = blob

        await mock_gcs.save(
            "test/file.txt",
            b"hello world",
            metadata={"author": "test"},
        )

        assert blob.metadata == {"author": "test"}

    @pytest.mark.asyncio
    async def test_get(self, mock_gcs):
        """Test getting content from GCS."""
        blob = MagicMock()
        blob.download_as_bytes.return_value = b"hello world"
        mock_gcs._bucket.blob.return_value = blob

        result = await mock_gcs.get("test/file.txt")
        assert result == b"hello world"

    @pytest.mark.asyncio
    async def test_get_not_found(self, mock_gcs):
        """Test getting non-existent blob raises FileNotFoundError."""
        from google.api_core.exceptions import NotFound

        blob = MagicMock()
        blob.download_as_bytes.side_effect = NotFound("Not found")
        mock_gcs._bucket.blob.return_value = blob

        with pytest.raises(FileNotFoundError):
            await mock_gcs.get("nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_delete(self, mock_gcs):
        """Test deleting a blob."""
        blob = MagicMock()
        mock_gcs._bucket.blob.return_value = blob

        result = await mock_gcs.delete("test/file.txt")
        assert result is True
        blob.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, mock_gcs):
        """Test deleting non-existent blob returns False."""
        from google.api_core.exceptions import NotFound

        blob = MagicMock()
        blob.delete.side_effect = NotFound("Not found")
        mock_gcs._bucket.blob.return_value = blob

        result = await mock_gcs.delete("nonexistent/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_gcs):
        """Test checking existence of existing blob."""
        blob = MagicMock()
        blob.exists.return_value = True
        mock_gcs._bucket.blob.return_value = blob

        result = await mock_gcs.exists("test/file.txt")
        assert result is True

    @pytest.mark.asyncio
    async def test_exists_false(self, mock_gcs):
        """Test checking existence of non-existent blob."""
        blob = MagicMock()
        blob.exists.return_value = False
        mock_gcs._bucket.blob.return_value = blob

        result = await mock_gcs.exists("nonexistent/file.txt")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_url_emulator(self, mock_gcs):
        """Test URL generation in emulator mode."""
        mock_gcs._is_emulator = True
        mock_gcs.endpoint_url = "http://localhost:4443"

        url = await mock_gcs.get_url("test/file.txt")
        assert "test-bucket" in url
        assert "test/file.txt" in url
        assert url.startswith("http://localhost:4443")

    @pytest.mark.asyncio
    async def test_copy(self, mock_gcs):
        """Test server-side copy within bucket."""
        source_blob = MagicMock()
        mock_gcs._bucket.blob.return_value = source_blob

        result = await mock_gcs.copy("source/file.txt", "dest/file.txt")
        assert result == "gs://test-bucket/dest/file.txt"
        mock_gcs._bucket.copy_blob.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bucket_if_not_exists(self, mock_gcs):
        """Test creating bucket when it doesn't exist."""
        result = await mock_gcs.create_bucket_if_not_exists()
        assert result is True
        mock_gcs._client.create_bucket.assert_called_once_with("test-bucket")

    @pytest.mark.asyncio
    async def test_create_bucket_already_exists(self, mock_gcs):
        """Test creating bucket when it already exists."""
        from google.api_core.exceptions import Conflict

        mock_gcs._client.create_bucket.side_effect = Conflict("Exists")

        result = await mock_gcs.create_bucket_if_not_exists()
        assert result is False


# =============================================================================
# S3 Storage Backend Tests
# =============================================================================


class TestS3StorageBackend:
    """Unit tests for S3StorageBackend with mocked boto3."""

    @pytest.fixture
    def mock_s3(self):
        """Create mocked S3 backend."""
        with patch("src.core.storage.s3.S3StorageBackend.__init__", return_value=None) as _:
            from src.core.storage.s3 import S3StorageBackend

            backend = S3StorageBackend.__new__(S3StorageBackend)
            backend.bucket = "test-bucket"
            backend.region = "us-east-1"
            backend.endpoint_url = None
            backend._client = MagicMock()

            from concurrent.futures import ThreadPoolExecutor
            backend._executor = ThreadPoolExecutor(max_workers=2)

            yield backend

    @pytest.mark.asyncio
    async def test_save(self, mock_s3):
        """Test saving content to S3."""
        result = await mock_s3.save(
            "test/file.txt", b"hello world", content_type="text/plain"
        )

        assert result == "s3://test-bucket/test/file.txt"
        mock_s3._client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_get(self, mock_s3):
        """Test getting content from S3."""
        body = MagicMock()
        body.read.return_value = b"hello world"
        mock_s3._client.get_object.return_value = {"Body": body}

        result = await mock_s3.get("test/file.txt")
        assert result == b"hello world"

    @pytest.mark.asyncio
    async def test_exists_true(self, mock_s3):
        """Test checking existence of existing S3 object."""
        result = await mock_s3.exists("test/file.txt")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete(self, mock_s3):
        """Test deleting from S3."""
        result = await mock_s3.delete("test/file.txt")
        assert result is True
        mock_s3._client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bucket_if_not_exists(self, mock_s3):
        """Test bucket creation when it doesn't exist."""
        from botocore.exceptions import ClientError

        mock_s3._client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404"}}, "HeadBucket"
        )

        result = await mock_s3.create_bucket_if_not_exists()
        assert result is True
        mock_s3._client.create_bucket.assert_called_once()
