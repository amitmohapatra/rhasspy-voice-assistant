"""Integration test configuration with cloud emulator fixtures.

Provides fixtures for:
- LocalStack (AWS S3, Secrets Manager, STS, IAM)
- Azurite (Azure Blob Storage)
- GCP Storage Emulator
- PostgreSQL
- Redis with RediSearch
- Qdrant vector database
"""

import asyncio
import os
from typing import AsyncGenerator, Generator
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio
import httpx

# AWS
import boto3
from botocore.config import Config as BotoConfig

# Test environment configuration
TEST_CONFIG = {
    # LocalStack (AWS)
    "AWS_ENDPOINT_URL": os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "AWS_DEFAULT_REGION": "us-east-1",

    # Azurite (Azure)
    "AZURE_STORAGE_CONNECTION_STRING": os.getenv(
        "AZURE_STORAGE_CONNECTION_STRING",
        "DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;"
        "AccountKey=Eby8vdM02xNOcqFlqUwJPLlmEtlCDXJ1OUzFT50uSRZ6IFsuFq2UVErCz4I6tq/K1SZFPTOtr/KBHBeksoGMGw==;"
        "BlobEndpoint=http://localhost:10000/devstoreaccount1;"
        "QueueEndpoint=http://localhost:10001/devstoreaccount1;"
        "TableEndpoint=http://localhost:10002/devstoreaccount1;"
    ),

    # GCP Storage
    "GCP_STORAGE_EMULATOR_HOST": os.getenv("GCP_STORAGE_EMULATOR_HOST", "http://localhost:4443"),
    "GCP_PROJECT_ID": "test-project",

    # PostgreSQL
    "TEST_DATABASE_URL": os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://test_user:test_password@localhost:5433/test_db"
    ),

    # Redis
    "TEST_REDIS_URL": os.getenv("TEST_REDIS_URL", "redis://localhost:6380/0"),

    # Vector Databases
    "QDRANT_URL": os.getenv("QDRANT_URL", "http://localhost:6334"),
}


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# AWS LocalStack Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def aws_config() -> dict:
    """Return AWS configuration for LocalStack."""
    return {
        "endpoint_url": TEST_CONFIG["AWS_ENDPOINT_URL"],
        "aws_access_key_id": TEST_CONFIG["AWS_ACCESS_KEY_ID"],
        "aws_secret_access_key": TEST_CONFIG["AWS_SECRET_ACCESS_KEY"],
        "region_name": TEST_CONFIG["AWS_DEFAULT_REGION"],
    }


@pytest.fixture(scope="session")
def s3_client(aws_config: dict):
    """Create S3 client connected to LocalStack."""
    return boto3.client("s3", **aws_config)


@pytest.fixture(scope="session")
def secrets_manager_client(aws_config: dict):
    """Create Secrets Manager client connected to LocalStack."""
    return boto3.client("secretsmanager", **aws_config)


@pytest.fixture(scope="session")
def sts_client(aws_config: dict):
    """Create STS client connected to LocalStack."""
    return boto3.client("sts", **aws_config)


@pytest.fixture(scope="session")
def iam_client(aws_config: dict):
    """Create IAM client connected to LocalStack."""
    return boto3.client("iam", **aws_config)


@pytest_asyncio.fixture(scope="function")
async def test_s3_bucket(s3_client) -> AsyncGenerator[str, None]:
    """Create a test S3 bucket and clean up after test."""
    import uuid
    bucket_name = f"test-bucket-{uuid.uuid4().hex[:8]}"

    s3_client.create_bucket(Bucket=bucket_name)

    yield bucket_name

    # Cleanup: Delete all objects and the bucket
    try:
        response = s3_client.list_objects_v2(Bucket=bucket_name)
        for obj in response.get("Contents", []):
            s3_client.delete_object(Bucket=bucket_name, Key=obj["Key"])
        s3_client.delete_bucket(Bucket=bucket_name)
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def test_secret(secrets_manager_client) -> AsyncGenerator[str, None]:
    """Create a test secret and clean up after test."""
    import uuid
    import json

    secret_name = f"test-secret-{uuid.uuid4().hex[:8]}"
    secret_value = {"api_key": "test-key-12345", "api_secret": "test-secret-67890"}

    secrets_manager_client.create_secret(
        Name=secret_name,
        SecretString=json.dumps(secret_value)
    )

    yield secret_name

    # Cleanup
    try:
        secrets_manager_client.delete_secret(
            SecretId=secret_name,
            ForceDeleteWithoutRecovery=True
        )
    except Exception:
        pass


