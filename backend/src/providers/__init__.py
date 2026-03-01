"""Multi-vendor provider system.

This module provides a unified interface for various AI services:
- LLM: Language models (OpenAI, Anthropic, Google, AWS Bedrock, local models)
- STT: Speech-to-Text (OpenAI Whisper, Google, Azure, Deepgram, AssemblyAI)
- TTS: Text-to-Speech (OpenAI, ElevenLabs, Google, Azure, PlayHT)
- Embeddings: Vector embeddings (OpenAI, Cohere, Voyage, BGE-M3, local models)
- VectorStore: Vector databases (Qdrant)
- Reranker: Cross-encoder reranking (Jina v2 recommended, BGE-Reranker-v2-m3)

Users can mix and match providers for each component.
"""

from src.providers.base import (
    ProviderType,
    ProviderVisibility,
    ProviderConfig,
    ProviderInfo,
    ProviderRegistry,
    BaseProvider,
)
from src.providers.factory import ProviderFactory

# Import providers to register them
from src.providers import stt
from src.providers import tts
from src.providers import embeddings
from src.providers import vectorstore
from src.providers import reranker

__all__ = [
    # Core classes
    "ProviderType",
    "ProviderVisibility",
    "ProviderConfig",
    "ProviderInfo",
    "ProviderRegistry",
    "BaseProvider",
    "ProviderFactory",
    # Provider modules
    "stt",
    "tts",
    "embeddings",
    "vectorstore",
    "reranker",
]
