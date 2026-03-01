"""ElevenLabs Text-to-Speech provider."""

from __future__ import annotations

from typing import Any, AsyncIterator
import httpx

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.tts.base import BaseTTSProvider, SpeechResult, VoiceInfo


@ProviderRegistry.register
class ElevenLabsProvider(BaseTTSProvider):
    """ElevenLabs Text-to-Speech provider."""

    provider_name = "elevenlabs"
    display_name = "ElevenLabs"
    description = "High-quality AI voices with emotion and style control"
    requires_api_key = True

    API_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.model or "eleven_multilingual_v2"

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "eleven_multilingual_v2",
                "name": "Multilingual V2",
                "description": "Best quality, 29 languages",
            },
            {
                "id": "eleven_turbo_v2",
                "name": "Turbo V2",
                "description": "Low latency, English only",
            },
            {
                "id": "eleven_monolingual_v1",
                "name": "Monolingual V1",
                "description": "English only, legacy",
            },
        ]

    @classmethod
    def get_available_voices(cls) -> list[VoiceInfo]:
        # Default voices - actual list fetched from API
        return [
            VoiceInfo(
                id="21m00Tcm4TlvDq8ikWAM",
                name="Rachel",
                language="en",
                gender="female",
                description="Calm and professional",
            ),
            VoiceInfo(
                id="AZnzlk1XvdvUeBnXmlld",
                name="Domi",
                language="en",
                gender="female",
                description="Strong and confident",
            ),
            VoiceInfo(
                id="EXAVITQu4vr4xnSDxMaL",
                name="Bella",
                language="en",
                gender="female",
                description="Soft and gentle",
            ),
            VoiceInfo(
                id="ErXwobaYiN019PkySvjV",
                name="Antoni",
                language="en",
                gender="male",
                description="Well-rounded and expressive",
            ),
            VoiceInfo(
                id="MF3mGyEYCl7XYWbV9V6O",
                name="Elli",
                language="en",
                gender="female",
                description="Emotional range",
            ),
            VoiceInfo(
                id="TxGEqnHWrfWFTfGW9XjX",
                name="Josh",
                language="en",
                gender="male",
                description="Deep and authoritative",
            ),
            VoiceInfo(
                id="VR6AewLTigWG4xSOukaG",
                name="Arnold",
                language="en",
                gender="male",
                description="Crisp and articulate",
            ),
            VoiceInfo(
                id="pNInz6obpgDQGcFmaJgB",
                name="Adam",
                language="en",
                gender="male",
                description="Deep and narrative",
            ),
            VoiceInfo(
                id="yoZ06aMxZJJ28mfd3POQ",
                name="Sam",
                language="en",
                gender="male",
                description="Raspy and dynamic",
            ),
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "stability": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.5,
                    "description": "Voice stability",
                },
                "similarity_boost": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0.75,
                    "description": "Voice similarity",
                },
                "style": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                    "default": 0,
                    "description": "Style exaggeration",
                },
                "use_speaker_boost": {
                    "type": "boolean",
                    "default": True,
                    "description": "Enhance speaker similarity",
                },
            },
        }

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> SpeechResult:
        """Synthesize speech using ElevenLabs."""
        voice = voice or "21m00Tcm4TlvDq8ikWAM"  # Rachel

        url = f"{self.API_URL}/text-to-speech/{voice}"

        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": kwargs.get("stability", 0.5),
                "similarity_boost": kwargs.get("similarity_boost", 0.75),
                "style": kwargs.get("style", 0),
                "use_speaker_boost": kwargs.get("use_speaker_boost", True),
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={
                    "xi-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            audio_data = response.content

        return SpeechResult(
            audio=audio_data,
            format="mp3",
        )

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech."""
        voice = voice or "21m00Tcm4TlvDq8ikWAM"

        url = f"{self.API_URL}/text-to-speech/{voice}/stream"

        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": kwargs.get("stability", 0.5),
                "similarity_boost": kwargs.get("similarity_boost", 0.75),
            },
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers={
                    "xi-api-key": self.config.api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    async def get_voices_from_api(self) -> list[VoiceInfo]:
        """Fetch available voices from ElevenLabs API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_URL}/voices",
                headers={"xi-api-key": self.config.api_key},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        return [
            VoiceInfo(
                id=v["voice_id"],
                name=v["name"],
                language=v.get("labels", {}).get("language", "en"),
                gender=v.get("labels", {}).get("gender"),
                preview_url=v.get("preview_url"),
                description=v.get("labels", {}).get("description"),
            )
            for v in data.get("voices", [])
        ]
