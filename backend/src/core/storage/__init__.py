"""
Storage abstraction layer for multi-cloud file storage.

Supports:
- Local filesystem (development)
- AWS S3 / LocalStack (production / local emulation)
- Azure Blob Storage / Azurite (production / local emulation)
- Google Cloud Storage / fake-gcs-server (production / local emulation)
"""

from src.core.storage.base import StorageBackend, StorageFile
from src.core.storage.local import LocalStorageBackend
from src.core.storage.factory import get_storage_backend, storage

__all__ = [
    "StorageBackend",
    "StorageFile",
    "LocalStorageBackend",
    "get_storage_backend",
    "storage",
]

# Conditionally export cloud backends only when their SDKs are installed
try:
    from src.core.storage.s3 import S3StorageBackend
    __all__.append("S3StorageBackend")
except ImportError:
    pass

try:
    from src.core.storage.azure_blob import AzureBlobStorageBackend
    __all__.append("AzureBlobStorageBackend")
except ImportError:
    pass

try:
    from src.core.storage.gcs import GCSStorageBackend
    __all__.append("GCSStorageBackend")
except ImportError:
    pass
