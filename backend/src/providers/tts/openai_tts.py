"""OpenAI Text-to-Speech provider."""

from __future__ import annotations

from typing import Any, AsyncIterator
import httpx

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.tts.base import BaseTTSProvider, SpeechResult, VoiceInfo


@ProviderRegistry.register
class OpenAITTSProvider(BaseTTSProvider):
    """OpenAI Text-to-Speech provider."""

    provider_name = "openai_tts"
    display_name = "OpenAI TTS"
    description = "OpenAI's text-to-speech with natural voices"
    requires_api_key = True

    API_URL = "https://api.openai.com/v1/audio/speech"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.model or "tts-1"

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "tts-1",
                "name": "TTS-1",
                "description": "Optimized for speed",
            },
            {
                "id": "tts-1-hd",
                "name": "TTS-1 HD",
                "description": "Optimized for quality",
            },
        ]

    @classmethod
    def get_available_voices(cls) -> list[VoiceInfo]:
        return [
            VoiceInfo(id="alloy", name="Alloy", language="en", gender="neutral"),
            VoiceInfo(id="echo", name="Echo", language="en", gender="male"),
            VoiceInfo(id="fable", name="Fable", language="en", gender="male"),
            VoiceInfo(id="onyx", name="Onyx", language="en", gender="male"),
            VoiceInfo(id="nova", name="Nova", language="en", gender="female"),
            VoiceInfo(id="shimmer", name="Shimmer", language="en", gender="female"),
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "speed": {
                    "type": "number",
                    "minimum": 0.25,
                    "maximum": 4.0,
                    "default": 1.0,
                    "description": "Speech speed",
                },
                "response_format": {
                    "type": "string",
                    "enum": ["mp3", "opus", "aac", "flac", "wav", "pcm"],
                    "default": "mp3",
                    "description": "Audio format",
                },
            },
        }

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> SpeechResult:
        """Synthesize speech using OpenAI TTS."""
        voice = voice or "alloy"
        response_format = kwargs.get("response_format", "mp3")

        payload = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
        }

        if "speed" in kwargs:
            payload["speed"] = kwargs["speed"]

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            audio_data = response.content

        return SpeechResult(
            audio=audio_data,
            format=response_format,
        )

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech."""
        voice = voice or "alloy"
        response_format = kwargs.get("response_format", "mp3")

        payload = {
            "model": self.model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
        }

        if "speed" in kwargs:
            payload["speed"] = kwargs["speed"]

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
