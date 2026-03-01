"""LLM Providers - Support for any LLM from any cloud.

Supported Providers:
- OpenAI (GPT-4o, GPT-4, o1, o3)
- Anthropic (Claude 3.5 Sonnet, Claude 3 Opus)
- Google (Gemini 2.0, Gemini 1.5 Pro/Flash)
- AWS Bedrock (Claude, Llama, Mistral, Titan via AWS)
- Azure OpenAI (OpenAI models with enterprise compliance)
- Mistral AI (Mistral Large, Mixtral, Codestral)
- Cohere (Command R, Command R+)
- Groq (Ultra-fast inference on LPU)
- Together AI (Open-source models at scale)
- Ollama (Local/self-hosted models)
- Fireworks AI (Fast inference)
- Replicate (Any ML model via API)

All providers implement the same interface for easy switching.
"""

from __future__ import annotations

from src.llm.providers.base import (
    LLMProvider,
    CompletionRequest,
    CompletionResponse,
    Message,
    StreamDelta,
    ToolCall,
    ToolDefinition,
)

# Core providers (always available)
from src.llm.providers.openai_provider import OpenAIProvider
from src.llm.providers.anthropic_provider import AnthropicProvider

# Cloud providers
from src.llm.providers.google_provider import GoogleGeminiProvider
from src.llm.providers.bedrock_provider import AWSBedrockProvider
from src.llm.providers.azure_openai_provider import AzureOpenAIProvider

# Specialized providers
from src.llm.providers.mistral_provider import MistralProvider
from src.llm.providers.cohere_provider import CohereProvider
from src.llm.providers.groq_provider import GroqProvider
from src.llm.providers.together_provider import TogetherProvider
from src.llm.providers.fireworks_provider import FireworksProvider
from src.llm.providers.replicate_provider import ReplicateProvider

# Local/self-hosted
from src.llm.providers.ollama_provider import OllamaProvider


# Provider registry for dynamic instantiation
# This maps provider names to their Python class implementations.
# The DB (ai_providers table) is the source of truth for which providers
# are enabled, but this dict is needed to map names to classes.
PROVIDER_CLASSES: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "google": GoogleGeminiProvider,
    "gemini": GoogleGeminiProvider,
    "bedrock": AWSBedrockProvider,
    "aws_bedrock": AWSBedrockProvider,
    "azure_openai": AzureOpenAIProvider,
    "azure": AzureOpenAIProvider,
    "mistral": MistralProvider,
    "cohere": CohereProvider,
    "groq": GroqProvider,
    "together": TogetherProvider,
    "together_ai": TogetherProvider,
    "fireworks": FireworksProvider,
    "fireworks_ai": FireworksProvider,
    "replicate": ReplicateProvider,
    "ollama": OllamaProvider,
    "local": OllamaProvider,
}

# Backward compatibility alias
PROVIDERS = PROVIDER_CLASSES


def get_provider(provider_name: str, **kwargs) -> LLMProvider:
    """Get an LLM provider instance by name.

    This is a fallback function that uses the in-code PROVIDER_CLASSES map.
    For DB-driven provider lookup, use get_provider_from_db() instead.

    Args:
        provider_name: Name of the provider (e.g., "openai", "anthropic", "gemini")
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider is not supported

    Example:
        >>> provider = get_provider("openai", api_key="sk-...")
        >>> provider = get_provider("ollama", host="http://localhost:11434")
        >>> provider = get_provider("bedrock", region="us-east-1")
    """
    provider_name = provider_name.lower().replace("-", "_")

    if provider_name not in PROVIDER_CLASSES:
        available = ", ".join(sorted(PROVIDER_CLASSES.keys()))
        raise ValueError(
            f"Unknown provider: {provider_name}. Available: {available}"
        )

    return PROVIDER_CLASSES[provider_name](**kwargs)


async def get_provider_from_db(
    db,  # AsyncSession
    provider_name: str,
    **kwargs
) -> LLMProvider:
    """Get an LLM provider instance by querying the database.

    This is the DB-driven approach that checks if the provider is active
    in the ai_providers table before instantiating.

    Args:
        db: SQLAlchemy async session
        provider_name: Name of the provider
        **kwargs: Provider-specific configuration

    Returns:
        Configured LLMProvider instance

    Raises:
        ValueError: If provider is not found or not active
    """
    from sqlalchemy import select
    from src.models.ai_model import AIProvider, ProviderStatus

    provider_name = provider_name.lower().replace("-", "_")

    # Query DB to check if provider exists and is active
    result = await db.execute(
        select(AIProvider).where(
            AIProvider.name == provider_name,
            AIProvider.status == ProviderStatus.ACTIVE,
        )
    )
    db_provider = result.scalar_one_or_none()

    if not db_provider:
        raise ValueError(
            f"Provider '{provider_name}' not found or not active in database"
        )

    # Get the class from PROVIDER_CLASSES
    if provider_name not in PROVIDER_CLASSES:
        raise ValueError(
            f"No implementation for provider: {provider_name}"
        )

    return PROVIDER_CLASSES[provider_name](**kwargs)


async def list_active_providers(db) -> list[dict]:
    """List all active providers from the database.

    Returns provider info including name, display_name, and status.
    """
    from sqlalchemy import select
    from src.models.ai_model import AIProvider, ProviderStatus

    result = await db.execute(
        select(AIProvider).where(
            AIProvider.status == ProviderStatus.ACTIVE
        ).order_by(AIProvider.sort_order)
    )
    providers = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "display_name": p.display_name,
            "provider_type": p.provider_type,
            "supports_streaming": p.supports_streaming,
            "supports_function_calling": p.supports_function_calling,
            "supports_vision": p.supports_vision,
            "has_implementation": p.name in PROVIDER_CLASSES,
        }
        for p in providers
    ]


def list_providers() -> list[str]:
    """List all available provider names."""
    return sorted(set(PROVIDERS.keys()))


__all__ = [
    # Base classes
    "LLMProvider",
    "CompletionRequest",
    "CompletionResponse",
    "Message",
    "StreamDelta",
    "ToolCall",
    "ToolDefinition",
    # Provider classes
    "OpenAIProvider",
    "AnthropicProvider",
    "GoogleGeminiProvider",
    "AWSBedrockProvider",
    "AzureOpenAIProvider",
    "MistralProvider",
    "CohereProvider",
    "GroqProvider",
    "TogetherProvider",
    "FireworksProvider",
    "ReplicateProvider",
    "OllamaProvider",
    # Registry (code-based fallback)
    "PROVIDER_CLASSES",
    "PROVIDERS",  # Backward compatibility alias
    "get_provider",
    "list_providers",
    # DB-driven provider access
    "get_provider_from_db",
    "list_active_providers",
]
