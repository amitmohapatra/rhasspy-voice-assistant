"""Deepgram STT provider."""

from __future__ import annotations

from typing import Any, AsyncIterator, BinaryIO
import httpx

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.stt.base import BaseSTTProvider, TranscriptionResult, TranscriptionSegment


@ProviderRegistry.register
class DeepgramProvider(BaseSTTProvider):
    """Deepgram Speech-to-Text provider."""

    provider_name = "deepgram"
    display_name = "Deepgram"
    description = "Fast and accurate speech recognition with real-time streaming"
    requires_api_key = True

    API_URL = "https://api.deepgram.com/v1/listen"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.model or "nova-2"

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "nova-2",
                "name": "Nova-2",
                "description": "Latest and most accurate model",
                "streaming": True,
            },
            {
                "id": "nova",
                "name": "Nova",
                "description": "Fast and accurate",
                "streaming": True,
            },
            {
                "id": "enhanced",
                "name": "Enhanced",
                "description": "High accuracy for specific use cases",
                "streaming": True,
            },
            {
                "id": "base",
                "name": "Base",
                "description": "Cost-effective option",
                "streaming": True,
            },
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "punctuate": {
                    "type": "boolean",
                    "default": True,
                    "description": "Add punctuation",
                },
                "diarize": {
                    "type": "boolean",
                    "default": False,
                    "description": "Speaker diarization",
                },
                "smart_format": {
                    "type": "boolean",
                    "default": True,
                    "description": "Smart formatting",
                },
                "utterances": {
                    "type": "boolean",
                    "default": False,
                    "description": "Split by utterances",
                },
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keywords to boost",
                },
            },
        }

    async def transcribe(
        self,
        audio: bytes | BinaryIO,
        language: str | None = None,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio using Deepgram."""
        if isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()

        # Build query parameters
        params = {
            "model": self.model,
            "punctuate": str(kwargs.get("punctuate", True)).lower(),
            "smart_format": str(kwargs.get("smart_format", True)).lower(),
        }

        if language:
            params["language"] = language

        if kwargs.get("diarize"):
            params["diarize"] = "true"

        if kwargs.get("utterances"):
            params["utterances"] = "true"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.API_URL,
                params=params,
                headers={
                    "Authorization": f"Token {self.config.api_key}",
                    "Content-Type": "audio/webm",
                },
                content=audio_data,
                timeout=120.0,
            )
            response.raise_for_status()
            result = response.json()

        # Parse response
        channel = result.get("results", {}).get("channels", [{}])[0]
        alternative = channel.get("alternatives", [{}])[0]

        words = None
        if "words" in alternative:
            words = [
                {
                    "word": w.get("word"),
                    "start": w.get("start"),
                    "end": w.get("end"),
                    "confidence": w.get("confidence"),
                }
                for w in alternative["words"]
            ]

        return TranscriptionResult(
            text=alternative.get("transcript", ""),
            language=channel.get("detected_language") or language,
            confidence=alternative.get("confidence"),
            words=words,
            duration_seconds=result.get("metadata", {}).get("duration"),
        )

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str | None = None,
        **kwargs,
    ) -> AsyncIterator[TranscriptionSegment]:
        """Stream transcription using Deepgram WebSocket."""
        import websockets
        import json

        # Build WebSocket URL
        ws_url = "wss://api.deepgram.com/v1/listen"
        params = [
            f"model={self.model}",
            "punctuate=true",
            "interim_results=true",
        ]
        if language:
            params.append(f"language={language}")

        ws_url = f"{ws_url}?{'&'.join(params)}"

        async with websockets.connect(
            ws_url,
            extra_headers={"Authorization": f"Token {self.config.api_key}"},
        ) as ws:
            # Start receiving task
            async def receive():
                async for message in ws:
                    data = json.loads(message)
                    if data.get("type") == "Results":
                        channel = data.get("channel", {})
                        alt = channel.get("alternatives", [{}])[0]
                        yield TranscriptionSegment(
                            text=alt.get("transcript", ""),
                            is_final=data.get("is_final", False),
                            confidence=alt.get("confidence"),
                            start_time=data.get("start"),
                            end_time=data.get("start", 0) + data.get("duration", 0),
                        )

            # Send audio chunks
            import asyncio

            async def send():
                async for chunk in audio_stream:
                    await ws.send(chunk)
                await ws.send(json.dumps({"type": "CloseStream"}))

            # Run both concurrently
            send_task = asyncio.create_task(send())

            async for segment in receive():
                yield segment

            await send_task
