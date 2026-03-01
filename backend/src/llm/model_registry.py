"""Model Registry Integration for LLM Providers.

This module provides a caching layer and helper functions for LLM providers
to fetch model information from the database registry.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_model import (
    AIProvider,
    AIModel,
    ProviderStatus,
    ModelStatus,
    ModelCategory,
)


class ModelRegistryCache:
    """In-memory cache for model registry data.

    Provides fast lookups for model information without hitting the database
    on every request. Cache is refreshed periodically.
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._providers: dict[str, dict[str, Any]] = {}
        self._models: dict[str, dict[str, Any]] = {}
        self._aliases: dict[str, str] = {}  # alias -> model_id
        self._provider_models: dict[str, list[str]] = {}  # provider_name -> [model_ids]
        self._last_refresh: datetime | None = None
        self._lock = asyncio.Lock()

    @property
    def is_stale(self) -> bool:
        """Check if cache needs refresh."""
        if self._last_refresh is None:
            return True
        return datetime.utcnow() - self._last_refresh > timedelta(seconds=self.ttl_seconds)

    async def refresh(self, db: AsyncSession) -> None:
        """Refresh cache from database."""
        async with self._lock:
            # Fetch all active providers with their models
            query = (
                select(AIProvider)
                .options(selectinload(AIProvider.models))
                .where(AIProvider.status == ProviderStatus.ACTIVE)
            )
            result = await db.execute(query)
            providers = result.scalars().all()

            # Clear existing cache
            self._providers.clear()
            self._models.clear()
            self._aliases.clear()
            self._provider_models.clear()

            # Populate cache
            for provider in providers:
                provider_data = {
                    "id": str(provider.id),
                    "name": provider.name,
                    "display_name": provider.display_name,
                    "base_url": provider.base_url,
                    "supports_streaming": provider.supports_streaming,
                    "supports_function_calling": provider.supports_function_calling,
                    "supports_vision": provider.supports_vision,
                    "supports_audio": provider.supports_audio,
                    "required_secrets": provider.required_secrets or [],
                }
                self._providers[provider.name] = provider_data
                self._provider_models[provider.name] = []

                for model in provider.models:
                    if model.status not in (ModelStatus.ACTIVE, ModelStatus.BETA):
                        continue

                    model_data = {
                        "id": str(model.id),
                        "model_id": model.model_id,
                        "name": model.name,
                        "display_name": model.display_name,
                        "provider_name": provider.name,
                        "category": model.category.value,
                        "context_window": model.context_window,
                        "max_output_tokens": model.max_output_tokens,
                        "supports_tools": model.supports_tools,
                        "supports_vision": model.supports_vision,
                        "supports_audio": model.supports_audio,
                        "supports_streaming": model.supports_streaming,
                        "supports_json_mode": model.supports_json_mode,
                        "is_reasoning_model": model.is_reasoning_model,
                        "is_moe": model.is_moe,
                        "input_price_per_1m": float(model.input_price_per_1m) if model.input_price_per_1m else None,
                        "output_price_per_1m": float(model.output_price_per_1m) if model.output_price_per_1m else None,
                        "default_temperature": float(model.default_temperature) if model.default_temperature else None,
                        "default_max_tokens": model.default_max_tokens,
                    }
                    self._models[model.model_id] = model_data
                    self._provider_models[provider.name].append(model.model_id)

                    # Register aliases
                    if model.aliases:
                        for alias in model.aliases:
                            self._aliases[alias.lower()] = model.model_id
                    # Also register name as alias
                    self._aliases[model.name.lower()] = model.model_id

            self._last_refresh = datetime.utcnow()

    def get_provider(self, provider_name: str) -> dict[str, Any] | None:
        """Get provider information."""
        return self._providers.get(provider_name)

    def get_model(self, model_id: str) -> dict[str, Any] | None:
        """Get model information by model_id."""
        return self._models.get(model_id)

    def resolve_alias(self, alias: str) -> str | None:
        """Resolve model alias to model_id."""
        # First check if it's already a valid model_id
        if alias in self._models:
            return alias
        # Then check aliases
        return self._aliases.get(alias.lower())

    def list_provider_models(self, provider_name: str) -> list[str]:
        """List all model IDs for a provider."""
        return self._provider_models.get(provider_name, [])

    def supports_tools(self, model_id: str) -> bool:
        """Check if model supports function calling."""
        model = self.get_model(model_id)
        if model:
            return model.get("supports_tools", False)
        return False

    def supports_vision(self, model_id: str) -> bool:
        """Check if model supports vision."""
        model = self.get_model(model_id)
        if model:
            return model.get("supports_vision", False)
        return False

    def get_context_window(self, model_id: str) -> int:
        """Get model context window size."""
        model = self.get_model(model_id)
        if model:
            return model.get("context_window", 4096)
        return 4096


