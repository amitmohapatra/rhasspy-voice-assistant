"""Voice API schemas with comprehensive Swagger documentation."""

from __future__ import annotations

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.enums import AudioFormat, STTProvider, TTSProvider, Language, OpenAIVoice


class TranscribeRequest(BaseSchema):
    """Schema for audio transcription (Speech-to-Text) request.

    Accepts base64-encoded audio in various formats and returns transcribed text.
    """

    audio: str = Field(
        ...,
        description="Base64-encoded audio data to transcribe.",
        json_schema_extra={"example": "UklGRiQA...base64_encoded_audio_data..."}
    )
    format: AudioFormat = Field(
        default=AudioFormat.WEBM,
        description="Format of the input audio.",
        json_schema_extra={"example": "webm"}
    )
    language: Language | None = Field(
        default=None,
        description="Language hint for better transcription accuracy.",
        json_schema_extra={"example": "en-US"}
    )
    provider: STTProvider | None = Field(
        default=None,
        description="STT provider to use. Defaults to the app's configured provider.",
        json_schema_extra={"example": "openai"}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "audio": "UklGRiQA...base64_encoded_audio_data...",
                "format": "webm",
                "language": "en-US",
                "provider": None
            }
        }
    }


class TranscribeResponse(BaseSchema):
    """Schema for transcription response."""

    text: str = Field(
        ...,
        description="Transcribed text from the audio.",
        json_schema_extra={"example": "Hello, how can I help you today?"}
    )
    language: Language | None = Field(
        default=None,
        description="Detected or specified language.",
        json_schema_extra={"example": "en-US"}
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Transcription confidence score (0-1).",
        json_schema_extra={"example": 0.95}
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Duration of the audio in seconds.",
        json_schema_extra={"example": 3.5}
    )
    words: list[dict] | None = Field(
        default=None,
        description="Word-level timestamps (if supported by provider).",
        json_schema_extra={
            "example": [
                {"word": "Hello", "start": 0.0, "end": 0.5},
                {"word": "how", "start": 0.6, "end": 0.8}
            ]
        }
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Hello, how can I help you today?",
                "language": "en-US",
                "confidence": 0.95,
                "duration_seconds": 3.5,
                "words": None
            }
        }
    }


class SynthesizeRequest(BaseSchema):
    """Schema for text-to-speech synthesis request.

    Converts text to audio using the specified voice and provider.
    """

    text: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Text to convert to speech (max 5000 characters).",
        json_schema_extra={"example": "Hello! How can I assist you today?"}
    )
    voice_id: str | None = Field(
        default=None,
        description="Voice ID to use. Available voices depend on the provider.",
        json_schema_extra={"example": "alloy"}
    )
    provider: TTSProvider | None = Field(
        default=None,
        description="TTS provider to use. Defaults to the app's configured provider.",
        json_schema_extra={"example": "openai"}
    )
    language: Language = Field(
        default=Language.EN_US,
        description="Language for synthesis.",
        json_schema_extra={"example": "en-US"}
    )
    speaking_rate: float = Field(
        default=1.0,
        ge=0.25,
        le=4.0,
        description="Speaking rate multiplier. 1.0 is normal speed.",
        json_schema_extra={"example": 1.0}
    )
    pitch: float = Field(
        default=0.0,
        ge=-20.0,
        le=20.0,
        description="Pitch adjustment in semitones.",
        json_schema_extra={"example": 0.0}
    )
    output_format: AudioFormat = Field(
        default=AudioFormat.MP3,
        description="Desired output audio format.",
        json_schema_extra={"example": "mp3"}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "Hello! How can I assist you today?",
                "voice_id": "alloy",
                "provider": "openai",
                "language": "en-US",
                "speaking_rate": 1.0,
                "pitch": 0.0,
                "output_format": "mp3"
            }
        }
    }


