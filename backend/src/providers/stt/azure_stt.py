"""Azure Speech-to-Text provider."""

from __future__ import annotations

from typing import Any, BinaryIO

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.stt.base import BaseSTTProvider, TranscriptionResult


@ProviderRegistry.register
class AzureSTTProvider(BaseSTTProvider):
    """Azure Cognitive Services Speech-to-Text provider."""

    provider_name = "azure_stt"
    display_name = "Azure Speech"
    description = "Microsoft Azure Speech Services with enterprise features"
    requires_api_key = True

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        self.region = config.settings.get("region", "eastus")

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "default",
                "name": "Default",
                "description": "Standard speech recognition",
            },
            {
                "id": "conversation",
                "name": "Conversation",
                "description": "Optimized for conversations",
            },
            {
                "id": "dictation",
                "name": "Dictation",
                "description": "Optimized for dictation",
            },
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "default": "eastus",
                    "description": "Azure region",
                },
                "profanity_option": {
                    "type": "string",
                    "enum": ["masked", "removed", "raw"],
                    "default": "masked",
                    "description": "Profanity handling",
                },
                "enable_dictation": {
                    "type": "boolean",
                    "default": False,
                    "description": "Enable dictation mode",
                },
            },
            "required": ["region"],
        }

    async def transcribe(
        self,
        audio: bytes | BinaryIO,
        language: str | None = None,
        **kwargs,
    ) -> TranscriptionResult:
        """Transcribe audio using Azure Speech Services."""
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError:
            raise ImportError(
                "azure-cognitiveservices-speech is required for Azure STT. "
                "Install with: pip install azure-cognitiveservices-speech"
            )

        if isinstance(audio, bytes):
            audio_data = audio
        else:
            audio_data = audio.read()

        # Configure speech
        speech_config = speechsdk.SpeechConfig(
            subscription=self.config.api_key,
            region=self.region,
        )

        if language:
            speech_config.speech_recognition_language = language

        # Set profanity option
        profanity = kwargs.get("profanity_option", "masked")
        if profanity == "masked":
            speech_config.set_profanity(speechsdk.ProfanityOption.Masked)
        elif profanity == "removed":
            speech_config.set_profanity(speechsdk.ProfanityOption.Removed)
        else:
            speech_config.set_profanity(speechsdk.ProfanityOption.Raw)

        # Enable word-level timestamps
        speech_config.request_word_level_timestamps()

        # Create audio input from bytes
        audio_stream = speechsdk.audio.PushAudioInputStream()
        audio_stream.write(audio_data)
        audio_stream.close()

        audio_config = speechsdk.audio.AudioConfig(stream=audio_stream)

        # Create recognizer
        recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            audio_config=audio_config,
        )

        # Perform recognition
        result = recognizer.recognize_once_async().get()

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # Parse detailed results
            words = None
            try:
                import json
                detailed = json.loads(result.json)
                if "NBest" in detailed and detailed["NBest"]:
                    best = detailed["NBest"][0]
                    if "Words" in best:
                        words = [
                            {
                                "word": w.get("Word"),
                                "start": w.get("Offset", 0) / 10_000_000,  # Convert to seconds
                                "end": (w.get("Offset", 0) + w.get("Duration", 0)) / 10_000_000,
                                "confidence": w.get("Confidence"),
                            }
                            for w in best["Words"]
                        ]
            except Exception:
                pass

            return TranscriptionResult(
                text=result.text,
                language=language,
                words=words,
            )
        elif result.reason == speechsdk.ResultReason.NoMatch:
            return TranscriptionResult(text="", language=language)
        else:
            raise Exception(f"Speech recognition failed: {result.reason}")

    @classmethod
    def get_supported_languages(cls) -> list[dict[str, str]]:
        return [
            {"code": "en-US", "name": "English (US)"},
            {"code": "en-GB", "name": "English (UK)"},
            {"code": "es-ES", "name": "Spanish (Spain)"},
            {"code": "fr-FR", "name": "French"},
            {"code": "de-DE", "name": "German"},
            {"code": "it-IT", "name": "Italian"},
            {"code": "pt-BR", "name": "Portuguese (Brazil)"},
            {"code": "zh-CN", "name": "Chinese (Simplified)"},
            {"code": "ja-JP", "name": "Japanese"},
            {"code": "ko-KR", "name": "Korean"},
        ]
