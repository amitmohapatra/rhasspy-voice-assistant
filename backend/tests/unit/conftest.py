"""Unit test configuration and fixtures.

Provides fixtures for unit testing without external dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(scope="function")
def encryption_service():
    """Create encryption service for testing."""
    from src.core.encryption import EncryptionService

    # Use a fixed test key (32 bytes)
    test_key = "test-encryption-key-32-bytes-xx"
    return EncryptionService(master_key=test_key, salt="test-salt")


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


@pytest.fixture(scope="function")
def mock_settings():
    """Create mock settings for testing."""
    mock = MagicMock()
    mock.encryption_key = "test-key-32-bytes-long-xxxxxxxx"
    mock.encryption_salt = "test-salt"
    mock.encryption_previous_keys = None
    mock.openai_api_key = "test-openai-key"
    mock.anthropic_api_key = "test-anthropic-key"
    mock.database_url = "postgresql+asyncpg://test:test@localhost:5432/test"
    mock.redis_url = "redis://localhost:6379/0"
    return mock


@pytest.fixture(scope="function")
def mock_db_session():
    """Create a mock database session."""
    mock = MagicMock()
    mock.execute = MagicMock()
    mock.commit = MagicMock()
    mock.rollback = MagicMock()
    mock.close = MagicMock()
    return mock


@pytest.fixture(scope="function")
def mock_redis_client():
    """Create a mock Redis client."""
    mock = MagicMock()
    mock.get = MagicMock(return_value=None)
    mock.set = MagicMock(return_value=True)
    mock.delete = MagicMock(return_value=True)
    mock.hget = MagicMock(return_value=None)
    mock.hset = MagicMock(return_value=True)
    return mock


@pytest.fixture(scope="function")
def sample_user_data():
    """Sample user data for testing."""
    import uuid

    return {
        "id": str(uuid.uuid4()),
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
        "is_active": True,
        "organization_id": str(uuid.uuid4()),
    }


@pytest.fixture(scope="function")
def sample_organization_data():
    """Sample organization data for testing."""
    import uuid

    return {
        "id": str(uuid.uuid4()),
        "name": "Test Organization",
        "slug": "test-org",
        "plan": "enterprise",
        "is_active": True,
    }


@pytest.fixture(scope="function")
def sample_assistant_data():
    """Sample assistant data for testing."""
    import uuid

    return {
        "id": str(uuid.uuid4()),
        "name": "Test Assistant",
        "description": "A test assistant",
        "system_prompt": "You are a helpful assistant.",
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 1000,
    }


@pytest.fixture(scope="function")
def sample_cloud_credentials():
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
            "client_secret": "super-secret",
            "subscription_id": "12345678-1234-1234-1234-123456789014",
        },
        "gcp": {
            "project_id": "test-project",
            "service_account_json": '{"type": "service_account"}',
        },
    }
