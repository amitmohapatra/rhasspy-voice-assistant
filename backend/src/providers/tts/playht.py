"""PlayHT Text-to-Speech provider."""

from __future__ import annotations

from typing import Any, AsyncIterator
import httpx

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.tts.base import BaseTTSProvider, SpeechResult, VoiceInfo


@ProviderRegistry.register
class PlayHTProvider(BaseTTSProvider):
    """PlayHT Text-to-Speech provider."""

    provider_name = "playht"
    display_name = "PlayHT"
    description = "Ultra-realistic AI voices with emotion control"
    requires_api_key = True

    API_URL = "https://api.play.ht/api/v2"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.user_id = config.settings.get("user_id", "")

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "PlayHT2.0",
                "name": "PlayHT 2.0",
                "description": "Latest and most realistic",
            },
            {
                "id": "PlayHT2.0-turbo",
                "name": "PlayHT 2.0 Turbo",
                "description": "Faster, slightly lower quality",
            },
            {
                "id": "PlayHT1.0",
                "name": "PlayHT 1.0",
                "description": "Legacy model",
            },
        ]

    @classmethod
    def get_available_voices(cls) -> list[VoiceInfo]:
        return [
            VoiceInfo(
                id="s3://voice-cloning-zero-shot/775ae416-49bb-4fb6-bd45-740f205d25cf/jennifersarah/manifest.json",
                name="Jennifer",
                language="en",
                gender="female",
            ),
            VoiceInfo(
                id="s3://voice-cloning-zero-shot/d9ff78ba-d016-47f6-b0ef-dd630f59414e/original/manifest.json",
                name="Matt",
                language="en",
                gender="male",
            ),
            VoiceInfo(
                id="s3://voice-cloning-zero-shot/820da3d2-3a3b-42e7-844d-e68db835a206/original/manifest.json",
                name="Davis",
                language="en",
                gender="male",
            ),
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "string",
                    "description": "PlayHT User ID",
                },
                "quality": {
                    "type": "string",
                    "enum": ["draft", "low", "medium", "high", "premium"],
                    "default": "high",
                    "description": "Audio quality",
                },
                "speed": {
                    "type": "number",
                    "minimum": 0.5,
                    "maximum": 2.0,
                    "default": 1.0,
                    "description": "Speaking speed",
                },
                "temperature": {
                    "type": "number",
                    "minimum": 0.1,
                    "maximum": 2.0,
                    "default": 1.0,
                    "description": "Voice variability",
                },
                "emotion": {
                    "type": "string",
                    "enum": [
                        "female_happy", "female_sad", "female_angry",
                        "female_fearful", "female_disgust", "female_surprised",
                        "male_happy", "male_sad", "male_angry",
                        "male_fearful", "male_disgust", "male_surprised",
                    ],
                    "description": "Emotion preset",
                },
            },
            "required": ["user_id"],
        }

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> SpeechResult:
        """Synthesize speech using PlayHT."""
        voice = voice or self.get_available_voices()[0].id

        payload = {
            "text": text,
            "voice": voice,
            "quality": kwargs.get("quality", "high"),
            "output_format": "mp3",
            "speed": kwargs.get("speed", 1.0),
            "temperature": kwargs.get("temperature", 1.0),
        }

        if kwargs.get("emotion"):
            payload["emotion"] = kwargs["emotion"]

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "X-User-ID": self.user_id,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            # Create TTS request
            response = await client.post(
                f"{self.API_URL}/tts",
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

            # Get audio URL
            audio_url = result.get("url") or result.get("audioUrl")

            if not audio_url:
                raise Exception("No audio URL in response")

            # Download audio
            audio_response = await client.get(audio_url, timeout=60.0)
            audio_response.raise_for_status()

        return SpeechResult(
            audio=audio_response.content,
            format="mp3",
        )

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech."""
        voice = voice or self.get_available_voices()[0].id

        payload = {
            "text": text,
            "voice": voice,
            "quality": kwargs.get("quality", "draft"),  # Use draft for streaming
            "output_format": "mp3",
            "speed": kwargs.get("speed", 1.0),
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "X-User-ID": self.user_id,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.API_URL}/tts/stream",
                headers=headers,
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk
