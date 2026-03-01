"""Cloud Key Vault Integration.

Supports:
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager
- HashiCorp Vault
- Local environment fallback
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class BaseVaultClient(ABC):
    """Base class for vault clients."""

    @abstractmethod
    async def get_secret(self, secret_name: str) -> str | None:
        """Get a secret value by name."""
        pass

    @abstractmethod
    async def set_secret(self, secret_name: str, value: str, **kwargs) -> bool:
        """Set a secret value."""
        pass

    @abstractmethod
    async def delete_secret(self, secret_name: str) -> bool:
        """Delete a secret."""
        pass

    @abstractmethod
    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List all secret names."""
        pass


class AWSSecretsManagerClient(BaseVaultClient):
    """AWS Secrets Manager client."""

    def __init__(self, region: str = None):
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "secretsmanager",
                    region_name=self.region,
                )
            except ImportError:
                raise ImportError("boto3 is required for AWS Secrets Manager")
        return self._client

    async def get_secret(self, secret_name: str) -> str | None:
        import asyncio

        def _get():
            try:
                client = self._get_client()
                response = client.get_secret_value(SecretId=secret_name)
                return response.get("SecretString")
            except Exception as e:
                logger.error(f"Failed to get secret {secret_name}: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, secret_name: str, value: str, **kwargs) -> bool:
        import asyncio

        def _set():
            try:
                client = self._get_client()
                try:
                    client.create_secret(Name=secret_name, SecretString=value)
                except client.exceptions.ResourceExistsException:
                    client.update_secret(SecretId=secret_name, SecretString=value)
                return True
            except Exception as e:
                logger.error(f"Failed to set secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _set)

    async def delete_secret(self, secret_name: str) -> bool:
        import asyncio

        def _delete():
            try:
                client = self._get_client()
                client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
                return True
            except Exception as e:
                logger.error(f"Failed to delete secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def list_secrets(self, prefix: str = "") -> list[str]:
        import asyncio

        def _list():
            try:
                client = self._get_client()
                paginator = client.get_paginator("list_secrets")
                secrets = []
                for page in paginator.paginate():
                    for secret in page.get("SecretList", []):
                        name = secret["Name"]
                        if not prefix or name.startswith(prefix):
                            secrets.append(name)
                return secrets
            except Exception as e:
                logger.error(f"Failed to list secrets: {e}")
                return []

        return await asyncio.get_event_loop().run_in_executor(None, _list)


class AzureKeyVaultClient(BaseVaultClient):
    """Azure Key Vault client."""

    def __init__(self, vault_url: str = None):
        self.vault_url = vault_url or os.getenv("AZURE_KEY_VAULT_URL")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from azure.identity import DefaultAzureCredential
                from azure.keyvault.secrets import SecretClient

                credential = DefaultAzureCredential()
                self._client = SecretClient(vault_url=self.vault_url, credential=credential)
            except ImportError:
                raise ImportError("azure-identity and azure-keyvault-secrets are required")
        return self._client

    async def get_secret(self, secret_name: str) -> str | None:
        import asyncio

        def _get():
            try:
                client = self._get_client()
                secret = client.get_secret(secret_name)
                return secret.value
            except Exception as e:
                logger.error(f"Failed to get secret {secret_name}: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, secret_name: str, value: str, **kwargs) -> bool:
        import asyncio

        def _set():
            try:
                client = self._get_client()
                client.set_secret(secret_name, value)
                return True
            except Exception as e:
                logger.error(f"Failed to set secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _set)

    async def delete_secret(self, secret_name: str) -> bool:
        import asyncio

        def _delete():
            try:
                client = self._get_client()
                poller = client.begin_delete_secret(secret_name)
                poller.result()
                return True
            except Exception as e:
                logger.error(f"Failed to delete secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def list_secrets(self, prefix: str = "") -> list[str]:
        import asyncio

        def _list():
            try:
                client = self._get_client()
                secrets = []
                for secret in client.list_properties_of_secrets():
                    if not prefix or secret.name.startswith(prefix):
                        secrets.append(secret.name)
                return secrets
            except Exception as e:
                logger.error(f"Failed to list secrets: {e}")
                return []

        return await asyncio.get_event_loop().run_in_executor(None, _list)


class GCPSecretManagerClient(BaseVaultClient):
    """Google Cloud Secret Manager client."""

    def __init__(self, project_id: str = None):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google.cloud import secretmanager
                self._client = secretmanager.SecretManagerServiceClient()
            except ImportError:
                raise ImportError("google-cloud-secret-manager is required")
        return self._client

    async def get_secret(self, secret_name: str) -> str | None:
        import asyncio

        def _get():
            try:
                client = self._get_client()
                name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
                response = client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")
            except Exception as e:
                logger.error(f"Failed to get secret {secret_name}: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, secret_name: str, value: str, **kwargs) -> bool:
        import asyncio

        def _set():
            try:
                client = self._get_client()
                parent = f"projects/{self.project_id}"
                secret_path = f"{parent}/secrets/{secret_name}"

                # Try to create the secret first
                try:
                    client.create_secret(
                        request={
                            "parent": parent,
                            "secret_id": secret_name,
                            "secret": {"replication": {"automatic": {}}},
                        }
                    )
                except Exception:
                    pass  # Secret already exists

                # Add a new version
                client.add_secret_version(
                    request={
                        "parent": secret_path,
                        "payload": {"data": value.encode("UTF-8")},
                    }
                )
                return True
            except Exception as e:
                logger.error(f"Failed to set secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _set)

    async def delete_secret(self, secret_name: str) -> bool:
        import asyncio

        def _delete():
            try:
                client = self._get_client()
                name = f"projects/{self.project_id}/secrets/{secret_name}"
                client.delete_secret(request={"name": name})
                return True
            except Exception as e:
                logger.error(f"Failed to delete secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def list_secrets(self, prefix: str = "") -> list[str]:
        import asyncio

        def _list():
            try:
                client = self._get_client()
                parent = f"projects/{self.project_id}"
                secrets = []
                for secret in client.list_secrets(request={"parent": parent}):
                    name = secret.name.split("/")[-1]
                    if not prefix or name.startswith(prefix):
                        secrets.append(name)
                return secrets
            except Exception as e:
                logger.error(f"Failed to list secrets: {e}")
                return []

        return await asyncio.get_event_loop().run_in_executor(None, _list)


class HashiCorpVaultClient(BaseVaultClient):
    """HashiCorp Vault client."""

    def __init__(self, url: str = None, token: str = None, mount_point: str = "secret"):
        self.url = url or os.getenv("VAULT_ADDR")
        self.token = token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(url=self.url, token=self.token)
            except ImportError:
                raise ImportError("hvac is required for HashiCorp Vault")
        return self._client

    async def get_secret(self, secret_name: str) -> str | None:
        import asyncio

        def _get():
            try:
                client = self._get_client()
                secret = client.secrets.kv.v2.read_secret_version(
                    path=secret_name,
                    mount_point=self.mount_point,
                )
                return secret["data"]["data"].get("value")
            except Exception as e:
                logger.error(f"Failed to get secret {secret_name}: {e}")
                return None

        return await asyncio.get_event_loop().run_in_executor(None, _get)

    async def set_secret(self, secret_name: str, value: str, **kwargs) -> bool:
        import asyncio

        def _set():
            try:
                client = self._get_client()
                client.secrets.kv.v2.create_or_update_secret(
                    path=secret_name,
                    secret={"value": value},
                    mount_point=self.mount_point,
                )
                return True
            except Exception as e:
                logger.error(f"Failed to set secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _set)

    async def delete_secret(self, secret_name: str) -> bool:
        import asyncio

        def _delete():
            try:
                client = self._get_client()
                client.secrets.kv.v2.delete_metadata_and_all_versions(
                    path=secret_name,
                    mount_point=self.mount_point,
                )
                return True
            except Exception as e:
                logger.error(f"Failed to delete secret {secret_name}: {e}")
                return False

        return await asyncio.get_event_loop().run_in_executor(None, _delete)

    async def list_secrets(self, prefix: str = "") -> list[str]:
        import asyncio

        def _list():
            try:
                client = self._get_client()
                secrets = client.secrets.kv.v2.list_secrets(
                    path=prefix,
                    mount_point=self.mount_point,
                )
                return secrets["data"]["keys"]
            except Exception as e:
                logger.error(f"Failed to list secrets: {e}")
                return []

        return await asyncio.get_event_loop().run_in_executor(None, _list)


class EnvironmentVaultClient(BaseVaultClient):
    """Fallback client that reads from environment variables."""

    async def get_secret(self, secret_name: str) -> str | None:
        return os.getenv(secret_name)

    async def set_secret(self, secret_name: str, value: str, **kwargs) -> bool:
        # Cannot set environment variables at runtime
        logger.warning("Cannot set secrets in environment mode")
        return False

    async def delete_secret(self, secret_name: str) -> bool:
        logger.warning("Cannot delete secrets in environment mode")
        return False

    async def list_secrets(self, prefix: str = "") -> list[str]:
        return [k for k in os.environ.keys() if k.startswith(prefix)]


class VaultManager:
    """Unified vault manager that supports multiple backends."""

    def __init__(self):
        self._clients: dict[str, BaseVaultClient] = {}
        self._default_client: BaseVaultClient | None = None
        self._initialize()

    def _initialize(self):
        """Initialize vault clients based on environment configuration."""
        vault_type = os.getenv("VAULT_TYPE", "environment").lower()

        if vault_type == "aws":
            self._default_client = AWSSecretsManagerClient()
        elif vault_type == "azure":
            self._default_client = AzureKeyVaultClient()
        elif vault_type == "gcp":
            self._default_client = GCPSecretManagerClient()
        elif vault_type == "hashicorp":
            self._default_client = HashiCorpVaultClient()
        else:
            self._default_client = EnvironmentVaultClient()

        logger.info(f"Initialized vault manager with {vault_type} backend")

    async def get_secret(
        self,
        secret_name: str,
        organization_prefix: str | None = None,
    ) -> str | None:
        """Get a secret value.

        First checks organization-specific secret, then falls back to global.
        Finally falls back to environment variable.
        """
        # Try organization-specific secret
        if organization_prefix:
            org_secret_name = f"{organization_prefix}/{secret_name}"
            value = await self._default_client.get_secret(org_secret_name)
            if value:
                return value

        # Try global secret
        value = await self._default_client.get_secret(secret_name)
        if value:
            return value

        # Fallback to environment
        return os.getenv(secret_name)

    async def set_secret(
        self,
        secret_name: str,
        value: str,
        organization_prefix: str | None = None,
        **kwargs,
    ) -> bool:
        """Set a secret value."""
        if organization_prefix:
            secret_name = f"{organization_prefix}/{secret_name}"
        return await self._default_client.set_secret(secret_name, value, **kwargs)

    async def delete_secret(
        self,
        secret_name: str,
        organization_prefix: str | None = None,
    ) -> bool:
        """Delete a secret."""
        if organization_prefix:
            secret_name = f"{organization_prefix}/{secret_name}"
        return await self._default_client.delete_secret(secret_name)

    async def list_secrets(
        self,
        organization_prefix: str | None = None,
    ) -> list[str]:
        """List secrets."""
        prefix = organization_prefix or ""
        return await self._default_client.list_secrets(prefix)


# Global vault manager instance
@lru_cache()
def get_vault_manager() -> VaultManager:
    """Get the global vault manager instance."""
    return VaultManager()
