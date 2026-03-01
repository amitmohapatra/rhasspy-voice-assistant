"""RAG Pipeline Configuration Schemas.

Fixed pipeline - no user-configurable chunking or retrieval parameters.
All processing is handled automatically by the platform.

Fixed components:
- Docling HybridChunker (structure-aware)
- Contextual enrichment (LLM-generated context per chunk)
- Parent-child retrieval
- BGE-M3 ONNX int8 (embedding)
- 3-way hybrid retrieval (dense + sparse + BM25 with RRF)
- BGE-reranker-v2-m3 (reranker)
- Redis (cache)

Supports:
- Multiple secret sources (Direct, Env, AWS, Azure, GCP, HashiCorp, Platform)
- Any REST API configuration
- Cloud and local deployments
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, field_validator
import json


# ============================================================================
# SECRET REFERENCE - Universal secret source configuration
# ============================================================================

class SecretSource(str, Enum):
    """Sources for retrieving secrets."""
    DIRECT = "direct"
    ENV = "env"
    AWS_SECRETS = "aws_secrets"
    AZURE_KEYVAULT = "azure_keyvault"
    GCP_SECRETS = "gcp_secrets"
    HASHICORP_VAULT = "hashicorp_vault"
    PLATFORM_DEFAULT = "platform_default"


class AWSSecretsConfig(BaseModel):
    """AWS Secrets Manager configuration."""
    region: str = "us-east-1"
    secret_name: str
    secret_key: Optional[str] = None
    auth_type: Literal["iam_role", "access_keys"] = "iam_role"
    access_key_id: Optional[str] = None
    secret_access_key: Optional["SecretReference"] = None


class AzureKeyVaultConfig(BaseModel):
    """Azure Key Vault configuration."""
    vault_url: str
    secret_name: str
    auth_type: Literal["managed_identity", "service_principal"] = "managed_identity"
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional["SecretReference"] = None


class GCPSecretsConfig(BaseModel):
    """Google Cloud Secret Manager configuration."""
    project_id: str
    secret_name: str
    version: str = "latest"
    auth_type: Literal["default", "service_account"] = "default"
    service_account_json: Optional[str] = None


class HashiCorpVaultConfig(BaseModel):
    """HashiCorp Vault configuration."""
    vault_url: str
    path: str
    key: str
    mount_point: str = "secret"
    auth_method: Literal["token", "approle", "kubernetes", "aws", "ldap"] = "token"
    token: Optional[str] = None
    role_id: Optional[str] = None
    secret_id: Optional["SecretReference"] = None
    kubernetes_role: Optional[str] = None


class SecretReference(BaseModel):
    """Universal secret reference supporting multiple sources."""
    source: SecretSource = SecretSource.DIRECT
    value: Optional[str] = None
    env_var: Optional[str] = None
    aws: Optional[AWSSecretsConfig] = None
    azure: Optional[AzureKeyVaultConfig] = None
    gcp: Optional[GCPSecretsConfig] = None
    hashicorp: Optional[HashiCorpVaultConfig] = None
    platform_key: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


# Update forward references
AWSSecretsConfig.model_rebuild()
AzureKeyVaultConfig.model_rebuild()
HashiCorpVaultConfig.model_rebuild()


# ============================================================================
# HEADER CONFIGURATION - For REST API calls
# ============================================================================

class HeaderConfig(BaseModel):
    """HTTP header configuration."""
    key: str
    value: str | SecretReference
    is_secret: bool = False

    @field_validator('value', mode='before')
    @classmethod
    def parse_value(cls, v):
        if isinstance(v, dict):
            return SecretReference(**v)
        return v


# ============================================================================
# REST API CONFIGURATION - Universal for any API
# ============================================================================

class ContentType(str, Enum):
    """Supported content types for REST APIs."""
    JSON = "application/json"
    MULTIPART = "multipart/form-data"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    TEXT = "text/plain"
    BINARY = "application/octet-stream"


class InputFormat(str, Enum):
    """How to encode input data."""
    BASE64 = "base64"
    BINARY = "binary"
    URL = "url"
    TEXT = "text"


class ResponseType(str, Enum):
    """Response format from API."""
    JSON = "json"
    TEXT = "text"
    BINARY = "binary"


class MultipartField(BaseModel):
    """Field configuration for multipart requests."""
    field_name: str
    field_type: Literal["file", "text"] = "text"
    value: str


class RestApiConfig(BaseModel):
    """Universal REST API configuration."""
    name: str
    enabled: bool = True
    endpoint_url: str
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"] = "POST"
    headers: list[HeaderConfig] = Field(default_factory=list)
    content_type: ContentType = ContentType.JSON
    input_format: InputFormat = InputFormat.BASE64
    request_body_template: Optional[str] = None
    multipart_fields: Optional[list[MultipartField]] = None
    form_fields: Optional[dict[str, str]] = None
    response_type: ResponseType = ResponseType.JSON
    output_extraction: Optional[str] = None
    timeout_seconds: int = 30
    retry_count: int = 2
    max_file_size_mb: int = 10

    def get_request_body(self) -> Optional[dict]:
        """Parse request body template to dict."""
        if self.request_body_template:
            try:
                return json.loads(self.request_body_template)
            except Exception:
                return None
        return None


# ============================================================================
# DOCUMENT PROCESSING CONFIGURATION (fixed defaults)
# ============================================================================

class DocumentProcessingConfig(BaseModel):
    """Document processing configuration (all fixed).

    Docling handles all document parsing:
    - RapidOCR PP-OCRv5 for 106-language OCR
    - PP-DocBee VLM for image/chart description (via PictureDescriptionVlmOptions)
    img2table handles borderless table extraction.
    """
    pass


# ============================================================================
# PIPELINE INFO
# ============================================================================

def get_pipeline_info() -> dict:
    """Get information about the fixed RAG pipeline."""
    return {
        "chunking": "Docling HybridChunker (structure-aware, auto-adapts)",
        "embedding": "Late chunking with BGE-M3 (document-context-aware, zero LLM calls)",
        "parent_child_retrieval": "Search small chunks, return parent sections",
        "retrieval": "3-way hybrid (dense+sparse+BM25 with RRF)",
        "reranker": "BGE-reranker-v2-m3",
        "vector_store": "Qdrant (named vectors)",
        "cache": "Redis",
        "document_enrichment": "Docling (PP-DocBee VLM + RapidOCR PP-OCRv5) + img2table",
    }
