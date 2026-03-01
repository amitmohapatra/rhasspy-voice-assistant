"""Unit tests for encryption service.

Tests Fernet encryption, key rotation, and secure credential storage.
"""

import pytest
import base64
from unittest.mock import patch, MagicMock

pytestmark = [pytest.mark.unit]


class TestEncryptionService:
    """Test EncryptionService class."""

    def test_encrypt_string(self, encryption_service):
        """Test encrypting a plain string."""
        plaintext = "my-secret-api-key-12345"

        encrypted = encryption_service.encrypt(plaintext)

        assert encrypted.startswith("enc:")
        assert encrypted != plaintext
        assert len(encrypted) > len(plaintext)

    def test_decrypt_string(self, encryption_service):
        """Test decrypting an encrypted string."""
        plaintext = "my-secret-api-key-12345"

        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_decrypt_non_encrypted_string(self, encryption_service):
        """Test decrypting a non-encrypted string returns original."""
        plaintext = "plain-text-value"

        result = encryption_service.decrypt(plaintext)

        assert result == plaintext

    def test_encrypt_empty_string(self, encryption_service):
        """Test encrypting an empty string returns empty string."""
        encrypted = encryption_service.encrypt("")

        # Empty strings are not encrypted (optimization)
        assert encrypted == ""
        decrypted = encryption_service.decrypt(encrypted)
        assert decrypted == ""

    def test_encrypt_unicode_string(self, encryption_service):
        """Test encrypting a unicode string."""
        plaintext = "Hello, World!"

        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_long_string(self, encryption_service):
        """Test encrypting a long string."""
        plaintext = "x" * 10000  # 10KB string

        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_special_characters(self, encryption_service):
        """Test encrypting string with special characters."""
        plaintext = '{"key": "value", "special": "!@#$%^&*()"}'

        encrypted = encryption_service.encrypt(plaintext)
        decrypted = encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self, encryption_service):
        """Test that same plaintext produces different ciphertext each time."""
        plaintext = "same-secret"

        encrypted1 = encryption_service.encrypt(plaintext)
        encrypted2 = encryption_service.encrypt(plaintext)

        # Fernet uses random IV, so ciphertext should be different
        assert encrypted1 != encrypted2

        # But both should decrypt to same value
        assert encryption_service.decrypt(encrypted1) == plaintext
        assert encryption_service.decrypt(encrypted2) == plaintext

    def test_is_encrypted(self, encryption_service):
        """Test checking if a value is encrypted."""
        encrypted = encryption_service.encrypt("test")
        plain = "plain-text"

        assert encryption_service.is_encrypted(encrypted) is True
        assert encryption_service.is_encrypted(plain) is False

    def test_decrypt_invalid_ciphertext(self, encryption_service):
        """Test decrypting invalid ciphertext raises error."""
        invalid = "enc:invalid-base64-data"

        with pytest.raises(Exception):
            encryption_service.decrypt(invalid)


