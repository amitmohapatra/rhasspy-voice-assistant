"""Google Cloud Speech-to-Text provider."""

from __future__ import annotations

from typing import Any, BinaryIO

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.stt.base import BaseSTTProvider, TranscriptionResult


@ProviderRegistry.register
class GoogleSTTProvider(BaseSTTProvider):
    """Google Cloud Speech-to-Text provider."""

    provider_name = "google_stt"
    display_name = "Google Cloud STT"
    description = "Google Cloud Speech-to-Text with wide language support"
    requires_api_key = True

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.model = config.model or "latest_long"

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "latest_long",
                "name": "Latest Long",
                "description": "Best for long-form audio",
            },
            {
                "id": "latest_short",
                "name": "Latest Short",
                "description": "Best for short audio clips",
            },
            {
                "id": "phone_call",
                "name": "Phone Call",
                "description": "Optimized for phone audio",
            },
            {
                "id": "video",
                "name": "Video",
                "description": "Optimized for video content",
            },
            {
                "id": "chirp",
                "name": "Chirp",
                "description": "Universal Speech Model (USM)",
            },
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "enable_word_time_offsets": {
                    "type": "boolean",
                    "default": True,
                    "description": "Include word timestamps",
                },
                "enable_automatic_punctuation": {
                    "type": "boolean",
                    "default": True,
                    "description": "Add punctuation",
                },
                "enable_speaker_diarization": {
                    "type": "boolean",
                    "default": False,
                    "description": "Speaker diarization",
                },
                "diarization_speaker_count": {
                    "type": "integer",
                    "minimum": 2,
                    "maximum": 10,
                    "description": "Number of speakers",
                },
                "profanity_filter": {
                    "type": "boolean",
                    "default": False,
                    "description": "Filter profanity",
                },
            },
        }

    async def transcribe(
        self,
        audio: bytes | BinaryIO,
        language: str | None = None,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio using Google Cloud STT."""
        try:
            from google.cloud import speech_v1 as speech
        except ImportError:
            raise ImportError(
                "google-cloud-speech is required for Google STT. "
                "Install with: pip install google-cloud-speech"
            )

        if isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()

        # Create client (uses GOOGLE_APPLICATION_CREDENTIALS or API key)
        client = speech.SpeechAsyncClient()

        # Configure recognition
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
            sample_rate_hertz=48000,
            language_code=language or "en-US",
            model=self.model,
            enable_word_time_offsets=kwargs.get("enable_word_time_offsets", True),
            enable_automatic_punctuation=kwargs.get("enable_automatic_punctuation", True),
            profanity_filter=kwargs.get("profanity_filter", False),
        )

        if kwargs.get("enable_speaker_diarization"):
            config.diarization_config = speech.SpeakerDiarizationConfig(
                enable_speaker_diarization=True,
                min_speaker_count=2,
                max_speaker_count=kwargs.get("diarization_speaker_count", 6),
            )

        audio_obj = speech.RecognitionAudio(content=audio_data)

        # Perform recognition
        response = await client.recognize(config=config, audio=audio_obj)

        # Parse response
        text_parts = []
        words = []

        for result in response.results:
            alternative = result.alternatives[0]
            text_parts.append(alternative.transcript)

            if alternative.words:
                for word_info in alternative.words:
                    words.append({
                        "word": word_info.word,
                        "start": word_info.start_time.total_seconds(),
                        "end": word_info.end_time.total_seconds(),
                        "confidence": alternative.confidence,
                    })

        return TranscriptionResult(
            text=" ".join(text_parts),
            language=language,
            confidence=response.results[0].alternatives[0].confidence if response.results else None,
            words=words if words else None,
        )

    @classmethod
    def get_supported_languages(cls) -> list[dict[str, str]]:
        """Google supports 125+ languages."""
        return [
            {"code": "en-US", "name": "English (US)"},
            {"code": "en-GB", "name": "English (UK)"},
            {"code": "es-ES", "name": "Spanish (Spain)"},
            {"code": "es-MX", "name": "Spanish (Mexico)"},
            {"code": "fr-FR", "name": "French"},
            {"code": "de-DE", "name": "German"},
            {"code": "it-IT", "name": "Italian"},
            {"code": "pt-BR", "name": "Portuguese (Brazil)"},
            {"code": "zh-CN", "name": "Chinese (Simplified)"},
            {"code": "ja-JP", "name": "Japanese"},
            {"code": "ko-KR", "name": "Korean"},
            {"code": "hi-IN", "name": "Hindi"},
            {"code": "ar-SA", "name": "Arabic"},
        ]
