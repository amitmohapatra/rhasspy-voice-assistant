"""Encryption service for storing secrets securely.

This module provides:
1. Fernet encryption for symmetric encryption of secrets
2. Key derivation from master key
3. Rotating encryption keys support
4. Field-level encryption for database columns
"""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from src.core.config import settings


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""
    pass


class EncryptionService:
    """Service for encrypting and decrypting sensitive data.

    Uses Fernet (AES-128-CBC with HMAC) for symmetric encryption.
    Supports key rotation via MultiFernet.
    """

    def __init__(
        self,
        master_key: Optional[str] = None,
        salt: Optional[str] = None,
    ):
        """Initialize the encryption service.

        Args:
            master_key: Master encryption key (defaults to settings.encryption_key)
            salt: Salt for key derivation (defaults to settings.encryption_salt)
        """
        self._master_key = master_key or getattr(settings, 'encryption_key', None)
        self._salt = salt or getattr(settings, 'encryption_salt', None)

        if not self._master_key:
            # Generate a default key for development (NOT for production!)
            self._master_key = Fernet.generate_key().decode()

        if not self._salt:
            # Generate a default salt for development
            self._salt = base64.urlsafe_b64encode(os.urandom(16)).decode()

        self._fernet = self._create_fernet()

    def _derive_key(self, master_key: str, salt: str) -> bytes:
        """Derive a Fernet key from master key using PBKDF2.

        Args:
            master_key: The master password/key
            salt: Salt for key derivation

        Returns:
            A valid Fernet key (32 bytes, URL-safe base64 encoded)
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt.encode(),
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(
            kdf.derive(master_key.encode())
        )
        return key

    def _create_fernet(self) -> Fernet:
        """Create a Fernet instance from the master key."""
        # Check if master key is already a valid Fernet key
        try:
            return Fernet(self._master_key.encode())
        except Exception:
            # Derive key from master key
            key = self._derive_key(self._master_key, self._salt)
            return Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string with 'enc:' prefix
        """
        if not plaintext:
            return plaintext

        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return f"enc:{encrypted.decode()}"
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string.

        Args:
            ciphertext: The encrypted string (with 'enc:' prefix)

        Returns:
            The decrypted plaintext string
        """
        if not ciphertext:
            return ciphertext

        # Check if already decrypted (no prefix)
        if not ciphertext.startswith("enc:"):
            return ciphertext

        try:
            encrypted_data = ciphertext[4:]  # Remove 'enc:' prefix
            decrypted = self._fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except InvalidToken:
            raise EncryptionError("Decryption failed: Invalid token or corrupted data")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def is_encrypted(self, value: str) -> bool:
        """Check if a value is encrypted.

        Args:
            value: The value to check

        Returns:
            True if the value appears to be encrypted
        """
        return value and value.startswith("enc:")

    def hash_value(self, value: str) -> str:
        """Create a one-way hash of a value.

        Useful for storing values that need to be compared but not decrypted
        (like API keys for lookup).

        Args:
            value: The value to hash

        Returns:
            SHA-256 hash of the value
        """
        return hashlib.sha256(value.encode()).hexdigest()

    def encrypt_dict(self, data: dict, fields_to_encrypt: list[str]) -> dict:
        """Encrypt specific fields in a dictionary.

        Args:
            data: The dictionary containing data
            fields_to_encrypt: List of field names to encrypt

        Returns:
            Dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in fields_to_encrypt:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result

    def decrypt_dict(self, data: dict, fields_to_decrypt: list[str]) -> dict:
        """Decrypt specific fields in a dictionary.

        Args:
            data: The dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt

        Returns:
            Dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in fields_to_decrypt:
            if field in result and result[field]:
                result[field] = self.decrypt(str(result[field]))
        return result


class RotatingEncryptionService(EncryptionService):
    """Encryption service that supports key rotation.

    Uses MultiFernet to allow decryption with old keys while
    always encrypting with the newest key.
    """

    def __init__(
        self,
        current_key: Optional[str] = None,
        previous_keys: Optional[list[str]] = None,
        salt: Optional[str] = None,
    ):
        """Initialize with current and previous keys.

        Args:
            current_key: The current encryption key
            previous_keys: List of previous keys (for decryption only)
            salt: Salt for key derivation
        """
        self._salt = salt or getattr(settings, 'encryption_salt', None) or 'default-salt'

        current_key = current_key or getattr(settings, 'encryption_key', None)
        previous_keys = previous_keys or getattr(settings, 'encryption_previous_keys', [])

        if not current_key:
            current_key = Fernet.generate_key().decode()

        # Create Fernet instances for all keys
        fernets = []

        # Current key first (will be used for encryption)
        fernets.append(self._create_fernet_from_key(current_key))

        # Previous keys (for decryption only)
        for key in previous_keys:
            try:
                fernets.append(self._create_fernet_from_key(key))
            except Exception:
                pass  # Skip invalid keys

        self._multi_fernet = MultiFernet(fernets)
        self._fernet = fernets[0]  # For compatibility

    def _create_fernet_from_key(self, key: str) -> Fernet:
        """Create a Fernet instance from a key."""
        try:
            return Fernet(key.encode())
        except Exception:
            # Derive key from master key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=self._salt.encode(),
                iterations=100000,
            )
            derived_key = base64.urlsafe_b64encode(
                kdf.derive(key.encode())
            )
            return Fernet(derived_key)

    def encrypt(self, plaintext: str) -> str:
        """Encrypt using the current key."""
        if not plaintext:
            return plaintext

        try:
            encrypted = self._multi_fernet.encrypt(plaintext.encode())
            return f"enc:{encrypted.decode()}"
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt using any available key."""
        if not ciphertext:
            return ciphertext

        if not ciphertext.startswith("enc:"):
            return ciphertext

        try:
            encrypted_data = ciphertext[4:]
            decrypted = self._multi_fernet.decrypt(encrypted_data.encode())
            return decrypted.decode()
        except InvalidToken:
            raise EncryptionError("Decryption failed: Invalid token or key rotation needed")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}")

    def rotate(self, ciphertext: str) -> str:
        """Re-encrypt data with the current key.

        Use this to migrate data encrypted with old keys to the current key.

        Args:
            ciphertext: The encrypted value

        Returns:
            The value re-encrypted with the current key
        """
        if not ciphertext or not ciphertext.startswith("enc:"):
            return ciphertext

        try:
            encrypted_data = ciphertext[4:]
            rotated = self._multi_fernet.rotate(encrypted_data.encode())
            return f"enc:{rotated.decode()}"
        except Exception as e:
            raise EncryptionError(f"Key rotation failed: {e}")


# Singleton instance for the application
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get the application encryption service singleton."""
    global _encryption_service
    if _encryption_service is None:
        # Check if we have previous keys for rotation support
        previous_keys = getattr(settings, 'encryption_previous_keys', None)
        if previous_keys:
            _encryption_service = RotatingEncryptionService()
        else:
            _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_value(value: str) -> str:
    """Convenience function to encrypt a value."""
    return get_encryption_service().encrypt(value)


def decrypt_value(value: str) -> str:
    """Convenience function to decrypt a value."""
    return get_encryption_service().decrypt(value)


def hash_secret(value: str) -> str:
    """Convenience function to hash a value."""
    return get_encryption_service().hash_value(value)


# Sensitive field names that should be encrypted
SENSITIVE_FIELDS = [
    'api_key',
    'secret_key',
    'password',
    'token',
    'auth_token',
    'access_token',
    'refresh_token',
    'client_secret',
    'private_key',
    'ssh_key',
    'service_account_key',
    'license_secret',
]