class TestRotatingEncryptionService:
    """Test RotatingEncryptionService with key rotation."""

    def test_encrypt_with_current_key(self, rotating_encryption_service):
        """Test encrypting uses current key."""
        plaintext = "secret-value"

        encrypted = rotating_encryption_service.encrypt(plaintext)

        assert encrypted.startswith("enc:")

    def test_decrypt_with_current_key(self, rotating_encryption_service):
        """Test decrypting with current key."""
        plaintext = "secret-value"

        encrypted = rotating_encryption_service.encrypt(plaintext)
        decrypted = rotating_encryption_service.decrypt(encrypted)

        assert decrypted == plaintext

    def test_decrypt_with_previous_keys(self):
        """Test decrypting data encrypted with a previous key."""
        from src.core.encryption import EncryptionService, RotatingEncryptionService

        # Encrypt with old key
        old_key = "old-key-32-bytes-long-xxxxxxxxxx"
        old_service = EncryptionService(master_key=old_key, salt="test-salt")
        plaintext = "old-encrypted-data"
        old_encrypted = old_service.encrypt(plaintext)

        # Create rotating service with new current key and old key as previous
        new_key = "new-key-32-bytes-long-xxxxxxxxxx"
        rotating_service = RotatingEncryptionService(
            current_key=new_key,
            previous_keys=[old_key],
            salt="test-salt",
        )

        # Should be able to decrypt with previous key
        decrypted = rotating_service.decrypt(old_encrypted)
        assert decrypted == plaintext

    def test_rotate_and_encrypt(self):
        """Test encrypting after key rotation uses new key."""
        from src.core.encryption import RotatingEncryptionService, EncryptionService

        old_key = "old-key-32-bytes-long-xxxxxxxxxx"
        new_key = "new-key-32-bytes-long-xxxxxxxxxx"

        rotating_service = RotatingEncryptionService(
            current_key=new_key,
            previous_keys=[old_key],
            salt="test-salt",
        )

        plaintext = "new-data"
        encrypted = rotating_service.encrypt(plaintext)

        # Verify it's encrypted with new key (should fail with only old key)
        old_only_service = EncryptionService(master_key=old_key, salt="test-salt")

        with pytest.raises(Exception):
            old_only_service.decrypt(encrypted)

        # But should work with new key
        new_only_service = EncryptionService(master_key=new_key, salt="test-salt")
        decrypted = new_only_service.decrypt(encrypted)
        assert decrypted == plaintext

    def test_rotate_with_current_key(self):
        """Test rotating (re-encrypting) data with current key."""
        from src.core.encryption import EncryptionService, RotatingEncryptionService

        old_key = "old-key-32-bytes-long-xxxxxxxxxx"
        new_key = "new-key-32-bytes-long-xxxxxxxxxx"

        # Encrypt with old key
        old_service = EncryptionService(master_key=old_key, salt="test-salt")
        plaintext = "data-to-migrate"
        old_encrypted = old_service.encrypt(plaintext)

        # Create rotating service
        rotating_service = RotatingEncryptionService(
            current_key=new_key,
            previous_keys=[old_key],
            salt="test-salt",
        )

        # Rotate (re-encrypt) with current key
        new_encrypted = rotating_service.rotate(old_encrypted)

        # Should be different ciphertext
        assert new_encrypted != old_encrypted

        # Should decrypt correctly
        decrypted = rotating_service.decrypt(new_encrypted)
        assert decrypted == plaintext

        # Should now work with new key only
        new_only_service = EncryptionService(master_key=new_key, salt="test-salt")
        decrypted2 = new_only_service.decrypt(new_encrypted)
        assert decrypted2 == plaintext


