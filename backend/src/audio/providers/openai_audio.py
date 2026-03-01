"""OpenAI Audio Providers - TTS and Whisper STT."""

from __future__ import annotations

import time
from typing import Optional, AsyncIterator

from openai import AsyncOpenAI

from src.audio.base import (
    TTSProvider,
    STTProvider,
    TTSRequest,
    TTSResponse,
    STTRequest,
    STTResponse,
    TranscriptionWord,
    TranscriptionSegment,
    Voice,
    VoiceGender,
    AudioFormat,
)


class OpenAITTSProvider(TTSProvider):
    """OpenAI Text-to-Speech provider.

    Supports:
    - TTS-1: Fast, optimized for real-time
    - TTS-1-HD: Higher quality, more detail

    Features:
    - 6 built-in voices
    - Speed control (0.25x to 4.0x)
    - Multiple output formats
    - Streaming support
    """

    provider_name = "openai"

    # Available voices
    VOICES = {
        "alloy": Voice(
            id="alloy",
            name="Alloy",
            language="en",
            gender=VoiceGender.NEUTRAL,
            description="Neutral, balanced voice",
            provider="openai",
        ),
        "echo": Voice(
            id="echo",
            name="Echo",
            language="en",
            gender=VoiceGender.MALE,
            description="Male, warm voice",
            provider="openai",
        ),
        "fable": Voice(
            id="fable",
            name="Fable",
            language="en",
            gender=VoiceGender.MALE,
            description="Male, British accent",
            provider="openai",
        ),
        "onyx": Voice(
            id="onyx",
            name="Onyx",
            language="en",
            gender=VoiceGender.MALE,
            description="Male, deep voice",
            provider="openai",
        ),
        "nova": Voice(
            id="nova",
            name="Nova",
            language="en",
            gender=VoiceGender.FEMALE,
            description="Female, young voice",
            provider="openai",
        ),
        "shimmer": Voice(
            id="shimmer",
            name="Shimmer",
            language="en",
            gender=VoiceGender.FEMALE,
            description="Female, soft voice",
            provider="openai",
        ),
    }

    # Pricing per 1M characters
    PRICING = {
        "tts-1": 15.00,
        "tts-1-hd": 30.00,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        default_model: str = "tts-1",
        default_voice: str = "alloy",
    ):
        """Initialize OpenAI TTS provider.

        Args:
            api_key: OpenAI API key
            organization: OpenAI organization ID
            default_model: Default TTS model
            default_voice: Default voice ID
        """
        self.client = AsyncOpenAI(
            api_key=api_key,
            organization=organization,
        )
        self.default_model = default_model
        self.default_voice = default_voice

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text."""
        start_time = time.time()

        try:
            # Map audio format
            format_map = {
                AudioFormat.MP3: "mp3",
                AudioFormat.WAV: "wav",
                AudioFormat.OGG: "opus",
                AudioFormat.FLAC: "flac",
                AudioFormat.AAC: "aac",
                AudioFormat.PCM: "pcm",
            }
            response_format = format_map.get(request.audio_format, "mp3")

            # Create speech
            response = await self.client.audio.speech.create(
                model=request.model or self.default_model,
                voice=request.voice or self.default_voice,
                input=request.text,
                response_format=response_format,
                speed=request.speed,
            )

            # Get audio data
            audio_data = response.content

            elapsed_ms = (time.time() - start_time) * 1000

            return TTSResponse(
                audio_data=audio_data,
                audio_format=request.audio_format,
                model=request.model or self.default_model,
                voice=request.voice or self.default_voice,
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
        format_map = {
            AudioFormat.MP3: "mp3",
            AudioFormat.WAV: "wav",
            AudioFormat.OGG: "opus",
            AudioFormat.FLAC: "flac",
            AudioFormat.AAC: "aac",
            AudioFormat.PCM: "pcm",
        }
        response_format = format_map.get(request.audio_format, "mp3")

        async with self.client.audio.speech.with_streaming_response.create(
            model=request.model or self.default_model,
            voice=request.voice or self.default_voice,
            input=request.text,
            response_format=response_format,
            speed=request.speed,
        ) as response:
            async for chunk in response.iter_bytes():
                yield chunk

    def list_voices(self, language: Optional[str] = None) -> list[Voice]:
        """List available voices."""
        voices = list(self.VOICES.values())
        if language:
            voices = [v for v in voices if v.language.startswith(language)]
        return voices

    def list_models(self) -> list[str]:
        """List available TTS models."""
        return ["tts-1", "tts-1-hd"]

    def estimate_cost(self, request: TTSRequest) -> float:
        """Estimate synthesis cost in USD."""
        model = request.model or self.default_model
        price_per_million = self.PRICING.get(model, 15.00)
        characters = len(request.text)
        return (characters / 1_000_000) * price_per_million


class OpenAISTTProvider(STTProvider):
    """OpenAI Whisper Speech-to-Text provider.

    Supports:
    - whisper-1: Multilingual transcription and translation

    Features:
    - Automatic language detection
    - Translation to English
    - Word-level timestamps
    - Multiple audio format support
    """

    provider_name = "openai"

    # Supported languages (subset)
    LANGUAGES = [
        "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr",
        "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi",
        "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no",
    ]

    # Pricing per minute
    PRICING = {
        "whisper-1": 0.006,  # $0.006 per minute
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        organization: Optional[str] = None,
        default_model: str = "whisper-1",
    ):
        """Initialize OpenAI STT provider.

        Args:
            api_key: OpenAI API key
            organization: OpenAI organization ID
            default_model: Default Whisper model
        """
        self.client = AsyncOpenAI(
            api_key=api_key,
            organization=organization,
        )
        self.default_model = default_model

    async def transcribe(self, request: STTRequest) -> STTResponse:
        """Transcribe audio to text."""
        start_time = time.time()

        try:
            # Prepare audio file
            if request.audio_data:
                audio_file = ("audio.mp3", request.audio_data)
            elif request.audio_file:
                audio_file = request.audio_file
            elif request.audio_url:
                # Download audio
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.audio_url)
                    audio_file = ("audio.mp3", resp.content)
            else:
                raise ValueError("No audio input provided")

            # Build params
            params = {
                "model": request.model or self.default_model,
                "file": audio_file,
            }

            if request.language:
                params["language"] = request.language

            if request.word_timestamps:
                params["timestamp_granularities"] = ["word", "segment"]
                params["response_format"] = "verbose_json"
            else:
                params["response_format"] = "verbose_json"

            if request.vocabulary:
                params["prompt"] = " ".join(request.vocabulary)

            # Transcribe
            response = await self.client.audio.transcriptions.create(**params)

            # Parse response
            text = response.text
            segments = []

            if hasattr(response, "segments") and response.segments:
                for seg in response.segments:
                    words = []
                    if hasattr(response, "words") and response.words:
                        # Find words in this segment
                        for word in response.words:
                            if seg.start <= word.start < seg.end:
                                words.append(TranscriptionWord(
                                    word=word.word,
                                    start_time=word.start,
                                    end_time=word.end,
                                    confidence=1.0,  # Whisper doesn't provide word confidence
                                ))

                    segments.append(TranscriptionSegment(
                        text=seg.text,
                        start_time=seg.start,
                        end_time=seg.end,
                        confidence=1.0,
                        words=words,
                    ))

            duration = response.duration if hasattr(response, "duration") else 0

            elapsed_ms = (time.time() - start_time) * 1000

            return STTResponse(
                text=text,
                segments=segments,
                confidence=1.0,
                detected_language=response.language if hasattr(response, "language") else None,
                audio_duration_seconds=duration,
                model=request.model or self.default_model,
                provider=self.provider_name,
                cost_usd=self.estimate_cost(duration),
                transcription_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return STTResponse(
                model=request.model or self.default_model,
                provider=self.provider_name,
                transcription_time_ms=elapsed_ms,
                error=str(e),
            )

    def list_models(self) -> list[str]:
        """List available STT models."""
        return ["whisper-1"]

    def list_languages(self) -> list[str]:
        """List supported languages."""
        return self.LANGUAGES

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost in USD."""
        minutes = duration_seconds / 60
        return minutes * self.PRICING["whisper-1"]
