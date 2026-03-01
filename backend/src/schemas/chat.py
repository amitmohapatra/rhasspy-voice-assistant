"""Voice chat schemas (preserved from old chat module).

The text chat schemas (ChatRequest, ChatResponse, StreamEvent) have been
replaced by the Responses API schemas in src/schemas/response.py.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema
from src.schemas.enums import Emotion, Language


class VoiceChatRequest(BaseSchema):
    """Schema for voice chat request.

    Used for avatar-based voice interactions where audio is processed
    through STT, sent to the assistant, and returned as TTS.
    """

    audio_data: str = Field(
        ...,
        description="Base64-encoded audio data from user's voice input.",
    )
    audio_format: str = Field(
        default="webm",
        description="Format of the audio data.",
    )
    conversation_id: UUID | None = Field(
        default=None,
        description="Existing conversation ID to continue.",
    )
    assistant_id: UUID | None = Field(
        default=None,
        description="Assistant ID to use.",
    )
    language: Language = Field(
        default=Language.EN_US,
        description="Language for STT and TTS.",
    )
    return_audio: bool = Field(
        default=True,
        description="Whether to return TTS audio response.",
    )


class VoiceChatResponse(BaseSchema):
    """Schema for voice chat response.

    Contains both the text response and audio data for playback.
    """

    conversation_id: UUID = Field(
        ...,
        description="ID of the conversation.",
    )
    transcription: str = Field(
        ...,
        description="Transcribed text from the user's audio input.",
    )
    response_text: str = Field(
        ...,
        description="The assistant's text response.",
    )
    audio_data: str | None = Field(
        default=None,
        description="Base64-encoded TTS audio of the response.",
    )
    audio_format: str = Field(
        default="mp3",
        description="Format of the response audio.",
    )
    emotion: Emotion = Field(
        default=Emotion.NEUTRAL,
        description="Emotion for avatar animation.",
    )
    duration_seconds: float | None = Field(
        default=None,
        description="Duration of the audio response in seconds.",
    )
