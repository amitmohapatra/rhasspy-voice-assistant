"""Google Cloud Text-to-Speech provider."""

from __future__ import annotations

from typing import Any

from src.providers.base import ProviderRegistry, ProviderConfig
from src.providers.tts.base import BaseTTSProvider, SpeechResult, VoiceInfo


@ProviderRegistry.register
class GoogleTTSProvider(BaseTTSProvider):
    """Google Cloud Text-to-Speech provider."""

    provider_name = "google_tts"
    display_name = "Google Cloud TTS"
    description = "Google Cloud TTS with WaveNet and Neural2 voices"
    requires_api_key = True

    def __init__(self, config: ProviderConfig):
        super().__init__(config)

    @classmethod
    def get_available_models(cls) -> list[dict[str, Any]]:
        return [
            {
                "id": "neural2",
                "name": "Neural2",
                "description": "Latest neural voice technology",
            },
            {
                "id": "wavenet",
                "name": "WaveNet",
                "description": "High-quality DeepMind voices",
            },
            {
                "id": "standard",
                "name": "Standard",
                "description": "Basic synthesis",
            },
            {
                "id": "studio",
                "name": "Studio",
                "description": "Premium studio quality",
            },
        ]

    @classmethod
    def get_available_voices(cls) -> list[VoiceInfo]:
        return [
            VoiceInfo(id="en-US-Neural2-A", name="Neural2-A", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Neural2-C", name="Neural2-C", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Neural2-D", name="Neural2-D", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Neural2-E", name="Neural2-E", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Neural2-F", name="Neural2-F", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Neural2-G", name="Neural2-G", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Neural2-H", name="Neural2-H", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Neural2-I", name="Neural2-I", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Neural2-J", name="Neural2-J", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Wavenet-A", name="Wavenet-A", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Wavenet-B", name="Wavenet-B", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Wavenet-C", name="Wavenet-C", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Wavenet-D", name="Wavenet-D", language="en-US", gender="male"),
            VoiceInfo(id="en-US-Wavenet-E", name="Wavenet-E", language="en-US", gender="female"),
            VoiceInfo(id="en-US-Wavenet-F", name="Wavenet-F", language="en-US", gender="female"),
        ]

    @classmethod
    def get_settings_schema(cls) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "speaking_rate": {
                    "type": "number",
                    "minimum": 0.25,
                    "maximum": 4.0,
                    "default": 1.0,
                    "description": "Speaking rate",
                },
                "pitch": {
                    "type": "number",
                    "minimum": -20.0,
                    "maximum": 20.0,
                    "default": 0,
                    "description": "Pitch adjustment in semitones",
                },
                "volume_gain_db": {
                    "type": "number",
                    "minimum": -96.0,
                    "maximum": 16.0,
                    "default": 0,
                    "description": "Volume gain in dB",
                },
                "audio_encoding": {
                    "type": "string",
                    "enum": ["MP3", "LINEAR16", "OGG_OPUS", "MULAW", "ALAW"],
                    "default": "MP3",
                    "description": "Audio encoding",
                },
            },
        }

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        **kwargs,
    ) -> SpeechResult:
        """Synthesize speech using Google Cloud TTS."""
        try:
            from google.cloud import texttospeech_v1 as texttospeech
        except ImportError:
            raise ImportError(
                "google-cloud-texttospeech is required for Google TTS. "
                "Install with: pip install google-cloud-texttospeech"
            )

        voice = voice or "en-US-Neural2-C"
        audio_encoding_str = kwargs.get("audio_encoding", "MP3")

        # Parse voice name
        parts = voice.split("-")
        language_code = f"{parts[0]}-{parts[1]}" if len(parts) >= 2 else "en-US"

        client = texttospeech.TextToSpeechAsyncClient()

        # Configure synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Configure voice
        voice_params = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice,
        )

        # Configure audio
        audio_encoding = getattr(texttospeech.AudioEncoding, audio_encoding_str)
        audio_config = texttospeech.AudioConfig(
            audio_encoding=audio_encoding,
            speaking_rate=kwargs.get("speaking_rate", 1.0),
            pitch=kwargs.get("pitch", 0),
            volume_gain_db=kwargs.get("volume_gain_db", 0),
        )

        # Perform synthesis
        response = await client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )

        format_map = {
            "MP3": "mp3",
            "LINEAR16": "wav",
            "OGG_OPUS": "ogg",
            "MULAW": "wav",
            "ALAW": "wav",
        }

        return SpeechResult(
            audio=response.audio_content,
            format=format_map.get(audio_encoding_str, "mp3"),
        )
