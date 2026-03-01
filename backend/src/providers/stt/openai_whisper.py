"""OpenAI Whisper STT provider."""

from __future__ import annotations

from typing import Any, BinaryIO
import httpx

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.stt.base import BaseSTTProvider, TranscriptionResult


@ProviderRegistry.register
class OpenAIWhisperProvider(BaseSTTProvider):
    """OpenAI Whisper Speech-to-Text provider."""

    provider_name = "openai_whisper"
    display_name = "OpenAI Whisper"
    description = "OpenAI's Whisper model for accurate speech recognition"
    requires_api_key = True

    WHISPER_API_URL = "https://api.openai.com/v1/audio/transcriptions"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.model or "whisper-1"

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "whisper-1",
                "name": "Whisper V2",
                "description": "Large-v2 model, most accurate",
                "languages": 99,
            },
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "response_format": {
                    "type": "string",
                    "enum": ["json", "text", "srt", "verbose_json", "vtt"],
                    "default": "verbose_json",
                    "description": "Output format",
                },
                "temperature": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0,
                    "description": "Sampling temperature",
                },
                "prompt": {
                    "type": "string",
                    "description": "Optional prompt to guide the model",
                },
            },
        }

    async def transcribe(
        self,
        audio: bytes | BinaryIO,
        language: str | None = None,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio using OpenAI Whisper."""
        # Prepare audio data
        if isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()

        # Prepare form data
        files = {
            "file": ("audio.webm", audio_data, "audio/webm"),
        }
        data = {
            "model": self.model,
            "response_format": kwargs.get("response_format", "verbose_json"),
        }

        if language:
            data["language"] = language

        if kwargs.get("prompt"):
            data["prompt"] = kwargs["prompt"]

        if "temperature" in kwargs:
            data["temperature"] = str(kwargs["temperature"])

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.WHISPER_API_URL,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                files=files,
                data=data,
                timeout=120.0,
            )
            response.raise_for_status()
            result = response.json()

        # Parse response
        if data["response_format"] == "verbose_json":
            return TranscriptionResult(
                text=result.get("text", ""),
                language=result.get("language"),
                duration_seconds=result.get("duration"),
                words=result.get("words"),
            )
        else:
            return TranscriptionResult(
                text=result.get("text", str(result)),
                language=language,
            )

    @classmethod
    def get_supported_formats(cls) -> list[str]:
        return ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"]