# Global cache instance
_cache: ModelRegistryCache | None = None


def get_model_cache() -> ModelRegistryCache:
    """Get or create the global model cache."""
    global _cache
    if _cache is None:
        _cache = ModelRegistryCache()
    return _cache


async def ensure_cache_fresh(db: AsyncSession) -> ModelRegistryCache:
    """Ensure cache is fresh and return it."""
    cache = get_model_cache()
    if cache.is_stale:
        await cache.refresh(db)
    return cache


class RegistryAwareProvider:
    """Mixin class for providers that use the model registry.

    Add this as a base class to enable registry-based model lookups.
    """

    _registry_cache: ModelRegistryCache | None = None

    @classmethod
    async def init_registry(cls, db: AsyncSession) -> None:
        """Initialize registry cache for this provider."""
        cls._registry_cache = await ensure_cache_fresh(db)

    @classmethod
    def resolve_model(cls, model: str) -> str:
        """Resolve model alias to official model_id."""
        if cls._registry_cache is None:
            return model
        resolved = cls._registry_cache.resolve_alias(model)
        return resolved if resolved else model

    @classmethod
    def get_model_info(cls, model: str) -> dict[str, Any] | None:
        """Get model information from registry."""
        if cls._registry_cache is None:
            return None
        model_id = cls.resolve_model(model)
        return cls._registry_cache.get_model(model_id)

    @classmethod
    def supports_tools(cls, model: str) -> bool:
        """Check if model supports function calling."""
        if cls._registry_cache is None:
            return True  # Default to true if no registry
        model_id = cls.resolve_model(model)
        return cls._registry_cache.supports_tools(model_id)

    @classmethod
    def supports_vision(cls, model: str) -> bool:
        """Check if model supports vision."""
        if cls._registry_cache is None:
            return False
        model_id = cls.resolve_model(model)
        return cls._registry_cache.supports_vision(model_id)

    @classmethod
    def get_context_window(cls, model: str) -> int:
        """Get model context window."""
        if cls._registry_cache is None:
            return 4096
        model_id = cls.resolve_model(model)
        return cls._registry_cache.get_context_window(model_id)


async def get_available_models(
    db: AsyncSession,
    provider_name: str | None = None,
    category: ModelCategory | None = None,
    supports_tools: bool | None = None,
    supports_vision: bool | None = None,
) -> list[dict[str, Any]]:
    """Get available models with optional filtering.

    This is a convenience function for getting model information
    without going through the full service layer.
    """
    cache = await ensure_cache_fresh(db)

    models = []
    for model_id, model_data in cache._models.items():
        # Apply filters
        if provider_name and model_data["provider_name"] != provider_name:
            continue
        if category and model_data["category"] != category.value:
            continue
        if supports_tools is not None and model_data["supports_tools"] != supports_tools:
            continue
        if supports_vision is not None and model_data["supports_vision"] != supports_vision:
            continue

        models.append(model_data)

    return models


async def resolve_model_for_provider(
    db: AsyncSession,
    provider_name: str,
    model: str,
) -> str:
    """Resolve a model identifier for a specific provider.

    Handles aliases and validates the model exists for the provider.
    Returns the official model_id.
    """
    cache = await ensure_cache_fresh(db)

    # First try to resolve as alias
    resolved = cache.resolve_alias(model)
    if resolved:
        model_info = cache.get_model(resolved)
        if model_info and model_info["provider_name"] == provider_name:
            return resolved

    # Check if it's a direct model_id for this provider
    model_info = cache.get_model(model)
    if model_info and model_info["provider_name"] == provider_name:
        return model

    # Model not found for this provider, return as-is
    # (let the provider API handle the error)
    return model
