"""Deepgram Audio Providers - TTS (Aura) and STT (Nova-2)."""

from __future__ import annotations

import time
import json
from typing import Optional, AsyncIterator

import httpx

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


class DeepgramTTSProvider(TTSProvider):
    """Deepgram Aura Text-to-Speech provider.

    Features:
    - Ultra-low latency (<250ms)
    - High-quality neural voices
    - Streaming support
    - 12+ voices
    """

    provider_name = "deepgram"

    BASE_URL = "https://api.deepgram.com/v1"

    # Available Aura voices
    VOICES = {
        "aura-asteria-en": Voice(
            id="aura-asteria-en",
            name="Asteria",
            language="en",
            gender=VoiceGender.FEMALE,
            description="American, professional",
            provider="deepgram",
        ),
        "aura-luna-en": Voice(
            id="aura-luna-en",
            name="Luna",
            language="en",
            gender=VoiceGender.FEMALE,
            description="American, warm",
            provider="deepgram",
        ),
        "aura-stella-en": Voice(
            id="aura-stella-en",
            name="Stella",
            language="en",
            gender=VoiceGender.FEMALE,
            description="American, authoritative",
            provider="deepgram",
        ),
        "aura-athena-en": Voice(
            id="aura-athena-en",
            name="Athena",
            language="en",
            gender=VoiceGender.FEMALE,
            description="British, sophisticated",
            provider="deepgram",
        ),
        "aura-hera-en": Voice(
            id="aura-hera-en",
            name="Hera",
            language="en",
            gender=VoiceGender.FEMALE,
            description="American, caring",
            provider="deepgram",
        ),
        "aura-orion-en": Voice(
            id="aura-orion-en",
            name="Orion",
            language="en",
            gender=VoiceGender.MALE,
            description="American, confident",
            provider="deepgram",
        ),
        "aura-arcas-en": Voice(
            id="aura-arcas-en",
            name="Arcas",
            language="en",
            gender=VoiceGender.MALE,
            description="American, friendly",
            provider="deepgram",
        ),
        "aura-perseus-en": Voice(
            id="aura-perseus-en",
            name="Perseus",
            language="en",
            gender=VoiceGender.MALE,
            description="American, deep",
            provider="deepgram",
        ),
        "aura-angus-en": Voice(
            id="aura-angus-en",
            name="Angus",
            language="en",
            gender=VoiceGender.MALE,
            description="Irish, warm",
            provider="deepgram",
        ),
        "aura-orpheus-en": Voice(
            id="aura-orpheus-en",
            name="Orpheus",
            language="en",
            gender=VoiceGender.MALE,
            description="American, narrator",
            provider="deepgram",
        ),
        "aura-helios-en": Voice(
            id="aura-helios-en",
            name="Helios",
            language="en",
            gender=VoiceGender.MALE,
            description="British, authoritative",
            provider="deepgram",
        ),
        "aura-zeus-en": Voice(
            id="aura-zeus-en",
            name="Zeus",
            language="en",
            gender=VoiceGender.MALE,
            description="American, powerful",
            provider="deepgram",
        ),
    }

    # Pricing per character
    PRICING = 0.0135 / 1000  # $0.0135 per 1000 characters

    def __init__(
        self,
        api_key: str,
        default_voice: str = "aura-asteria-en",
        timeout: float = 30.0,
    ):
        """Initialize Deepgram TTS provider.

        Args:
            api_key: Deepgram API key
            default_voice: Default voice ID
            timeout: Request timeout
        """
        self.api_key = api_key
        self.default_voice = default_voice
        self.timeout = timeout

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text."""
        start_time = time.time()

        try:
            voice = request.voice or self.default_voice

            # Map audio format
            format_map = {
                AudioFormat.MP3: "mp3",
                AudioFormat.WAV: "wav",
                AudioFormat.OGG: "ogg",
                AudioFormat.FLAC: "flac",
                AudioFormat.AAC: "aac",
            }
            encoding = format_map.get(request.audio_format, "mp3")

            # Build params
            params = {
                "model": voice,
                "encoding": encoding,
            }

            if request.sample_rate:
                params["sample_rate"] = request.sample_rate.value

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.BASE_URL}/speak",
                    headers={
                        "Authorization": f"Token {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    params=params,
                    json={"text": request.text},
                )
                response.raise_for_status()

                audio_data = response.content

            elapsed_ms = (time.time() - start_time) * 1000

            return TTSResponse(
                audio_data=audio_data,
                audio_format=request.audio_format,
                model="aura",
                voice=voice,
                provider=self.provider_name,
                characters_used=len(request.text),
                cost_usd=len(request.text) * self.PRICING,
                synthesis_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return TTSResponse(
                model="aura",
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
        voice = request.voice or self.default_voice

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/speak",
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                },
                params={"model": voice},
                json={"text": request.text},
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes():
                    yield chunk

    def list_voices(self, language: Optional[str] = None) -> list[Voice]:
        """List available voices."""
        voices = list(self.VOICES.values())
        if language:
            voices = [v for v in voices if v.language.startswith(language)]
        return voices

    def list_models(self) -> list[str]:
        """List available TTS models."""
        return ["aura"]

    def estimate_cost(self, request: TTSRequest) -> float:
        """Estimate synthesis cost in USD."""
        return len(request.text) * self.PRICING


class DeepgramSTTProvider(STTProvider):
    """Deepgram Speech-to-Text provider.

    Supports:
    - Nova-2: Highest accuracy
    - Nova: Fast and accurate
    - Enhanced: General purpose
    - Base: Fastest processing

    Features:
    - Real-time streaming
    - Speaker diarization
    - Word-level timestamps
    - Smart formatting
    - 30+ languages
    """

    provider_name = "deepgram"

    BASE_URL = "https://api.deepgram.com/v1"

    # Available models
    MODELS = {
        "nova-2": "Nova-2 (Highest accuracy)",
        "nova-2-general": "Nova-2 General",
        "nova-2-meeting": "Nova-2 Meeting",
        "nova-2-phonecall": "Nova-2 Phone Call",
        "nova": "Nova",
        "enhanced": "Enhanced",
        "base": "Base (Fastest)",
    }

    # Supported languages
    LANGUAGES = [
        "en", "en-US", "en-GB", "en-AU", "en-IN",
        "es", "es-ES", "es-419",
        "fr", "fr-FR", "fr-CA",
        "de", "it", "pt", "pt-BR",
        "nl", "ja", "ko", "zh", "zh-CN", "zh-TW",
        "ru", "pl", "tr", "ar", "hi", "id", "vi", "th",
    ]

    # Pricing per minute
    PRICING = {
        "nova-2": 0.0043,
        "nova": 0.0043,
        "enhanced": 0.0043,
        "base": 0.0025,
    }

    def __init__(
        self,
        api_key: str,
        default_model: str = "nova-2",
        timeout: float = 120.0,
    ):
        """Initialize Deepgram STT provider.

        Args:
            api_key: Deepgram API key
            default_model: Default model
            timeout: Request timeout
        """
        self.api_key = api_key
        self.default_model = default_model
        self.timeout = timeout

    async def transcribe(self, request: STTRequest) -> STTResponse:
        """Transcribe audio to text."""
        start_time = time.time()

        try:
            # Get audio data
            if request.audio_data:
                audio_data = request.audio_data
                content_type = "audio/mpeg"
            elif request.audio_url:
                # Use URL directly
                audio_data = None
                content_type = None
            elif request.audio_file:
                audio_data = request.audio_file.read()
                content_type = "audio/mpeg"
            else:
                raise ValueError("No audio input provided")

            # Build query params
            params = {
                "model": request.model or self.default_model,
                "punctuate": str(request.punctuate).lower(),
                "smart_format": "true",
                "utterances": "true",
            }

            if request.language:
                params["language"] = request.language
            else:
                params["detect_language"] = "true"

            if request.word_timestamps:
                params["words"] = "true"

            if request.speaker_diarization:
                params["diarize"] = "true"
                if request.max_speakers:
                    params["diarize_version"] = "2"

            if request.vocabulary:
                params["keywords"] = ",".join(request.vocabulary)

            if request.profanity_filter:
                params["profanity_filter"] = "true"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if audio_data:
                    # Direct audio upload
                    response = await client.post(
                        f"{self.BASE_URL}/listen",
                        headers={
                            "Authorization": f"Token {self.api_key}",
                            "Content-Type": content_type,
                        },
                        params=params,
                        content=audio_data,
                    )
                else:
                    # URL-based transcription
                    response = await client.post(
                        f"{self.BASE_URL}/listen",
                        headers={
                            "Authorization": f"Token {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        params=params,
                        json={"url": request.audio_url},
                    )

                response.raise_for_status()
                result = response.json()

            # Parse response
            results = result.get("results", {})
            channels = results.get("channels", [{}])
            alternatives = channels[0].get("alternatives", [{}]) if channels else [{}]
            best = alternatives[0] if alternatives else {}

            # Get transcript
            text = best.get("transcript", "")
            confidence = best.get("confidence", 0.0)

            # Parse words
            segments = []
            if "paragraphs" in best:
                for para in best.get("paragraphs", {}).get("paragraphs", []):
                    for sentence in para.get("sentences", []):
                        words = []
                        for word_data in sentence.get("words", []):
                            words.append(TranscriptionWord(
                                word=word_data.get("word", ""),
                                start_time=word_data.get("start", 0),
                                end_time=word_data.get("end", 0),
                                confidence=word_data.get("confidence", 0),
                                speaker=word_data.get("speaker"),
                            ))

                        segments.append(TranscriptionSegment(
                            text=sentence.get("text", ""),
                            start_time=sentence.get("start", 0),
                            end_time=sentence.get("end", 0),
                            confidence=confidence,
                            words=words,
                            speaker=para.get("speaker"),
                        ))
            elif "words" in best:
                # Build segments from words
                words = []
                for word_data in best.get("words", []):
                    words.append(TranscriptionWord(
                        word=word_data.get("word", ""),
                        start_time=word_data.get("start", 0),
                        end_time=word_data.get("end", 0),
                        confidence=word_data.get("confidence", 0),
                        speaker=word_data.get("speaker"),
                    ))

                if words:
                    segments.append(TranscriptionSegment(
                        text=text,
                        start_time=words[0].start_time,
                        end_time=words[-1].end_time,
                        confidence=confidence,
                        words=words,
                    ))

            # Get metadata
            metadata = result.get("metadata", {})
            duration = metadata.get("duration", 0)
            detected_language = results.get("channels", [{}])[0].get("detected_language")

            elapsed_ms = (time.time() - start_time) * 1000

            return STTResponse(
                text=text,
                segments=segments,
                confidence=confidence,
                detected_language=detected_language,
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

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes],
        request: STTRequest,
    ) -> AsyncIterator[STTResponse]:
        """Stream transcription results via WebSocket."""
        import websockets

        # Build WebSocket URL
        params = {
            "model": request.model or self.default_model,
            "punctuate": str(request.punctuate).lower(),
            "interim_results": str(request.interim_results).lower(),
        }

        if request.language:
            params["language"] = request.language

        if request.word_timestamps:
            params["words"] = "true"

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        ws_url = f"wss://api.deepgram.com/v1/listen?{param_str}"

        async with websockets.connect(
            ws_url,
            extra_headers={"Authorization": f"Token {self.api_key}"},
        ) as ws:
            # Start sending audio
            async def send_audio():
                async for chunk in audio_stream:
                    await ws.send(chunk)
                await ws.send(json.dumps({"type": "CloseStream"}))

            import asyncio
            send_task = asyncio.create_task(send_audio())

            try:
                async for message in ws:
                    data = json.loads(message)

                    if data.get("type") == "Results":
                        channel = data.get("channel", {})
                        alternatives = channel.get("alternatives", [{}])
                        best = alternatives[0] if alternatives else {}

                        yield STTResponse(
                            text=best.get("transcript", ""),
                            confidence=best.get("confidence", 0.0),
                            model=request.model or self.default_model,
                            provider=self.provider_name,
                        )
            finally:
                send_task.cancel()

    def list_models(self) -> list[str]:
        """List available STT models."""
        return list(self.MODELS.keys())

    def list_languages(self) -> list[str]:
        """List supported languages."""
        return self.LANGUAGES

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost in USD."""
        minutes = duration_seconds / 60
        return minutes * self.PRICING.get(self.default_model, 0.0043)
