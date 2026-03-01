"""Base STT provider class."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any, AsyncIterator, BinaryIO
from pydantic import BaseModel

from src.providers.base import BaseProvider, ProviderType


class TranscriptionResult(BaseModel):
    """Result of a transcription."""
    text: str
    language: str | None = None
    confidence: float | None = None
    words: list[dict[str, Any]] | None = None
    duration_seconds: float | None = None


class TranscriptionSegment(BaseModel):
    """A segment of transcription (for streaming)."""
    text: str
    is_final: bool = False
    confidence: float | None = None
    start_time: float | None = None
    end_time: float | None = None


class BaseSTTProvider(BaseProvider[TranscriptionResult]):
    """Base class for Speech-to-Text providers."""

    provider_type = ProviderType.STT

    @abstractmethod
    async def transcribe(
        self,
        audio: bytes | BinaryIO,
        language: str | None = None,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio to text.

        Args:
            audio: Audio data as bytes or file-like object
            language: Optional language code (e.g., 'en', 'es')
            **kwargs: Provider-specific options

        Returns:
            TranscriptionResult with the transcribed text
        """
        pass

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
        **kwargs,
    ) -> AsyncIterator[TranscriptionSegment]:
        """Stream transcription of audio.

        Args:
            audio_stream: Async iterator of audio chunks
            language: Optional language code
            **kwargs: Provider-specific options

        Yields:
            TranscriptionSegment objects as they become available
        """
        raise NotImplementedError(
            f"{self.display_name} does not support streaming transcription"
        )
        yield  # Make this a generator

    @classmethod
    def get_supported_formats(cls) -> list[str]:
        """Get list of supported audio formats."""
        return ["wav", "mp3", "webm", "ogg", "flac", "m4a"]

    @classmethod
    def get_supported_languages(cls) -> list[dict[str, str]]:
        """Get list of supported languages."""
        return [
            {"code": "en", "name": "English"},
            {"code": "es", "name": "Spanish"},
            {"code": "fr", "name": "French"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
        ]