class TestEncryptionKeyGeneration:
    """Test encryption key generation."""

    def test_generate_key(self):
        """Test generating a new encryption key using Fernet."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()

        assert key is not None
        assert len(key) > 0
        # Should be base64 encoded
        decoded = base64.urlsafe_b64decode(key)
        assert len(decoded) == 32  # 256 bits

    def test_generate_unique_keys(self):
        """Test that generated keys are unique."""
        from cryptography.fernet import Fernet

        keys = [Fernet.generate_key() for _ in range(10)]

        # All keys should be unique
        assert len(set(keys)) == 10


class TestEncryptionFromConfig:
    """Test encryption service initialization from config."""

    def test_create_from_config_with_key(self):
        """Test creating encryption service from config with key."""
        from src.core.encryption import EncryptionService

        # Test with explicit key and salt
        service = EncryptionService(
            master_key="test-key-32-bytes-long-xxxxxxxx",
            salt="test-salt"
        )

        assert service is not None
        # Should be able to encrypt/decrypt
        encrypted = service.encrypt("test")
        assert service.decrypt(encrypted) == "test"

    def test_create_from_config_with_rotation(self):
        """Test creating encryption service with key rotation config."""
        from src.core.encryption import RotatingEncryptionService

        # Test with explicit keys
        service = RotatingEncryptionService(
            current_key="current-key-32-bytes-long-xxxxx",
            previous_keys=[
                "previous-key-1-32-bytes-long-xx",
                "previous-key-2-32-bytes-long-xx",
            ],
            salt="test-salt"
        )

        assert service is not None

    def test_create_from_config_no_key(self):
        """Test creating encryption service without key uses auto-generated key."""
        from src.core.encryption import EncryptionService

        # When no key is provided, service should auto-generate one
        service = EncryptionService()

        # Should still work with auto-generated key
        assert service is not None
        encrypted = service.encrypt("test")
        assert service.decrypt(encrypted) == "test"


class TestCredentialEncryption:
    """Test encrypting/decrypting credential objects using encrypt_dict/decrypt_dict."""

    def test_encrypt_credentials_dict(self, encryption_service):
        """Test encrypting a credentials dictionary."""
        credentials = {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "us-east-1",
        }

        # Use encrypt_dict with sensitive fields
        encrypted = encryption_service.encrypt_dict(credentials, ["secret_access_key"])

        # Sensitive fields should be encrypted
        assert encrypted["secret_access_key"].startswith("enc:")
        # Non-sensitive fields should not be encrypted
        assert encrypted["region"] == "us-east-1"

        # Decrypt
        decrypted = encryption_service.decrypt_dict(encrypted, ["secret_access_key"])
        assert decrypted["secret_access_key"] == credentials["secret_access_key"]

    def test_encrypt_azure_credentials(self, encryption_service):
        """Test encrypting Azure credentials."""
        credentials = {
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "client_id": "12345678-1234-1234-1234-123456789013",
            "client_secret": "super-secret-value",
            "subscription_id": "12345678-1234-1234-1234-123456789014",
        }

        # Encrypt only the secret
        encrypted = encryption_service.encrypt_dict(credentials, ["client_secret"])

        # Secret should be encrypted
        assert encrypted["client_secret"].startswith("enc:")

        decrypted = encryption_service.decrypt_dict(encrypted, ["client_secret"])
        assert decrypted["client_secret"] == credentials["client_secret"]

    def test_encrypt_gcp_credentials(self, encryption_service):
        """Test encrypting GCP service account credentials."""
        credentials = {
            "project_id": "my-project",
            "service_account_json": '{"type": "service_account", "private_key": "-----BEGIN PRIVATE KEY-----\\nMIIE..."}',
        }

        # Encrypt service account JSON
        encrypted = encryption_service.encrypt_dict(credentials, ["service_account_json"])

        # Service account JSON should be encrypted
        assert encrypted["service_account_json"].startswith("enc:")

        decrypted = encryption_service.decrypt_dict(encrypted, ["service_account_json"])
        assert decrypted["service_account_json"] == credentials["service_account_json"]


class TestEncryptionPerformance:
    """Test encryption service performance."""

    def test_encrypt_performance(self, encryption_service):
        """Test encryption performance with many operations."""
        import time

        plaintext = "test-secret-value"
        iterations = 1000

        start = time.time()
        for _ in range(iterations):
            encryption_service.encrypt(plaintext)
        elapsed = time.time() - start

        # Should complete 1000 encryptions in under 1 second
        assert elapsed < 1.0, f"Encryption too slow: {elapsed}s for {iterations} ops"

    def test_decrypt_performance(self, encryption_service):
        """Test decryption performance with many operations."""
        import time

        plaintext = "test-secret-value"
        encrypted = encryption_service.encrypt(plaintext)
        iterations = 1000

        start = time.time()
        for _ in range(iterations):
            encryption_service.decrypt(encrypted)
        elapsed = time.time() - start

        # Should complete 1000 decryptions in under 1 second
        assert elapsed < 1.0, f"Decryption too slow: {elapsed}s for {iterations} ops"


class TestEncryptionSecurity:
    """Test encryption security properties."""

    def test_key_not_in_ciphertext(self, encryption_service):
        """Test that key material is not present in ciphertext."""
        plaintext = "secret-data"
        encrypted = encryption_service.encrypt(plaintext)

        # Key should not appear in ciphertext
        # Note: This is a basic check, not a full security audit
        assert "test-encryption-key" not in encrypted
        assert "32-bytes" not in encrypted

    def test_plaintext_not_in_ciphertext(self, encryption_service):
        """Test that plaintext is not visible in ciphertext."""
        plaintext = "my-api-key-12345"
        encrypted = encryption_service.encrypt(plaintext)

        # Plaintext should not be visible
        assert "my-api-key" not in encrypted
        assert "12345" not in encrypted.replace("enc:", "")

    def test_decrypt_wrong_key_fails(self):
        """Test that decryption with wrong key fails."""
        from src.core.encryption import EncryptionService

        key1 = "correct-key-32-bytes-long-xxxxx"
        key2 = "wrong-key-32-bytes-long-xxxxxxx"

        service1 = EncryptionService(master_key=key1, salt="test-salt")
        service2 = EncryptionService(master_key=key2, salt="test-salt")

        encrypted = service1.encrypt("secret")

        with pytest.raises(Exception):
            service2.decrypt(encrypted)

    def test_tampered_ciphertext_fails(self, encryption_service):
        """Test that tampered ciphertext fails to decrypt."""
        encrypted = encryption_service.encrypt("secret")

        # Tamper with ciphertext (change a character)
        tampered = encrypted[:10] + "X" + encrypted[11:]

        with pytest.raises(Exception):
            encryption_service.decrypt(tampered)
