"""AssemblyAI STT provider."""

from __future__ import annotations

from typing import Any, BinaryIO
import httpx
import asyncio

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.stt.base import BaseSTTProvider, TranscriptionResult


@ProviderRegistry.register
class AssemblyAIProvider(BaseSTTProvider):
    """AssemblyAI Speech-to-Text provider."""

    provider_name = "assemblyai"
    display_name = "AssemblyAI"
    description = "AI-powered speech recognition with advanced features"
    requires_api_key = True

    UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
    TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.model or "best"

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "best",
                "name": "Best",
                "description": "Highest accuracy model",
            },
            {
                "id": "nano",
                "name": "Nano",
                "description": "Faster, lower cost",
            },
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "speaker_labels": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable speaker diarization",
                },
                "auto_chapters": {
                    "type": "boolean",
                    "default": False,
                    "description": "Auto-generate chapters",
                },
                "entity_detection": {
                    "type": "boolean",
                    "default": False,
                    "description": "Detect entities",
                },
                "sentiment_analysis": {
                    "type": "boolean",
                    "default": False,
                    "description": "Analyze sentiment",
                },
                "auto_highlights": {
                    "type": "boolean",
                    "default": False,
                    "description": "Extract key phrases",
                },
                "content_safety": {
                    "type": "boolean",
                    "default": False,
                    "description": "Detect sensitive content",
                },
            },
        }

    async def transcribe(
        self,
        audio: bytes | BinaryIO,
        language: str | None = None,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio using AssemblyAI."""
        if isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()

        headers = {"Authorization": self.config.api_key}

        async with httpx.AsyncClient() as client:
            # Upload audio
            upload_response = await client.post(
                self.UPLOAD_URL,
                headers=headers,
                content=audio_data,
                timeout=120.0,
            )
            upload_response.raise_for_status()
            audio_url = upload_response.json()["upload_url"]

            # Create transcription request
            transcript_request = {
                "audio_url": audio_url,
                "speech_model": self.model,
            }

            if language:
                transcript_request["language_code"] = language

            # Add optional features
            if kwargs.get("speaker_labels"):
                transcript_request["speaker_labels"] = True
            if kwargs.get("auto_chapters"):
                transcript_request["auto_chapters"] = True
            if kwargs.get("entity_detection"):
                transcript_request["entity_detection"] = True
            if kwargs.get("sentiment_analysis"):
                transcript_request["sentiment_analysis"] = True
            if kwargs.get("auto_highlights"):
                transcript_request["auto_highlights"] = True
            if kwargs.get("content_safety"):
                transcript_request["content_safety"] = True

            # Submit transcription
            transcript_response = await client.post(
                self.TRANSCRIPT_URL,
                headers=headers,
                json=transcript_request,
                timeout=30.0,
            )
            transcript_response.raise_for_status()
            transcript_id = transcript_response.json()["id"]

            # Poll for completion
            while True:
                status_response = await client.get(
                    f"{self.TRANSCRIPT_URL}/{transcript_id}",
                    headers=headers,
                    timeout=30.0,
                )
                status_response.raise_for_status()
                result = status_response.json()

                if result["status"] == "completed":
                    break
                elif result["status"] == "error":
                    raise Exception(f"Transcription failed: {result.get('error')}")

                await asyncio.sleep(1)

        # Parse response
        words = None
        if result.get("words"):
            words = [
                {
                    "word": w.get("text"),
                    "start": w.get("start") / 1000,  # Convert to seconds
                    "end": w.get("end") / 1000,
                    "confidence": w.get("confidence"),
                }
                for w in result["words"]
            ]

        return TranscriptionResult(
            text=result.get("text", ""),
            language=result.get("language_code") or language,
            confidence=result.get("confidence"),
            words=words,
            duration_seconds=result.get("audio_duration"),
        )
