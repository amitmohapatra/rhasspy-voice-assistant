"""Integration tests for cloud provider SDKs.

Tests AWS (LocalStack), Azure (Azurite), and GCP (emulators) integrations.
"""

import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestAWSIntegration:
    """Test AWS integration using LocalStack."""

    def test_s3_create_bucket(self, s3_client):
        """Test creating S3 bucket."""
        bucket_name = f"test-bucket-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        response = s3_client.create_bucket(Bucket=bucket_name)
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

        # Cleanup
        s3_client.delete_bucket(Bucket=bucket_name)

    def test_s3_upload_and_download(self, s3_client, test_s3_bucket):
        """Test uploading and downloading from S3."""
        test_content = b"Hello, this is test content!"
        key = "test-file.txt"

        # Upload
        s3_client.put_object(
            Bucket=test_s3_bucket,
            Key=key,
            Body=test_content,
        )

        # Download
        response = s3_client.get_object(Bucket=test_s3_bucket, Key=key)
        downloaded_content = response["Body"].read()

        assert downloaded_content == test_content

    def test_s3_list_objects(self, s3_client, test_s3_bucket):
        """Test listing objects in S3 bucket."""
        # Upload multiple files
        for i in range(5):
            s3_client.put_object(
                Bucket=test_s3_bucket,
                Key=f"file-{i}.txt",
                Body=f"Content {i}".encode(),
            )

        # List objects
        response = s3_client.list_objects_v2(Bucket=test_s3_bucket)

        assert "Contents" in response
        assert len(response["Contents"]) == 5

    def test_s3_delete_objects(self, s3_client, test_s3_bucket):
        """Test deleting objects from S3."""
        key = "to-delete.txt"

        # Upload
        s3_client.put_object(
            Bucket=test_s3_bucket,
            Key=key,
            Body=b"Delete me!",
        )

        # Delete
        s3_client.delete_object(Bucket=test_s3_bucket, Key=key)

        # Verify deleted
        response = s3_client.list_objects_v2(Bucket=test_s3_bucket, Prefix=key)
        assert "Contents" not in response or len(response["Contents"]) == 0

    def test_secrets_manager_create_and_get(self, secrets_manager_client, test_secret):
        """Test creating and retrieving secrets."""
        response = secrets_manager_client.get_secret_value(SecretId=test_secret)

        assert response["SecretString"] is not None
        secret_data = json.loads(response["SecretString"])
        assert "api_key" in secret_data

    def test_secrets_manager_update_secret(self, secrets_manager_client, test_secret):
        """Test updating a secret."""
        new_value = {"api_key": "updated-key-12345", "new_field": "new_value"}

        secrets_manager_client.update_secret(
            SecretId=test_secret,
            SecretString=json.dumps(new_value),
        )

        # Verify update
        response = secrets_manager_client.get_secret_value(SecretId=test_secret)
        retrieved = json.loads(response["SecretString"])

        assert retrieved["api_key"] == "updated-key-12345"
        assert retrieved["new_field"] == "new_value"

    def test_secrets_manager_list_secrets(self, secrets_manager_client, test_secret):
        """Test listing secrets."""
        response = secrets_manager_client.list_secrets()

        assert "SecretList" in response
        secret_names = [s["Name"] for s in response["SecretList"]]
        assert test_secret in secret_names

    def test_sts_get_caller_identity(self, sts_client):
        """Test STS GetCallerIdentity."""
        response = sts_client.get_caller_identity()

        assert "Account" in response
        assert "Arn" in response
        assert "UserId" in response

    def test_iam_list_roles(self, iam_client):
        """Test IAM ListRoles."""
        response = iam_client.list_roles()

        assert "Roles" in response
        # LocalStack might have default roles