# =============================================================================
# Azure Azurite Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def azure_connection_string() -> str:
    """Return Azure Storage connection string for Azurite."""
    return TEST_CONFIG["AZURE_STORAGE_CONNECTION_STRING"]


@pytest.fixture(scope="session")
def azure_blob_service_client(azure_connection_string: str):
    """Create Azure Blob Service client connected to Azurite."""
    try:
        from azure.storage.blob import BlobServiceClient
        return BlobServiceClient.from_connection_string(azure_connection_string)
    except ImportError:
        pytest.skip("azure-storage-blob not installed")


@pytest_asyncio.fixture(scope="function")
async def test_azure_container(azure_blob_service_client) -> AsyncGenerator[str, None]:
    """Create a test Azure container and clean up after test."""
    import uuid

    container_name = f"test-container-{uuid.uuid4().hex[:8]}"

    container_client = azure_blob_service_client.create_container(container_name)

    yield container_name

    # Cleanup
    try:
        azure_blob_service_client.delete_container(container_name)
    except Exception:
        pass


# =============================================================================
# GCP Storage Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def gcp_storage_client():
    """Create GCP Storage client connected to emulator."""
    try:
        from google.cloud import storage
        from google.auth.credentials import AnonymousCredentials

        # Configure client to use emulator
        client = storage.Client(
            credentials=AnonymousCredentials(),
            project=TEST_CONFIG["GCP_PROJECT_ID"],
        )
        # Override the API endpoint
        client._connection.API_BASE_URL = TEST_CONFIG["GCP_STORAGE_EMULATOR_HOST"]
        return client
    except ImportError:
        pytest.skip("google-cloud-storage not installed")


@pytest_asyncio.fixture(scope="function")
async def test_gcp_bucket(gcp_storage_client) -> AsyncGenerator[str, None]:
    """Create a test GCP bucket and clean up after test."""
    import uuid

    bucket_name = f"test-bucket-{uuid.uuid4().hex[:8]}"

    bucket = gcp_storage_client.create_bucket(bucket_name)

    yield bucket_name

    # Cleanup
    try:
        bucket = gcp_storage_client.bucket(bucket_name)
        bucket.delete(force=True)
    except Exception:
        pass


# =============================================================================
# PostgreSQL Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def test_db_engine():
    """Create test database engine."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        TEST_CONFIG["TEST_DATABASE_URL"],
        echo=False,
        pool_size=5,
        max_overflow=10,
    )

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_db_session_factory(test_db_engine):
    """Create test database session factory."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    return sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


@pytest_asyncio.fixture(scope="function")
async def test_db_session(test_db_session_factory) -> AsyncGenerator:
    """Create a test database session with automatic rollback."""
    async with test_db_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="session")
async def init_test_db(test_db_engine):
    """Initialize test database schema."""
    from src.models import Base

    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# =============================================================================
# Redis Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def redis_client():
    """Create Redis client for testing."""
    import redis.asyncio as redis

    client = redis.from_url(TEST_CONFIG["TEST_REDIS_URL"])

    yield client

    await client.aclose()


