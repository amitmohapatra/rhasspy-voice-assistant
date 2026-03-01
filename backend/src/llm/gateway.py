"""LLM Gateway - Unified interface for all LLM providers."""

from __future__ import annotations

import importlib
from collections.abc import AsyncGenerator
from functools import lru_cache
from typing import Any

from src.core.config import settings
from src.core.exceptions import LLMError
from src.llm.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    Message,
    StreamDelta,
)
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.anthropic_provider import AnthropicProvider


# Lazy-import mapping: provider name -> (module_path, class_name)
_LAZY_IMPORTS: dict[str, tuple[str, str]] = {
    "google": ("src.llm.providers.google_provider", "GoogleGeminiProvider"),
    "azure": ("src.llm.providers.azure_openai_provider", "AzureOpenAIProvider"),
    "azure_openai": ("src.llm.providers.azure_openai_provider", "AzureOpenAIProvider"),
    "bedrock": ("src.llm.providers.bedrock_provider", "AWSBedrockProvider"),
    "cohere": ("src.llm.providers.cohere_provider", "CohereProvider"),
    "groq": ("src.llm.providers.groq_provider", "GroqProvider"),
    "together": ("src.llm.providers.together_provider", "TogetherProvider"),
    "fireworks": ("src.llm.providers.fireworks_provider", "FireworksProvider"),
    "mistral": ("src.llm.providers.mistral_provider", "MistralProvider"),
    "ollama": ("src.llm.providers.ollama_provider", "OllamaProvider"),
}


class LLMGateway:
    """Unified gateway for all LLM providers.

    This gateway provides:
    - Multi-provider support with automatic fallback
    - Unified interface for completions and embeddings
    - Provider-specific configuration
    - Lazy provider registration (cloud SDKs only loaded when needed)
    """

    PROVIDER_MAP: dict[str, type[LLMProvider]] = {
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
    }

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}

    def _lazy_register(self, provider_name: str) -> None:
        """Lazy-import and register a provider to avoid importing all SDKs at startup."""
        if provider_name in _LAZY_IMPORTS:
            module_path, class_name = _LAZY_IMPORTS[provider_name]
            module = importlib.import_module(module_path)
            self.PROVIDER_MAP[provider_name] = getattr(module, class_name)

    def _get_or_create_provider(
        self,
        provider_name: str,
        config: dict[str, Any] | None = None,
    ) -> LLMProvider:
        """Get or create a provider instance."""
        cache_key = f"{provider_name}:{hash(frozenset((config or {}).items()))}"

        if cache_key not in self._providers:
            # Try lazy registration if not already in PROVIDER_MAP
            if provider_name not in self.PROVIDER_MAP:
                self._lazy_register(provider_name)

            if provider_name not in self.PROVIDER_MAP:
                raise LLMError(
                    message=f"Unknown provider: {provider_name}",
                    provider=provider_name,
                )

            provider_class = self.PROVIDER_MAP[provider_name]
            self._providers[cache_key] = provider_class(**(config or {}))

        return self._providers[cache_key]

    async def complete(
        self,
        messages: list[Message],
        model: str,
        provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        connectors: list[dict[str, Any]] | None = None,
        provider_config: dict[str, Any] | None = None,
        fallback_providers: list[str] | None = None,
    ) -> CompletionResponse:
        """Complete a chat request.

        Args:
            messages: List of chat messages
            model: Model name
            provider: Provider name (defaults to settings)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional provider-native tool definitions
            connectors: Optional Cohere connectors
            provider_config: Provider-specific configuration
            fallback_providers: List of fallback providers if primary fails

        Returns:
            CompletionResponse with generated content
        """
        provider_name = provider or settings.default_llm_provider
        providers_to_try = [provider_name] + (fallback_providers or [])

        last_error: Exception | None = None

        for prov in providers_to_try:
            try:
                llm_provider = self._get_or_create_provider(prov, provider_config)

                request = CompletionRequest(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    connectors=connectors,
                    stream=False,
                )

                return await llm_provider.complete(request)

            except LLMError as e:
                last_error = e
                if prov == providers_to_try[-1]:
                    raise
                continue

        # Should never reach here, but just in case
        raise last_error or LLMError("All providers failed")

    async def stream(
        self,
        messages: list[Message],
        model: str,
        provider: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
        connectors: list[dict[str, Any]] | None = None,
        provider_config: dict[str, Any] | None = None,
    ) -> AsyncGenerator[StreamDelta, None]:
        """Stream a chat completion.

        Args:
            messages: List of chat messages
            model: Model name
            provider: Provider name (defaults to settings)
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools: Optional provider-native tool definitions
            connectors: Optional Cohere connectors
            provider_config: Provider-specific configuration

        Yields:
            StreamDelta objects with text or tool call updates
        """
        provider_name = provider or settings.default_llm_provider
        llm_provider = self._get_or_create_provider(provider_name, provider_config)

        request = CompletionRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            connectors=connectors,
            stream=True,
        )

        async for delta in llm_provider.stream(request):
            yield delta

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
        provider: str | None = None,
        provider_config: dict[str, Any] | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of texts to embed
            model: Embedding model name (defaults to settings)
            provider: Provider name (defaults to openai for embeddings)
            provider_config: Provider-specific configuration

        Returns:
            List of embedding vectors
        """
        # Default to OpenAI for embeddings as it's most commonly used
        provider_name = provider or "openai"
        model_name = model or settings.default_embedding_model

        llm_provider = self._get_or_create_provider(provider_name, provider_config)

        return await llm_provider.embed(texts, model_name)

    def get_provider(
        self,
        provider_name: str,
        config: dict[str, Any] | None = None,
    ) -> LLMProvider:
        """Get a specific provider instance."""
        return self._get_or_create_provider(provider_name, config)

    def list_providers(self) -> list[str]:
        """List available providers."""
        all_providers = set(self.PROVIDER_MAP.keys()) | set(_LAZY_IMPORTS.keys())
        return sorted(all_providers)

    def list_models(self, provider: str) -> list[str]:
        """List models for a provider."""
        llm_provider = self._get_or_create_provider(provider)
        return llm_provider.list_models()


@lru_cache
def get_llm_gateway() -> LLMGateway:
    """Get cached LLM gateway instance."""
    return LLMGateway()
