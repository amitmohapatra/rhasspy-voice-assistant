"""Application configuration using Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = Field(default="AI Platform")
    project_name: str = Field(default="AI Platform")
    version: str = Field(default="1.0.0")
    api_v1_prefix: str = Field(default="/api/v1")
    app_env: str = Field(default="development")
    debug: bool = Field(default=True)
    secret_key: str = Field(default="change-me-in-production")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_platform"
    )
    database_pool_size: int = Field(default=20)
    database_max_overflow: int = Field(default=10)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Storage (local, s3, azure_blob, or gcs)
    storage_type: str = Field(default="local")  # "local", "s3", "azure_blob", "gcs"
    storage_path: str = Field(default="./storage")  # For local storage

    # AWS Configuration
    aws_access_key_id: str | None = Field(default=None)
    aws_secret_access_key: str | None = Field(default=None)
    aws_region: str = Field(default="us-east-1")

    # S3 Storage
    s3_bucket: str | None = Field(default=None)
    s3_endpoint_url: str | None = Field(default=None)  # For LocalStack: http://localhost:4566
    s3_use_ssl: bool = Field(default=True)  # False for LocalStack

    # Azure Blob Storage
    azure_storage_connection_string: str | None = Field(default=None)
    azure_storage_container: str | None = Field(default=None)
    azure_storage_account_name: str | None = Field(default=None)
    azure_storage_account_key: str | None = Field(default=None)
    azure_storage_endpoint_url: str | None = Field(default=None)  # For Azurite

    # GCP Cloud Storage
    gcp_project_id: str | None = Field(default=None)
    gcp_storage_bucket: str | None = Field(default=None)
    gcp_credentials_json: str | None = Field(default=None)  # Path to service account JSON
    gcp_storage_endpoint_url: str | None = Field(default=None)  # For fake-gcs-server

    # AWS RDS (production database)
    # Uses DATABASE_URL, but these are for reference
    rds_instance_class: str = Field(default="db.t3.medium")
    rds_allocated_storage: int = Field(default=20)

    # AWS ElastiCache (production Redis)
    # Uses REDIS_URL, but these are for reference
    elasticache_node_type: str = Field(default="cache.t3.micro")

    # LLM Providers
    openai_api_key: str | None = Field(default=None)
    openai_base_url: str | None = Field(default=None)
    anthropic_api_key: str | None = Field(default=None)
    google_api_key: str | None = Field(default=None)
    cohere_api_key: str | None = Field(default=None)
    voyage_api_key: str | None = Field(default=None)

    # Vector Database (Qdrant recommended)
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = Field(default=None)
    qdrant_prefer_grpc: bool = Field(default=False)

    # ColSmol visual page retrieval (requires ~500MB extra RAM in inference container)
    colsmol_enabled: bool = Field(default=False)

    # Default LLM Settings
    default_llm_provider: str = Field(default="openai")
    default_llm_model: str = Field(default="gpt-4o")
    default_embedding_model: str = Field(default="BAAI/bge-m3")
    default_embedding_dimensions: int = Field(default=1024)

    # Audio Settings
    tts_provider: str = Field(default="openai")
    tts_model: str = Field(default="tts-1")
    tts_voice: str = Field(default="nova")
    stt_provider: str = Field(default="openai")
    stt_model: str = Field(default="whisper-1")

    # JWT Settings
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)

    # CORS
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # Celery
    celery_broker_url: str = Field(default="redis://localhost:6379/1")
    celery_result_backend: str = Field(default="redis://localhost:6379/2")

    # HTTP/2 and Server Configuration
    server_host: str = Field(default="0.0.0.0")
    server_port: int = Field(default=8000)
    server_workers: int = Field(default=4)
    http2_enabled: bool = Field(default=True)
    ssl_certfile: str | None = Field(default=None)
    ssl_keyfile: str | None = Field(default=None)
    keepalive_timeout: int = Field(default=30)
    access_log: bool = Field(default=True)

    # Connection Pool Settings
    http_client_timeout: int = Field(default=30)
    http_client_pool_size: int = Field(default=100)
    http_client_pool_maxsize: int = Field(default=100)

    # ML Processing
    ml_process_pool_workers: int = Field(default=4)
    ml_thread_pool_workers: int = Field(default=8)
    ml_max_concurrent_requests: int = Field(default=10)
    ml_cache_ttl: int = Field(default=3600)
    ml_circuit_breaker_threshold: int = Field(default=5)
    ml_circuit_breaker_timeout: int = Field(default=60)

    # Inference Service
    inference_service_url: str = Field(default="http://localhost:8001")
    inference_service_timeout: int = Field(default=1200)

    # Encryption (for storing sensitive data)
    encryption_key: str | None = Field(default=None)
    encryption_salt: str = Field(default="rhasspy-voice-assistant-salt")
    encryption_previous_keys: list[str] | None = Field(default=None)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> list[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