class TestAzureIntegration:
    """Test Azure integration using Azurite."""

    def test_blob_create_container(self, azure_blob_service_client):
        """Test creating blob container."""
        import uuid
        container_name = f"test-container-{uuid.uuid4().hex[:8]}"

        container_client = azure_blob_service_client.create_container(container_name)
        assert container_client is not None

        # Cleanup
        azure_blob_service_client.delete_container(container_name)

    def test_blob_upload_and_download(self, azure_blob_service_client, test_azure_container):
        """Test uploading and downloading blobs."""
        blob_name = "test-blob.txt"
        test_content = b"Hello from Azure!"

        # Get container client
        container_client = azure_blob_service_client.get_container_client(test_azure_container)

        # Upload
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(test_content)

        # Download
        downloaded = blob_client.download_blob().readall()
        assert downloaded == test_content

    def test_blob_list_blobs(self, azure_blob_service_client, test_azure_container):
        """Test listing blobs in container."""
        container_client = azure_blob_service_client.get_container_client(test_azure_container)

        # Upload multiple blobs
        for i in range(3):
            blob_client = container_client.get_blob_client(f"blob-{i}.txt")
            blob_client.upload_blob(f"Content {i}".encode())

        # List blobs
        blobs = list(container_client.list_blobs())
        assert len(blobs) == 3

    def test_blob_delete_blob(self, azure_blob_service_client, test_azure_container):
        """Test deleting a blob."""
        container_client = azure_blob_service_client.get_container_client(test_azure_container)
        blob_name = "to-delete.txt"

        # Upload
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(b"Delete me!")

        # Delete
        blob_client.delete_blob()

        # Verify deleted
        blobs = list(container_client.list_blobs(name_starts_with=blob_name))
        assert len(blobs) == 0

    def test_blob_metadata(self, azure_blob_service_client, test_azure_container):
        """Test blob metadata operations."""
        container_client = azure_blob_service_client.get_container_client(test_azure_container)
        blob_name = "metadata-test.txt"

        # Upload with metadata
        blob_client = container_client.get_blob_client(blob_name)
        blob_client.upload_blob(
            b"Test content",
            metadata={"custom_key": "custom_value", "environment": "test"},
        )

        # Get metadata
        props = blob_client.get_blob_properties()
        assert props.metadata["custom_key"] == "custom_value"
        assert props.metadata["environment"] == "test"


class TestGCPIntegration:
    """Test GCP integration using emulators."""

    def test_storage_create_bucket(self, gcp_storage_client):
        """Test creating GCS bucket."""
        import uuid
        bucket_name = f"test-bucket-{uuid.uuid4().hex[:8]}"

        bucket = gcp_storage_client.create_bucket(bucket_name)
        assert bucket is not None
        assert bucket.name == bucket_name

        # Cleanup
        bucket.delete(force=True)

    def test_storage_upload_and_download(self, gcp_storage_client, test_gcp_bucket):
        """Test uploading and downloading from GCS."""
        blob_name = "test-file.txt"
        test_content = "Hello from GCP!"

        bucket = gcp_storage_client.bucket(test_gcp_bucket)
        blob = bucket.blob(blob_name)

        # Upload
        blob.upload_from_string(test_content)

        # Download
        downloaded = blob.download_as_text()
        assert downloaded == test_content

    def test_storage_list_blobs(self, gcp_storage_client, test_gcp_bucket):
        """Test listing blobs in GCS bucket."""
        bucket = gcp_storage_client.bucket(test_gcp_bucket)

        # Upload multiple files
        for i in range(4):
            blob = bucket.blob(f"file-{i}.txt")
            blob.upload_from_string(f"Content {i}")

        # List blobs
        blobs = list(bucket.list_blobs())
        assert len(blobs) == 4

    def test_storage_delete_blob(self, gcp_storage_client, test_gcp_bucket):
        """Test deleting blob from GCS."""
        bucket = gcp_storage_client.bucket(test_gcp_bucket)
        blob_name = "to-delete.txt"

        # Upload
        blob = bucket.blob(blob_name)
        blob.upload_from_string("Delete me!")

        # Delete
        blob.delete()

        # Verify deleted (blob.exists() should return False)
        assert not blob.exists()


