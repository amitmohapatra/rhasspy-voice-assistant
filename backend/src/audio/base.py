"""Base classes for Audio/Speech providers (TTS and STT)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, AsyncIterator, BinaryIO
from uuid import UUID, uuid4


class AudioFormat(str, Enum):
    """Supported audio formats."""
    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"
    FLAC = "flac"
    AAC = "aac"
    OPUS = "opus"
    PCM = "pcm"
    WEBM = "webm"


class SampleRate(int, Enum):
    """Common sample rates."""
    LOW = 8000       # Phone quality
    MEDIUM = 16000   # Speech recognition
    STANDARD = 22050 # Standard audio
    HIGH = 24000     # High quality speech
    CD = 44100       # CD quality
    STUDIO = 48000   # Studio quality


class VoiceGender(str, Enum):
    """Voice gender options."""
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class SpeechModel(str, Enum):
    """Speech recognition models."""
    DEFAULT = "default"
    PHONE_CALL = "phone_call"
    VIDEO = "video"
    COMMAND = "command"
    ENHANCED = "enhanced"


@dataclass
class Voice:
    """Voice configuration for TTS."""
    id: str
    name: str
    language: str
    gender: VoiceGender = VoiceGender.NEUTRAL
    description: Optional[str] = None
    preview_url: Optional[str] = None
    provider: str = ""

    # Voice characteristics
    age: Optional[str] = None  # "young", "middle_aged", "old"
    accent: Optional[str] = None
    style: Optional[str] = None  # "conversational", "newscast", "assistant"

    # Provider-specific metadata
    metadata: dict = field(default_factory=dict)


@dataclass
class TTSRequest:
    """Request for text-to-speech synthesis."""
    text: str

    # Voice settings
    voice: Optional[str] = None  # Voice ID
    language: Optional[str] = None

    # Model settings
    model: Optional[str] = None

    # Audio output settings
    audio_format: AudioFormat = AudioFormat.MP3
    sample_rate: Optional[SampleRate] = None

    # Speech control
    speed: float = 1.0  # 0.25 to 4.0
    pitch: float = 0.0  # -20 to 20 semitones
    volume: float = 0.0  # -96 to 16 dB

    # Advanced settings
    style: Optional[str] = None  # Speaking style
    style_degree: float = 1.0  # 0.01 to 2.0
    role: Optional[str] = None  # Character role for some providers

    # SSML support
    use_ssml: bool = False

    # Streaming
    stream: bool = False

    # Additional options
    extra_options: dict = field(default_factory=dict)


@dataclass
class TTSResponse:
    """Response from text-to-speech synthesis."""
    id: UUID = field(default_factory=uuid4)

    # Audio data
    audio_data: Optional[bytes] = None
    audio_url: Optional[str] = None

    # Audio metadata
    audio_format: AudioFormat = AudioFormat.MP3
    sample_rate: int = 24000
    duration_seconds: float = 0.0

    # Model info
    model: str = ""
    voice: str = ""
    provider: str = ""

    # Usage
    characters_used: int = 0
    cost_usd: float = 0.0

    # Timing
    synthesis_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Errors
    error: Optional[str] = None


@dataclass
class STTRequest:
    """Request for speech-to-text transcription."""
    # Audio input (one of these required)
    audio_data: Optional[bytes] = None
    audio_url: Optional[str] = None
    audio_file: Optional[BinaryIO] = None

    # Audio metadata
    audio_format: Optional[AudioFormat] = None
    sample_rate: Optional[int] = None
    channels: int = 1

    # Model settings
    model: Optional[str] = None
    language: Optional[str] = None  # BCP-47 language code

    # Transcription options
    punctuate: bool = True
    profanity_filter: bool = False
    word_timestamps: bool = False
    speaker_diarization: bool = False
    max_speakers: int = 2

    # Vocabulary hints
    vocabulary: Optional[list[str]] = None
    phrases: Optional[list[str]] = None

    # Streaming
    stream: bool = False
    interim_results: bool = False

    # Additional options
    extra_options: dict = field(default_factory=dict)


@dataclass
class TranscriptionWord:
    """A single word in transcription with timing."""
    word: str
    start_time: float  # seconds
    end_time: float    # seconds
    confidence: float  # 0-1
    speaker: Optional[int] = None  # Speaker ID for diarization


@dataclass
class TranscriptionSegment:
    """A segment of transcription (e.g., sentence or speaker turn)."""
    text: str
    start_time: float
    end_time: float
    confidence: float
    words: list[TranscriptionWord] = field(default_factory=list)
    speaker: Optional[int] = None
    language: Optional[str] = None


@dataclass
class STTResponse:
    """Response from speech-to-text transcription."""
    id: UUID = field(default_factory=uuid4)

    # Transcription
    text: str = ""
    segments: list[TranscriptionSegment] = field(default_factory=list)

    # Confidence
    confidence: float = 0.0

    # Detected metadata
    detected_language: Optional[str] = None
    audio_duration_seconds: float = 0.0

    # Model info
    model: str = ""
    provider: str = ""

    # Usage
    cost_usd: float = 0.0

    # Timing
    transcription_time_ms: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Errors
    error: Optional[str] = None


class TTSProvider(ABC):
    """Base class for Text-to-Speech providers."""

    provider_name: str = "base"

    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text.

        Args:
            request: TTS request with text and settings

        Returns:
            TTSResponse with audio data
        """
        pass

    async def synthesize_stream(
        self,
        request: TTSRequest
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech.

        Args:
            request: TTS request with text and settings

        Yields:
            Audio data chunks
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support streaming TTS")

    @abstractmethod
    def list_voices(
        self,
        language: Optional[str] = None
    ) -> list[Voice]:
        """List available voices.

        Args:
            language: Optional language filter (BCP-47 code)

        Returns:
            List of available voices
        """
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available TTS models."""
        pass

    def estimate_cost(self, request: TTSRequest) -> float:
        """Estimate synthesis cost in USD."""
        return 0.0


class STTProvider(ABC):
    """Base class for Speech-to-Text providers."""

    provider_name: str = "base"

    @abstractmethod
    async def transcribe(self, request: STTRequest) -> STTResponse:
        """Transcribe audio to text.

        Args:
            request: STT request with audio and settings

        Returns:
            STTResponse with transcription
        """
        pass

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        request: STTRequest,
    ) -> AsyncIterator[STTResponse]:
        """Stream transcription results.

        Args:
            audio_stream: Stream of audio data chunks
            request: STT request settings

        Yields:
            STTResponse with interim or final results
        """
        raise NotImplementedError(f"{self.provider_name} doesn't support streaming STT")

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available STT models."""
        pass

    @abstractmethod
    def list_languages(self) -> list[str]:
        """List supported languages."""
        pass

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost in USD."""
        return 0.0
