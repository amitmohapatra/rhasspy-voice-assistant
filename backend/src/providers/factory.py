"""Provider factory for creating provider instances."""

from src.providers.base import (
    ProviderType,
    ProviderConfig,
    ProviderRegistry,
    BaseProvider,
)

# Import all providers to register them
from src.providers.llm import *
from src.providers.stt import *
from src.providers.tts import *
from src.providers.embeddings import *
from src.providers.vectorstore import *


class ProviderFactory:
    """Factory for creating provider instances."""

    @staticmethod
    def create(config: ProviderConfig) -> BaseProvider:
        """Create a provider instance from configuration."""
        provider_class = ProviderRegistry.get(
            config.provider_type,
            config.provider_name,
        )

        if not provider_class:
            raise ValueError(
                f"Unknown provider: {config.provider_name} "
                f"for type: {config.provider_type}"
            )

        return provider_class(config)

    @staticmethod
    def create_llm(provider_name: str, api_key: str | None = None, **kwargs) -> "BaseLLMProvider":
        """Create an LLM provider."""
        from src.providers.llm.base import BaseLLMProvider

        config = ProviderConfig(
            provider_type=ProviderType.LLM,
            provider_name=provider_name,
            api_key=api_key,
            **kwargs,
        )
        provider = ProviderFactory.create(config)
        assert isinstance(provider, BaseLLMProvider)
        return provider

    @staticmethod
    def create_stt(provider_name: str, api_key: str | None = None, **kwargs) -> "BaseSTTProvider":
        """Create an STT provider."""
        from src.providers.stt.base import BaseSTTProvider

        config = ProviderConfig(
            provider_type=ProviderType.STT,
            provider_name=provider_name,
            api_key=api_key,
            **kwargs,
        )
        provider = ProviderFactory.create(config)
        assert isinstance(provider, BaseSTTProvider)
        return provider

    @staticmethod
    def create_tts(provider_name: str, api_key: str | None = None, **kwargs) -> "BaseTTSProvider":
        """Create a TTS provider."""
        from src.providers.tts.base import BaseTTSProvider

        config = ProviderConfig(
            provider_type=ProviderType.TTS,
            provider_name=provider_name,
            api_key=api_key,
            **kwargs,
        )
        provider = ProviderFactory.create(config)
        assert isinstance(provider, BaseTTSProvider)
        return provider

    @staticmethod
    def create_embeddings(provider_name: str, api_key: str | None = None, **kwargs) -> "BaseEmbeddingsProvider":
        """Create an embeddings provider."""
        from src.providers.embeddings.base import BaseEmbeddingsProvider

        config = ProviderConfig(
            provider_type=ProviderType.EMBEDDINGS,
            provider_name=provider_name,
            api_key=api_key,
            **kwargs,
        )
        provider = ProviderFactory.create(config)
        assert isinstance(provider, BaseEmbeddingsProvider)
        return provider

    @staticmethod
    def create_vectorstore(provider_name: str, **kwargs) -> "BaseVectorStoreProvider":
        """Create a vector store provider."""
        from src.providers.vectorstore.base import BaseVectorStoreProvider

        config = ProviderConfig(
            provider_type=ProviderType.VECTORSTORE,
            provider_name=provider_name,
            **kwargs,
        )
        provider = ProviderFactory.create(config)
        assert isinstance(provider, BaseVectorStoreProvider)
        return provider
