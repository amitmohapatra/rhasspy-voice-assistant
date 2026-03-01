"""Integration tests for storage backends against real emulators.

These tests require running emulators:
- LocalStack for S3 (docker compose --profile aws up)
- Azurite for Azure Blob (docker compose --profile azure up)
- fake-gcs-server for GCS (docker compose --profile gcp up)

Run with: pytest tests/integration/test_storage_integration.py -v
"""

from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio


# =============================================================================
# S3 Integration Tests (LocalStack)
# =============================================================================


@pytest.mark.integration
class TestS3Integration:
    """Integration tests for S3 backend against LocalStack."""

    @pytest_asyncio.fixture
    async def s3_backend(self):
        from src.core.storage.s3 import S3StorageBackend

        backend = S3StorageBackend(
            bucket=f"test-{uuid.uuid4().hex[:8]}",
            region="us-east-1",
            access_key_id="test",
            secret_access_key="test",
            endpoint_url=os.getenv("S3_ENDPOINT_URL", "http://localhost:4566"),
            use_ssl=False,
        )
        await backend.create_bucket_if_not_exists()
        yield backend

    @pytest.mark.asyncio
    async def test_roundtrip(self, s3_backend):
        """Test save, get, exists, delete cycle."""
        key = f"test/{uuid.uuid4().hex}.txt"
        content = b"hello from S3 integration test"

        # Save
        uri = await s3_backend.save(key, content, content_type="text/plain")
        assert uri.startswith("s3://")

        # Exists
        assert await s3_backend.exists(key) is True

        # Get
        result = await s3_backend.get(key)
        assert result == content

        # Delete
        assert await s3_backend.delete(key) is True
        assert await s3_backend.exists(key) is False

    @pytest.mark.asyncio
    async def test_list(self, s3_backend):
        """Test listing objects with prefix."""
        prefix = f"list-test/{uuid.uuid4().hex[:8]}"

        for i in range(3):
            await s3_backend.save(f"{prefix}/file{i}.txt", f"content {i}".encode())

        files = await s3_backend.list(prefix=prefix)
        assert len(files) == 3

    @pytest.mark.asyncio
    async def test_copy(self, s3_backend):
        """Test server-side copy."""
        src_key = f"copy-test/{uuid.uuid4().hex}.txt"
        dst_key = f"copy-test/{uuid.uuid4().hex}-copy.txt"

        await s3_backend.save(src_key, b"copy me")
        await s3_backend.copy(src_key, dst_key)

        assert await s3_backend.exists(dst_key) is True
        assert await s3_backend.get(dst_key) == b"copy me"

    @pytest.mark.asyncio
    async def test_get_url(self, s3_backend):
        """Test presigned URL generation."""
        key = f"url-test/{uuid.uuid4().hex}.txt"
        await s3_backend.save(key, b"url content")

        url = await s3_backend.get_url(key)
        assert "http" in url

    @pytest.mark.asyncio
    async def test_stream(self, s3_backend):
        """Test streaming download."""
        key = f"stream-test/{uuid.uuid4().hex}.txt"
        content = b"x" * 16384  # 16KB
        await s3_backend.save(key, content)

        chunks = []
        async for chunk in s3_backend.stream(key, chunk_size=4096):
            chunks.append(chunk)

        assert b"".join(chunks) == content

    @pytest.mark.asyncio
    async def test_get_not_found(self, s3_backend):
        """Test FileNotFoundError for missing objects."""
        with pytest.raises(FileNotFoundError):
            await s3_backend.get(f"nonexistent/{uuid.uuid4().hex}")

    @pytest.mark.asyncio
    async def test_metadata(self, s3_backend):
        """Test saving with metadata."""
        key = f"meta-test/{uuid.uuid4().hex}.txt"
        await s3_backend.save(
            key, b"metadata content", metadata={"author": "test", "version": "1"}
        )

        assert await s3_backend.exists(key) is True


# =============================================================================
# Azure Blob Integration Tests (Azurite)
# =============================================================================