@pytest_asyncio.fixture(scope="function")
async def clean_redis(redis_client):
    """Clean Redis database before and after each test."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


# =============================================================================
# Vector Database Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def qdrant_client():
    """Create Qdrant client for testing."""
    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(url=TEST_CONFIG["QDRANT_URL"])
        yield client
        client.close()
    except ImportError:
        pytest.skip("qdrant-client not installed")


@pytest_asyncio.fixture(scope="function")
async def test_qdrant_collection(qdrant_client) -> AsyncGenerator[str, None]:
    """Create a test Qdrant collection and clean up after test."""
    import uuid
    from qdrant_client.models import Distance, VectorParams

    collection_name = f"test_collection_{uuid.uuid4().hex[:8]}"

    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    yield collection_name

    # Cleanup
    try:
        qdrant_client.delete_collection(collection_name)
    except Exception:
        pass


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def async_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create an async HTTP client for API testing."""
    async with httpx.AsyncClient(
        base_url="http://localhost:8000",
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        yield client


# =============================================================================
# Encryption Service Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def encryption_service():
    """Create encryption service for testing."""
    from src.core.encryption import EncryptionService

    test_key = "test-encryption-key-32-bytes-long"
    return EncryptionService(key=test_key)


@pytest.fixture(scope="function")
def rotating_encryption_service():
    """Create rotating encryption service for testing."""
    from src.core.encryption import RotatingEncryptionService

    current_key = "current-key-32-bytes-long-xxxxx"
    previous_keys = [
        "previous-key-1-32-bytes-long-xx",
        "previous-key-2-32-bytes-long-xx",
    ]

    return RotatingEncryptionService(
        current_key=current_key,
        previous_keys=previous_keys,
    )


# =============================================================================
# Cloud SDK Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def mock_aws_sdk(aws_config: dict):
    """Create AWS SDK configured for LocalStack."""
    from src.core.cloud_sdk import AWSSDK

    return AWSSDK(
        access_key_id=aws_config["aws_access_key_id"],
        secret_access_key=aws_config["aws_secret_access_key"],
        region=aws_config["region_name"],
        endpoint_url=aws_config["endpoint_url"],
    )


@pytest.fixture(scope="function")
def mock_azure_sdk(azure_connection_string: str):
    """Create Azure SDK configured for Azurite."""
    from src.core.cloud_sdk import AzureSDK

    # Parse connection string for testing
    return AzureSDK(
        tenant_id="test-tenant-id",
        client_id="test-client-id",
        client_secret="test-client-secret",
        subscription_id="test-subscription-id",
    )


@pytest.fixture(scope="function")
def mock_gcp_sdk():
    """Create GCP SDK configured for emulator."""
    from src.core.cloud_sdk import GCPSDK

    return GCPSDK(
        project_id=TEST_CONFIG["GCP_PROJECT_ID"],
        service_account_json=None,  # Use emulator credentials
    )


# =============================================================================
# Test Data Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def sample_organization_data() -> dict:
    """Sample organization data for testing."""
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "name": f"Test Organization {uuid.uuid4().hex[:8]}",
        "slug": f"test-org-{uuid.uuid4().hex[:8]}",
        "plan": "enterprise",
        "is_active": True,
        "settings": {
            "max_users": 100,
            "max_assistants": 50,
            "features": ["rag", "voice", "analytics"],
        },
    }


@pytest.fixture(scope="function")
def sample_deployment_data(sample_organization_data: dict) -> dict:
    """Sample deployment data for testing."""
    import uuid
    return {
        "id": str(uuid.uuid4()),
        "organization_id": sample_organization_data["id"],
        "name": f"Test Deployment {uuid.uuid4().hex[:8]}",
        "cloud_provider": "aws",
        "cloud_region": "us-east-1",
        "status": "pending",
        "config": {
            "instance_type": "t3.medium",
            "min_instances": 1,
            "max_instances": 3,
        },
    }


@pytest.fixture(scope="function")
def sample_license_data(sample_deployment_data: dict) -> dict:
    """Sample license data for testing."""
    import uuid
    from datetime import datetime, timedelta

    return {
        "id": str(uuid.uuid4()),
        "deployment_id": sample_deployment_data["id"],
        "license_key": f"LIC-{uuid.uuid4().hex[:16].upper()}",
        "license_secret": f"SEC-{uuid.uuid4().hex[:32]}",
        "status": "active",
        "tier": "enterprise",
        "max_users": 100,
        "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
        "features": {
            "rag": True,
            "voice": True,
            "analytics": True,
            "custom_models": True,
        },
    }


@pytest.fixture(scope="function")
def sample_cloud_credentials() -> dict:
    """Sample cloud credentials for testing."""
    return {
        "aws": {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "us-east-1",
        },
        "azure": {
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "client_id": "12345678-1234-1234-1234-123456789013",
            "client_secret": "client-secret-value",
            "subscription_id": "12345678-1234-1234-1234-123456789014",
        },
        "gcp": {
            "project_id": "test-project-123",
            "service_account_json": {
                "type": "service_account",
                "project_id": "test-project-123",
                "private_key_id": "key-id",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n",
                "client_email": "test@test-project-123.iam.gserviceaccount.com",
                "client_id": "123456789",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            },
        },
    }
