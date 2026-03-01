"""Speech-to-Text providers."""

from src.providers.stt.base import BaseSTTProvider, TranscriptionResult
from src.providers.stt.openai_whisper import OpenAIWhisperProvider
from src.providers.stt.deepgram import DeepgramProvider
from src.providers.stt.assemblyai import AssemblyAIProvider
from src.providers.stt.google_stt import GoogleSTTProvider
from src.providers.stt.azure_stt import AzureSTTProvider

__all__ = [
    "BaseSTTProvider",
    "TranscriptionResult",
    "OpenAIWhisperProvider",
    "DeepgramProvider",
    "AssemblyAIProvider",
    "GoogleSTTProvider",
    "AzureSTTProvider",
]