@pytest.mark.integration
class TestAzureBlobIntegration:
    """Integration tests for Azure Blob backend against Azurite."""

    @pytest_asyncio.fixture
    async def azure_backend(self):
        try:
            from src.core.storage.azure_blob import AzureBlobStorageBackend
        except ImportError:
            pytest.skip("azure-storage-blob not installed")

        connection_string = os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING",
            "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
            "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/"
            "K1SZFPTOtr/KBHBeksoGMGw==;"
            "BlobEndpoint=http://localhost:10000/devstoreaccount1;"
            "QueueEndpoint=http://localhost:10001/devstoreaccount1;"
            "TableEndpoint=http://localhost:10002/devstoreaccount1;",
        )

        backend = AzureBlobStorageBackend(
            container_name=f"test-{uuid.uuid4().hex[:8]}",
            connection_string=connection_string,
        )
        await backend.create_container_if_not_exists()
        yield backend

    @pytest.mark.asyncio
    async def test_roundtrip(self, azure_backend):
        """Test save, get, exists, delete cycle."""
        key = f"test/{uuid.uuid4().hex}.txt"
        content = b"hello from Azure integration test"

        uri = await azure_backend.save(key, content, content_type="text/plain")
        assert uri.startswith("azure://")

        assert await azure_backend.exists(key) is True

        result = await azure_backend.get(key)
        assert result == content

        assert await azure_backend.delete(key) is True
        assert await azure_backend.exists(key) is False

    @pytest.mark.asyncio
    async def test_list(self, azure_backend):
        """Test listing blobs with prefix."""
        prefix = f"list-test/{uuid.uuid4().hex[:8]}"

        for i in range(3):
            await azure_backend.save(
                f"{prefix}/file{i}.txt", f"content {i}".encode()
            )

        files = await azure_backend.list(prefix=prefix)
        assert len(files) == 3

    @pytest.mark.asyncio
    async def test_copy(self, azure_backend):
        """Test server-side copy."""
        src_key = f"copy-test/{uuid.uuid4().hex}.txt"
        dst_key = f"copy-test/{uuid.uuid4().hex}-copy.txt"

        await azure_backend.save(src_key, b"copy me")
        await azure_backend.copy(src_key, dst_key)

        assert await azure_backend.exists(dst_key) is True
        assert await azure_backend.get(dst_key) == b"copy me"

    @pytest.mark.asyncio
    async def test_get_url(self, azure_backend):
        """Test URL generation."""
        key = f"url-test/{uuid.uuid4().hex}.txt"
        await azure_backend.save(key, b"url content")

        url = await azure_backend.get_url(key)
        assert "http" in url

    @pytest.mark.asyncio
    async def test_stream(self, azure_backend):
        """Test streaming download."""
        key = f"stream-test/{uuid.uuid4().hex}.txt"
        content = b"x" * 16384
        await azure_backend.save(key, content)

        chunks = []
        async for chunk in azure_backend.stream(key, chunk_size=4096):
            chunks.append(chunk)

        assert b"".join(chunks) == content

    @pytest.mark.asyncio
    async def test_get_not_found(self, azure_backend):
        """Test FileNotFoundError for missing blobs."""
        with pytest.raises(FileNotFoundError):
            await azure_backend.get(f"nonexistent/{uuid.uuid4().hex}")

    @pytest.mark.asyncio
    async def test_metadata(self, azure_backend):
        """Test saving with metadata."""
        key = f"meta-test/{uuid.uuid4().hex}.txt"
        await azure_backend.save(
            key,
            b"metadata content",
            content_type="text/plain",
            metadata={"author": "test", "version": "1"},
        )
        assert await azure_backend.exists(key) is True


# =============================================================================
# GCS Integration Tests (fake-gcs-server)
# =============================================================================


@pytest.mark.integration
class TestGCSIntegration:
    """Integration tests for GCS backend against fake-gcs-server."""

    @pytest_asyncio.fixture
    async def gcs_backend(self):
        try:
            from src.core.storage.gcs import GCSStorageBackend
        except ImportError:
            pytest.skip("google-cloud-storage not installed")

        backend = GCSStorageBackend(
            bucket_name=f"test-{uuid.uuid4().hex[:8]}",
            project_id="test-project",
            endpoint_url=os.getenv(
                "GCP_STORAGE_ENDPOINT_URL", "http://localhost:4443"
            ),
        )
        await backend.create_bucket_if_not_exists()
        yield backend

    @pytest.mark.asyncio
    async def test_roundtrip(self, gcs_backend):
        """Test save, get, exists, delete cycle."""
        key = f"test/{uuid.uuid4().hex}.txt"
        content = b"hello from GCS integration test"

        uri = await gcs_backend.save(key, content, content_type="text/plain")
        assert uri.startswith("gs://")

        assert await gcs_backend.exists(key) is True

        result = await gcs_backend.get(key)
        assert result == content

        assert await gcs_backend.delete(key) is True
        assert await gcs_backend.exists(key) is False

    @pytest.mark.asyncio
    async def test_list(self, gcs_backend):
        """Test listing objects with prefix."""
        prefix = f"list-test/{uuid.uuid4().hex[:8]}"

        for i in range(3):
            await gcs_backend.save(f"{prefix}/file{i}.txt", f"content {i}".encode())

        files = await gcs_backend.list(prefix=prefix)
        assert len(files) == 3

    @pytest.mark.asyncio
    async def test_copy(self, gcs_backend):
        """Test server-side copy."""
        src_key = f"copy-test/{uuid.uuid4().hex}.txt"
        dst_key = f"copy-test/{uuid.uuid4().hex}-copy.txt"

        await gcs_backend.save(src_key, b"copy me")
        await gcs_backend.copy(src_key, dst_key)

        assert await gcs_backend.exists(dst_key) is True
        assert await gcs_backend.get(dst_key) == b"copy me"

    @pytest.mark.asyncio
    async def test_get_url(self, gcs_backend):
        """Test URL generation in emulator mode."""
        key = f"url-test/{uuid.uuid4().hex}.txt"
        await gcs_backend.save(key, b"url content")

        url = await gcs_backend.get_url(key)
        assert "http" in url

    @pytest.mark.asyncio
    async def test_stream(self, gcs_backend):
        """Test streaming download."""
        key = f"stream-test/{uuid.uuid4().hex}.txt"
        content = b"x" * 16384
        await gcs_backend.save(key, content)

        chunks = []
        async for chunk in gcs_backend.stream(key, chunk_size=4096):
            chunks.append(chunk)

        assert b"".join(chunks) == content

    @pytest.mark.asyncio
    async def test_get_not_found(self, gcs_backend):
        """Test FileNotFoundError for missing objects."""
        with pytest.raises(FileNotFoundError):
            await gcs_backend.get(f"nonexistent/{uuid.uuid4().hex}")

    @pytest.mark.asyncio
    async def test_metadata(self, gcs_backend):
        """Test saving with metadata."""
        key = f"meta-test/{uuid.uuid4().hex}.txt"
        await gcs_backend.save(
            key,
            b"metadata content",
            metadata={"author": "test", "version": "1"},
        )
        assert await gcs_backend.exists(key) is True
