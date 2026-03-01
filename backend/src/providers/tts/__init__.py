"""Text-to-Speech providers."""

from src.providers.tts.base import BaseTTSProvider, SpeechResult, VoiceInfo
from src.providers.tts.openai_tts import OpenAITTSProvider
from src.providers.tts.elevenlabs import ElevenLabsProvider
from src.providers.tts.google_tts import GoogleTTSProvider
from src.providers.tts.azure_tts import AzureTTSProvider
from src.providers.tts.playht import PlayHTProvider

__all__ = [
    "BaseTTSProvider",
    "SpeechResult",
    "VoiceInfo",
    "OpenAITTSProvider",
    "ElevenLabsProvider",
    "GoogleTTSProvider",
    "AzureTTSProvider",
    "PlayHTProvider",
]
