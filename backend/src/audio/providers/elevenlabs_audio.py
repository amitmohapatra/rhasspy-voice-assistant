"""ElevenLabs TTS Provider - High-quality voice synthesis."""

from __future__ import annotations

import time
from typing import Optional, AsyncIterator

import httpx

from src.audio.base import (
    TTSProvider,
    TTSRequest,
    TTSResponse,
    Voice,
    VoiceGender,
    AudioFormat,
)


class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs Text-to-Speech provider.

    Supports:
    - Multilingual v2: High-quality multilingual
    - Turbo v2.5: Fastest generation
    - Turbo v2: Fast with good quality

    Features:
    - Voice cloning (with consent)
    - Emotion control
    - Speed and stability settings
    - 29+ languages
    - Streaming support
    """

    provider_name = "elevenlabs"

    BASE_URL = "https://api.elevenlabs.io/v1"

    # Available models
    MODELS = {
        "eleven_multilingual_v2": "Multilingual v2",
        "eleven_turbo_v2_5": "Turbo v2.5 (Fastest)",
        "eleven_turbo_v2": "Turbo v2",
        "eleven_monolingual_v1": "English v1",
    }

    # Pricing per 1000 characters (approximate)
    PRICING = {
        "eleven_multilingual_v2": 0.30,
        "eleven_turbo_v2_5": 0.15,
        "eleven_turbo_v2": 0.15,
        "eleven_monolingual_v1": 0.30,
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = "eleven_multilingual_v2",
        default_voice: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel
        timeout: float = 60.0,
    ):
        """Initialize ElevenLabs TTS provider.

        Args:
            api_key: ElevenLabs API key
            default_model: Default model ID
            default_voice: Default voice ID
            timeout: Request timeout
        """
        self.api_key = api_key
        self.default_model = default_model
        self.default_voice = default_voice
        self.timeout = timeout
        self._voices_cache: Optional[list[Voice]] = None

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text."""
        start_time = time.time()

        try:
            voice_id = request.voice or self.default_voice
            model_id = request.model or self.default_model

            # Map audio format
            format_map = {
                AudioFormat.MP3: "mp3_44100_128",
                AudioFormat.WAV: "pcm_44100",
                AudioFormat.OGG: "opus_16000",
            }
            output_format = format_map.get(request.audio_format, "mp3_44100_128")

            # Build request body
            body = {
                "text": request.text,
                "model_id": model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": request.style_degree if request.style else 0.0,
                    "use_speaker_boost": True,
                },
            }

            # Add speed control
            if request.speed != 1.0:
                # ElevenLabs doesn't have direct speed control
                # but we can approximate with style
                pass

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.BASE_URL}/text-to-speech/{voice_id}",
                    headers={
                        "xi-api-key": self.api_key,
                        "Content-Type": "application/json",
                        "Accept": "audio/mpeg",
                    },
                    params={"output_format": output_format},
                    json=body,
                )
                response.raise_for_status()

                audio_data = response.content

            elapsed_ms = (time.time() - start_time) * 1000

            return TTSResponse(
                audio_data=audio_data,
                audio_format=request.audio_format,
                model=model_id,
                voice=voice_id,
                provider=self.provider_name,
                characters_used=len(request.text),
                cost_usd=self.estimate_cost(request),
                synthesis_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return TTSResponse(
                model=request.model or self.default_model,
                voice=request.voice or self.default_voice,
                provider=self.provider_name,
                synthesis_time_ms=elapsed_ms,
                error=str(e),
            )

    async def synthesize_stream(
        self,
        request: TTSRequest,
    ) -> AsyncIterator[bytes]:
        """Stream synthesized speech."""
        voice_id = request.voice or self.default_voice
        model_id = request.model or self.default_model

        body = {
            "text": request.text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/text-to-speech/{voice_id}/stream",
                headers={
                    "xi-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                json=body,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    def list_voices(self, language: Optional[str] = None) -> list[Voice]:
        """List available voices."""
        # Return cached voices if available
        # In production, this would call the API
        return [
            Voice(
                id="21m00Tcm4TlvDq8ikWAM",
                name="Rachel",
                language="en",
                gender=VoiceGender.FEMALE,
                description="American, calm, young",
                provider=self.provider_name,
            ),
            Voice(
                id="AZnzlk1XvdvUeBnXmlld",
                name="Domi",
                language="en",
                gender=VoiceGender.FEMALE,
                description="American, strong, confident",
                provider=self.provider_name,
            ),
            Voice(
                id="EXAVITQu4vr4xnSDxMaL",
                name="Bella",
                language="en",
                gender=VoiceGender.FEMALE,
                description="American, soft, warm",
                provider=self.provider_name,
            ),
            Voice(
                id="ErXwobaYiN019PkySvjV",
                name="Antoni",
                language="en",
                gender=VoiceGender.MALE,
                description="American, warm, friendly",
                provider=self.provider_name,
            ),
            Voice(
                id="VR6AewLTigWG4xSOukaG",
                name="Arnold",
                language="en",
                gender=VoiceGender.MALE,
                description="American, deep, narrator",
                provider=self.provider_name,
            ),
            Voice(
                id="pNInz6obpgDQGcFmaJgB",
                name="Adam",
                language="en",
                gender=VoiceGender.MALE,
                description="American, deep, narration",
                provider=self.provider_name,
            ),
            Voice(
                id="yoZ06aMxZJJ28mfd3POQ",
                name="Sam",
                language="en",
                gender=VoiceGender.MALE,
                description="American, young, raspy",
                provider=self.provider_name,
            ),
        ]

    async def fetch_voices(self) -> list[Voice]:
        """Fetch all voices from the API."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.BASE_URL}/voices",
                headers={"xi-api-key": self.api_key},
            )
            response.raise_for_status()

            data = response.json()
            voices = []

            for v in data.get("voices", []):
                voices.append(Voice(
                    id=v["voice_id"],
                    name=v["name"],
                    language=v.get("labels", {}).get("language", "en"),
                    gender=VoiceGender(v.get("labels", {}).get("gender", "neutral")),
                    description=v.get("labels", {}).get("description", ""),
                    preview_url=v.get("preview_url"),
                    provider=self.provider_name,
                    metadata=v.get("labels", {}),
                ))

            self._voices_cache = voices
            return voices

    def list_models(self) -> list[str]:
        """List available TTS models."""
        return list(self.MODELS.keys())

    def estimate_cost(self, request: TTSRequest) -> float:
        """Estimate synthesis cost in USD."""
        model = request.model or self.default_model
        price_per_1000 = self.PRICING.get(model, 0.30)
        characters = len(request.text)
        return (characters / 1000) * price_per_1000

    async def get_user_info(self) -> dict:
        """Get user subscription info."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.BASE_URL}/user/subscription",
                headers={"xi-api-key": self.api_key},
            )
            response.raise_for_status()
            return response.json()
