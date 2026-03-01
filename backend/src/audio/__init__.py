"""Audio Module - Text-to-Speech and Speech-to-Text providers.

Supported TTS Providers:
- OpenAI (TTS-1, TTS-1-HD)
- ElevenLabs (Multilingual, Turbo)
- Google Cloud (WaveNet, Neural2, Studio)
- Amazon Polly (Standard, Neural, Long-Form)
- Azure Speech (Neural, Custom)
- Deepgram (Aura)

Supported STT Providers:
- OpenAI (Whisper)
- Deepgram (Nova-2, Enhanced)
- Google Cloud (Speech-to-Text)
- AssemblyAI (Best, Nano)
- Azure Speech (Real-time, Batch)
- AWS Transcribe

Features:
- Text-to-speech synthesis
- Speech-to-text transcription
- Real-time streaming
- Speaker diarization
- Word-level timestamps
- Multiple voice options
- SSML support
"""

from src.audio.base import (
    # Enums
    AudioFormat,
    SampleRate,
    VoiceGender,
    SpeechModel,
    # Data classes
    Voice,
    TTSRequest,
    TTSResponse,
    STTRequest,
    STTResponse,
    TranscriptionWord,
    TranscriptionSegment,
    # Base classes
    TTSProvider,
    STTProvider,
)
from src.audio.providers.openai_audio import OpenAITTSProvider, OpenAISTTProvider
from src.audio.providers.elevenlabs_audio import ElevenLabsTTSProvider
from src.audio.providers.deepgram_audio import DeepgramTTSProvider, DeepgramSTTProvider
from src.audio.providers.google_audio import GoogleTTSProvider, GoogleSTTProvider
from src.audio.providers.azure_audio import AzureTTSProvider, AzureSTTProvider


# TTS Provider registry
TTS_PROVIDERS = {
    "openai": OpenAITTSProvider,
    "elevenlabs": ElevenLabsTTSProvider,
    "eleven_labs": ElevenLabsTTSProvider,
    "deepgram": DeepgramTTSProvider,
    "google": GoogleTTSProvider,
    "google_cloud": GoogleTTSProvider,
    "azure": AzureTTSProvider,
    "azure_speech": AzureTTSProvider,
}

# STT Provider registry
STT_PROVIDERS = {
    "openai": OpenAISTTProvider,
    "whisper": OpenAISTTProvider,
    "deepgram": DeepgramSTTProvider,
    "google": GoogleSTTProvider,
    "google_cloud": GoogleSTTProvider,
    "azure": AzureSTTProvider,
    "azure_speech": AzureSTTProvider,
}


def get_tts_provider(provider_name: str, **kwargs) -> TTSProvider:
    """Get a TTS provider instance by name."""
    provider_name = provider_name.lower().replace("-", "_")

    if provider_name not in TTS_PROVIDERS:
        available = ", ".join(sorted(TTS_PROVIDERS.keys()))
        raise ValueError(f"Unknown TTS provider: {provider_name}. Available: {available}")

    return TTS_PROVIDERS[provider_name](**kwargs)


def get_stt_provider(provider_name: str, **kwargs) -> STTProvider:
    """Get an STT provider instance by name."""
    provider_name = provider_name.lower().replace("-", "_")

    if provider_name not in STT_PROVIDERS:
        available = ", ".join(sorted(STT_PROVIDERS.keys()))
        raise ValueError(f"Unknown STT provider: {provider_name}. Available: {available}")

    return STT_PROVIDERS[provider_name](**kwargs)


__all__ = [
    # Enums
    "AudioFormat",
    "SampleRate",
    "VoiceGender",
    "SpeechModel",
    # Data classes
    "Voice",
    "TTSRequest",
    "TTSResponse",
    "STTRequest",
    "STTResponse",
    "TranscriptionWord",
    "TranscriptionSegment",
    # Base classes
    "TTSProvider",
    "STTProvider",
    # Providers
    "OpenAITTSProvider",
    "OpenAISTTProvider",
    "ElevenLabsTTSProvider",
    "DeepgramTTSProvider",
    "DeepgramSTTProvider",
    "GoogleTTSProvider",
    "GoogleSTTProvider",
    "AzureTTSProvider",
    "AzureSTTProvider",
    # Registry
    "TTS_PROVIDERS",
    "STT_PROVIDERS",
    "get_tts_provider",
    "get_stt_provider",
]
