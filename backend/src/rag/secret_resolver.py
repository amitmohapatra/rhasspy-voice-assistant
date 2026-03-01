"""Secret Resolver Service.

Resolves secrets from multiple sources:
- Direct (encrypted in DB)
- Environment variables
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager
- HashiCorp Vault
- Platform defaults
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from src.core.encryption import decrypt_value
from src.core.vault import (
    AWSSecretsManagerClient,
    AzureKeyVaultClient,
    GCPSecretManagerClient,
    HashiCorpVaultClient,
    get_vault_manager,
)
from src.rag.pipeline_config import (
    SecretReference,
    SecretSource,
    HeaderConfig,
)

logger = logging.getLogger(__name__)


class SecretResolver:
    """Resolves secrets from various sources."""

    def __init__(self):
        """Initialize the secret resolver."""
        self._vault_clients = {}

    async def resolve(self, ref: SecretReference) -> Optional[str]:
        """Resolve a secret reference to its actual value.

        Args:
            ref: The secret reference configuration

        Returns:
            The resolved secret value, or None if not found
        """
        try:
            match ref.source:
                case SecretSource.DIRECT:
                    return self._resolve_direct(ref)
                case SecretSource.ENV:
                    return self._resolve_env(ref)
                case SecretSource.AWS_SECRETS:
                    return await self._resolve_aws(ref)
                case SecretSource.AZURE_KEYVAULT:
                    return await self._resolve_azure(ref)
                case SecretSource.GCP_SECRETS:
                    return await self._resolve_gcp(ref)
                case SecretSource.HASHICORP_VAULT:
                    return await self._resolve_hashicorp(ref)
                case SecretSource.PLATFORM_DEFAULT:
                    return await self._resolve_platform(ref)
                case _:
                    logger.warning(f"Unknown secret source: {ref.source}")
                    return None
        except Exception as e:
            logger.error(f"Failed to resolve secret: {e}")
            return None

    def _resolve_direct(self, ref: SecretReference) -> Optional[str]:
        """Resolve a direct (encrypted) secret."""
        if not ref.value:
            return None
        # Decrypt if encrypted
        return decrypt_value(ref.value)

    def _resolve_env(self, ref: SecretReference) -> Optional[str]:
        """Resolve from environment variable."""
        if not ref.env_var:
            return None
        return os.environ.get(ref.env_var)

    async def _resolve_aws(self, ref: SecretReference) -> Optional[str]:
        """Resolve from AWS Secrets Manager."""
        if not ref.aws:
            return None

        config = ref.aws

        # Create client with optional access keys
        if config.auth_type == "access_keys" and config.access_key_id:
            # Resolve the secret access key if it's also a reference
            secret_key = None
            if config.secret_access_key:
                secret_key = await self.resolve(config.secret_access_key)

            import boto3
            client = boto3.client(
                "secretsmanager",
                region_name=config.region,
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=secret_key,
            )
        else:
            # Use IAM role (default credentials)
            client = self._get_aws_client(config.region)

        try:
            import asyncio

            def _get():
                response = client.get_secret_value(SecretId=config.secret_name)
                secret_string = response.get("SecretString")

                # If a specific key is requested from JSON secret
                if config.secret_key and secret_string:
                    import json
                    try:
                        data = json.loads(secret_string)
                        return data.get(config.secret_key)
                    except json.JSONDecodeError:
                        pass

                return secret_string

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            logger.error(f"AWS Secrets Manager error: {e}")
            return None

    def _get_aws_client(self, region: str):
        """Get or create AWS client."""
        cache_key = f"aws_{region}"
        if cache_key not in self._vault_clients:
            import boto3
            self._vault_clients[cache_key] = boto3.client(
                "secretsmanager",
                region_name=region,
            )
        return self._vault_clients[cache_key]

    async def _resolve_azure(self, ref: SecretReference) -> Optional[str]:
        """Resolve from Azure Key Vault."""
        if not ref.azure:
            return None

        config = ref.azure

        try:
            from azure.keyvault.secrets import SecretClient

            if config.auth_type == "service_principal":
                from azure.identity import ClientSecretCredential

                # Resolve client secret if it's a reference
                client_secret = None
                if config.client_secret:
                    client_secret = await self.resolve(config.client_secret)

                credential = ClientSecretCredential(
                    tenant_id=config.tenant_id,
                    client_id=config.client_id,
                    client_secret=client_secret,
                )
            else:
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()

            client = SecretClient(vault_url=config.vault_url, credential=credential)

            import asyncio

            def _get():
                secret = client.get_secret(config.secret_name)
                return secret.value

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            logger.error(f"Azure Key Vault error: {e}")
            return None

    async def _resolve_gcp(self, ref: SecretReference) -> Optional[str]:
        """Resolve from Google Cloud Secret Manager."""
        if not ref.gcp:
            return None

        config = ref.gcp

        try:
            from google.cloud import secretmanager

            if config.auth_type == "service_account" and config.service_account_json:
                import base64
                import json
                import tempfile

                # Decode service account JSON
                sa_json = base64.b64decode(config.service_account_json).decode()
                sa_data = json.loads(sa_json)

                # Write to temp file for credentials
                with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                    json.dump(sa_data, f)
                    temp_path = f.name

                client = secretmanager.SecretManagerServiceClient.from_service_account_file(
                    temp_path
                )

                # Clean up temp file
                import os
                os.unlink(temp_path)
            else:
                # Use default credentials
                client = secretmanager.SecretManagerServiceClient()

            import asyncio

            def _get():
                name = f"projects/{config.project_id}/secrets/{config.secret_name}/versions/{config.version}"
                response = client.access_secret_version(request={"name": name})
                return response.payload.data.decode("UTF-8")

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            logger.error(f"GCP Secret Manager error: {e}")
            return None

    async def _resolve_hashicorp(self, ref: SecretReference) -> Optional[str]:
        """Resolve from HashiCorp Vault."""
        if not ref.hashicorp:
            return None

        config = ref.hashicorp

        try:
            import hvac

            # Build auth kwargs based on method
            if config.auth_method == "token":
                client = hvac.Client(url=config.vault_url, token=config.token)
            elif config.auth_method == "approle":
                # Resolve secret_id if it's a reference
                secret_id = None
                if config.secret_id:
                    secret_id = await self.resolve(config.secret_id)

                client = hvac.Client(url=config.vault_url)
                client.auth.approle.login(
                    role_id=config.role_id,
                    secret_id=secret_id,
                )
            elif config.auth_method == "kubernetes":
                client = hvac.Client(url=config.vault_url)
                # Read the service account token
                with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                    jwt = f.read()
                client.auth.kubernetes.login(
                    role=config.kubernetes_role,
                    jwt=jwt,
                )
            else:
                # AWS, LDAP, etc. - use token for now
                client = hvac.Client(url=config.vault_url, token=config.token)

            import asyncio

            def _get():
                secret = client.secrets.kv.v2.read_secret_version(
                    path=config.path,
                    mount_point=config.mount_point,
                )
                data = secret["data"]["data"]
                return data.get(config.key)

            return await asyncio.get_event_loop().run_in_executor(None, _get)
        except Exception as e:
            logger.error(f"HashiCorp Vault error: {e}")
            return None

    async def _resolve_platform(self, ref: SecretReference) -> Optional[str]:
        """Resolve from platform defaults."""
        if not ref.platform_key:
            return None

        # Use the vault manager to get platform-level secrets
        vault = get_vault_manager()
        return await vault.get_secret(
            ref.platform_key,
        )

    async def resolve_header(self, header: HeaderConfig) -> tuple[str, str]:
        """Resolve a header configuration to key-value pair.

        Args:
            header: The header configuration

        Returns:
            Tuple of (header_key, header_value)
        """
        key = header.key

        if isinstance(header.value, SecretReference):
            value = await self.resolve(header.value)
        else:
            value = header.value

        return key, value or ""

    async def resolve_headers(self, headers: list[HeaderConfig]) -> dict[str, str]:
        """Resolve all headers to a dictionary.

        Args:
            headers: List of header configurations

        Returns:
            Dictionary of resolved headers
        """
        result = {}
        for header in headers:
            key, value = await self.resolve_header(header)
            result[key] = value
        return result


# Singleton instance
_resolver: Optional[SecretResolver] = None


def get_secret_resolver() -> SecretResolver:
    """Get a secret resolver instance.

    Returns:
        A SecretResolver instance
    """
    global _resolver
    if _resolver is None:
        _resolver = SecretResolver()
    return _resolver