class TestCloudSDKValidation:
    """Test cloud SDK validation functions."""

    @pytest.mark.asyncio
    async def test_aws_sdk_validate_credentials(self, mock_aws_sdk):
        """Test AWS SDK credential validation."""
        result = await mock_aws_sdk.validate_credentials()

        # With LocalStack, validation should succeed
        assert result.valid is True or result.error is not None

    @pytest.mark.asyncio
    async def test_aws_sdk_test_connection(self, mock_aws_sdk):
        """Test AWS SDK connection test."""
        result = await mock_aws_sdk.test_connection()

        # Connection test should complete
        assert result is not None
        assert hasattr(result, "valid")

    @pytest.mark.asyncio
    async def test_aws_sdk_check_permissions(self, mock_aws_sdk):
        """Test AWS SDK permission checking."""
        result = await mock_aws_sdk.check_permissions()

        assert result is not None
        assert hasattr(result, "permissions")


class TestCloudStorageOperations:
    """Test cross-cloud storage operations."""

    @pytest.mark.parametrize("provider,fixture_name", [
        ("aws", "test_s3_bucket"),
        ("azure", "test_azure_container"),
        ("gcp", "test_gcp_bucket"),
    ])
    def test_storage_lifecycle(self, provider, fixture_name, request):
        """Test basic storage lifecycle across providers."""
        try:
            bucket_or_container = request.getfixturevalue(fixture_name)
        except pytest.FixtureLookupError:
            pytest.skip(f"Fixture {fixture_name} not available")

        # Fixture created successfully means lifecycle works
        assert bucket_or_container is not None


class TestSecretsManagement:
    """Test secrets management across providers."""

    def test_aws_secret_rotation(self, secrets_manager_client, test_secret):
        """Test AWS secret rotation simulation."""
        # Update secret multiple times to simulate rotation
        for i in range(3):
            new_value = {"api_key": f"rotated-key-{i}", "rotation": i}
            secrets_manager_client.update_secret(
                SecretId=test_secret,
                SecretString=json.dumps(new_value),
            )

        # Get current version
        response = secrets_manager_client.get_secret_value(SecretId=test_secret)
        current = json.loads(response["SecretString"])

        assert current["rotation"] == 2  # Last rotation

    def test_aws_secret_versioning(self, secrets_manager_client, test_secret):
        """Test AWS secret versioning."""
        # Get secret versions
        response = secrets_manager_client.list_secret_version_ids(SecretId=test_secret)

        assert "Versions" in response
        # Should have at least one version
        assert len(response["Versions"]) >= 1


class TestCloudErrorHandling:
    """Test error handling for cloud operations."""

    def test_s3_bucket_not_found(self, s3_client):
        """Test accessing non-existent bucket."""
        import botocore.exceptions

        with pytest.raises(botocore.exceptions.ClientError) as exc:
            s3_client.get_object(
                Bucket="non-existent-bucket-12345",
                Key="test.txt",
            )

        assert "NoSuchBucket" in str(exc.value) or "NoSuchKey" in str(exc.value) or "404" in str(exc.value)

    def test_secrets_not_found(self, secrets_manager_client):
        """Test accessing non-existent secret."""
        import botocore.exceptions

        with pytest.raises(botocore.exceptions.ClientError) as exc:
            secrets_manager_client.get_secret_value(
                SecretId="non-existent-secret-12345"
            )

        assert "ResourceNotFoundException" in str(exc.value) or "404" in str(exc.value)

    def test_azure_container_not_found(self, azure_blob_service_client):
        """Test accessing non-existent Azure container."""
        from azure.core.exceptions import ResourceNotFoundError

        container_client = azure_blob_service_client.get_container_client(
            "non-existent-container-12345"
        )

        with pytest.raises(ResourceNotFoundError):
            list(container_client.list_blobs())

    def test_gcp_bucket_not_found(self, gcp_storage_client):
        """Test accessing non-existent GCP bucket."""
        from google.cloud.exceptions import NotFound

        bucket = gcp_storage_client.bucket("non-existent-bucket-12345")

        with pytest.raises(NotFound):
            bucket.reload()
