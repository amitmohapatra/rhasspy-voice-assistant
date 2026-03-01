"""Base provider classes and registry.

Provider Visibility:
- CLIENT_VISIBLE: Shown in client/organization settings UI
- PLATFORM_ONLY: Internal platform use only (not shown to clients)
- ADVANCED: Shown only in advanced settings (collapsed by default)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, TypeVar, Generic
from pydantic import BaseModel, Field


class ProviderType(str, Enum):
    """Types of providers available."""
    LLM = "llm"
    STT = "stt"
    TTS = "tts"
    EMBEDDINGS = "embeddings"
    VECTORSTORE = "vectorstore"
    RERANKER = "reranker"


class ProviderVisibility(str, Enum):
    """Controls where the provider is shown to users."""
    CLIENT_VISIBLE = "client_visible"  # Shown in org settings UI
    PLATFORM_ONLY = "platform_only"    # Internal use only (hidden from clients)
    ADVANCED = "advanced"              # Shown in advanced/collapsed section


class ProviderConfig(BaseModel):
    """Configuration for a provider."""
    provider_type: ProviderType
    provider_name: str
    api_key: str | None = None
    api_base: str | None = None
    model: str | None = None
    settings: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class ProviderInfo(BaseModel):
    """Information about an available provider."""
    name: str
    display_name: str
    provider_type: ProviderType
    description: str
    models: list[dict[str, Any]] = Field(default_factory=list)
    requires_api_key: bool = True
    settings_schema: dict[str, Any] = Field(default_factory=dict)
    # Visibility control
    visibility: ProviderVisibility = ProviderVisibility.CLIENT_VISIBLE
    # Indicates if this is a recommended/default option
    is_recommended: bool = False
    # Category for grouping in UI (e.g., "Cloud", "Self-hosted", "Local")
    category: str = "general"


T = TypeVar("T")


class BaseProvider(ABC, Generic[T]):
    """Base class for all providers."""

    provider_type: ProviderType
    provider_name: str
    display_name: str
    description: str
    requires_api_key: bool = True
    # Visibility control - override in subclass as needed
    visibility: ProviderVisibility = ProviderVisibility.CLIENT_VISIBLE
    is_recommended: bool = False
    category: str = "general"  # "cloud", "self-hosted", "local", "enterprise"

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate the provider configuration."""
        if self.requires_api_key and not self.config.api_key:
            raise ValueError(f"{self.display_name} requires an API key")

    @classmethod
    @abstractmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        """Get list of available models for this provider."""
        pass

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        """Get JSON schema for provider-specific settings."""
        return {}

    @classmethod
    def get_info(cls) -> ProviderInfo:
        """Get provider information."""
        return ProviderInfo(
            name=cls.provider_name,
            display_name=cls.display_name,
            provider_type=cls.provider_type,
            description=cls.description,
            models=cls.get_available_models(),
            requires_api_key=cls.requires_api_key,
            settings_schema=cls.get_settings_schema(),
            visibility=cls.visibility,
            is_recommended=cls.is_recommended,
            category=cls.category,
        )


class ProviderRegistry:
    """Registry of available providers."""

    _providers: dict[ProviderType, dict[str, type[BaseProvider]]] = {
        ProviderType.LLM: {},
        ProviderType.STT: {},
        ProviderType.TTS: {},
        ProviderType.EMBEDDINGS: {},
        ProviderType.VECTORSTORE: {},
        ProviderType.RERANKER: {},
    }

    @classmethod
    def register(cls, provider_class: type[BaseProvider]) -> type[BaseProvider]:
        """Register a provider class."""
        provider_type = provider_class.provider_type
        provider_name = provider_class.provider_name
        cls._providers[provider_type][provider_name] = provider_class
        return provider_class

    @classmethod
    def get(cls, provider_type: ProviderType, provider_name: str) -> type[BaseProvider] | None:
        """Get a provider class by type and name."""
        return cls._providers.get(provider_type, {}).get(provider_name)

    @classmethod
    def list_providers(
        cls,
        provider_type: ProviderType,
        visibility: ProviderVisibility | list[ProviderVisibility] | None = None,
    ) -> list[ProviderInfo]:
        """List all providers of a given type.

        Args:
            provider_type: Type of provider to list
            visibility: Filter by visibility level(s). None = all providers.
        """
        providers = cls._providers.get(provider_type, {})
        all_info = [p.get_info() for p in providers.values()]

        if visibility is None:
            return all_info

        # Convert single visibility to list
        if isinstance(visibility, ProviderVisibility):
            visibility = [visibility]

        return [p for p in all_info if p.visibility in visibility]

    @classmethod
    def list_client_providers(cls, provider_type: ProviderType) -> list[ProviderInfo]:
        """List only providers visible to clients (not platform-only)."""
        return cls.list_providers(
            provider_type,
            visibility=[ProviderVisibility.CLIENT_VISIBLE, ProviderVisibility.ADVANCED]
        )

    @classmethod
    def list_all_providers(
        cls,
        visibility: ProviderVisibility | list[ProviderVisibility] | None = None,
    ) -> dict[str, list[ProviderInfo]]:
        """List all providers grouped by type."""
        return {
            pt.value: cls.list_providers(pt, visibility)
            for pt in ProviderType
        }

    @classmethod
    def list_all_client_providers(cls) -> dict[str, list[ProviderInfo]]:
        """List all providers visible to clients, grouped by type."""
        return cls.list_all_providers(
            visibility=[ProviderVisibility.CLIENT_VISIBLE, ProviderVisibility.ADVANCED]
        )