class SynthesizeResponse(BaseSchema):
    """Schema for synthesis response."""

    audio: str = Field(
        ...,
        description="Base64-encoded synthesized audio.",
        json_schema_extra={"example": "//uQx...base64_encoded_mp3_data..."}
    )
    format: AudioFormat = Field(
        ...,
        description="Format of the output audio.",
        json_schema_extra={"example": "mp3"}
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Duration of the audio in seconds.",
        json_schema_extra={"example": 2.5}
    )
    sample_rate: int | None = Field(
        default=None,
        description="Audio sample rate in Hz.",
        json_schema_extra={"example": 24000}
    )
    byte_size: int | None = Field(
        default=None,
        description="Size of the audio data in bytes.",
        json_schema_extra={"example": 48000}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "audio": "//uQx...base64_encoded_mp3_data...",
                "format": "mp3",
                "duration_seconds": 2.5,
                "sample_rate": 24000,
                "byte_size": 48000
            }
        }
    }


class VoiceInfo(BaseSchema):
    """Schema for voice information."""

    id: str = Field(
        ...,
        description="Unique voice identifier.",
        json_schema_extra={"example": "alloy"}
    )
    name: str = Field(
        ...,
        description="Display name of the voice.",
        json_schema_extra={"example": "Alloy"}
    )
    provider: TTSProvider = Field(
        ...,
        description="Provider offering this voice.",
        json_schema_extra={"example": "openai"}
    )
    language: Language = Field(
        ...,
        description="Primary language of the voice.",
        json_schema_extra={"example": "en-US"}
    )
    gender: str | None = Field(
        default=None,
        description="Voice gender (male/female/neutral).",
        json_schema_extra={"example": "neutral"}
    )
    preview_url: str | None = Field(
        default=None,
        description="URL to preview the voice.",
        json_schema_extra={"example": None}
    )
    description: str | None = Field(
        default=None,
        description="Description of the voice characteristics.",
        json_schema_extra={"example": "A versatile, natural-sounding voice"}
    )


class VoiceListResponse(BaseSchema):
    """Schema for list of available voices."""

    voices: list[VoiceInfo] = Field(
        default_factory=list,
        description="List of available voices."
    )
    provider: TTSProvider | None = Field(
        default=None,
        description="Provider filter applied (if any).",
        json_schema_extra={"example": None}
    )


class RealtimeSessionRequest(BaseSchema):
    """Schema for initiating a real-time voice session via WebSocket."""

    assistant_id: str = Field(
        ...,
        description="ID of the assistant to use for the session.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    conversation_id: str | None = Field(
        default=None,
        description="Existing conversation ID to continue.",
        json_schema_extra={"example": None}
    )
    language: Language = Field(
        default=Language.EN_US,
        description="Language for STT and TTS.",
        json_schema_extra={"example": "en-US"}
    )
    voice_id: str | None = Field(
        default=None,
        description="Voice ID for TTS responses.",
        json_schema_extra={"example": "alloy"}
    )
    enable_vad: bool = Field(
        default=True,
        description="Enable Voice Activity Detection for automatic speech detection."
    )
    vad_threshold: float = Field(
        default=0.5,
        ge=0,
        le=1,
        description="VAD sensitivity threshold.",
        json_schema_extra={"example": 0.5}
    )


class RealtimeEvent(BaseSchema):
    """Schema for real-time WebSocket events."""

    event: str = Field(
        ...,
        description="Event type: audio_chunk, transcript, response_start, response_delta, response_done, error",
        json_schema_extra={"example": "transcript"}
    )
    data: dict = Field(
        default_factory=dict,
        description="Event-specific data payload.",
        json_schema_extra={"example": {"text": "Hello", "is_final": True}}
    )
    timestamp: str | None = Field(
        default=None,
        description="Event timestamp in ISO format.",
        json_schema_extra={"example": "2024-01-15T10:30:00.123Z"}
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event": "transcript",
                    "data": {"text": "Hello, how are you?", "is_final": True},
                    "timestamp": "2024-01-15T10:30:00.123Z"
                },
                {
                    "event": "response_delta",
                    "data": {"content": "I'm doing great, thanks!"},
                    "timestamp": "2024-01-15T10:30:01.456Z"
                },
                {
                    "event": "audio_chunk",
                    "data": {"audio": "//uQx...", "format": "mp3"},
                    "timestamp": "2024-01-15T10:30:02.789Z"
                }
            ]
        }
    }
