"""Base TTS provider class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, AsyncIterator
from pydantic import BaseModel

from src.providers.base import BaseProvider, ProviderType


class VoiceInfo(BaseModel):
    """Information about a voice."""
    id: str
    name: str
    language: str
    gender: str | None = None
    preview_url: str | None = None
    description: str | None = None


class SpeechResult(BaseModel):
    """Result of speech synthesis."""
    audio: bytes
    format: str = "mp3"
    sample_rate: int | None = None
    duration_seconds: float | None = None


class BaseTTSProvider(BaseProvider[SpeechResult]):
    """Base class for Text-to-Speech providers."""

    provider_type = ProviderType.TTS

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> SpeechResult:
        """Synthesize speech from text.

        Args:
            text: Text to convert to speech
            voice: Voice ID to use
            **kwargs: Provider-specific options

        Returns:
            SpeechResult with audio data
        """
        pass

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech.

        Args:
            text: Text to convert to speech
            voice: Voice ID to use
            **kwargs: Provider-specific options

        Yields:
            Audio chunks as they become available
        """
        raise NotImplementedError(
            f"{self.display_name} does not support streaming synthesis"
        )
        yield  # Make this a generator

    @classmethod
    @abstractmethod
    def get_available_voices(cls) -> list[VoiceInfo]:
        """Get list of available voices."""
        pass

    @classmethod
    def get_supported_formats(cls) -> list[str]:
        """Get list of supported audio output formats."""
        return ["mp3", "wav", "ogg"]
