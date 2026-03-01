"""Azure Speech Services - TTS and STT providers."""

from __future__ import annotations

import time
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


class AzureTTSProvider(TTSProvider):
    """Azure Cognitive Services Text-to-Speech provider.

    Supports:
    - Neural voices: High-quality neural synthesis
    - Custom Neural Voice: Train your own voice
    - Audio Content Creation: Long-form audio

    Features:
    - 400+ neural voices
    - 140+ languages and variants
    - Speaking styles (news, customer service, etc.)
    - Emotion control
    - SSML support with visemes
    - Custom pronunciation
    """

    provider_name = "azure"

    # Pricing per 1M characters
    PRICING = {
        "neural": 16.00,
        "custom_neural": 24.00,
    }

    def __init__(
        self,
        subscription_key: str,
        region: str = "eastus",
        default_voice: str = "en-US-JennyNeural",
    ):
        """Initialize Azure TTS provider.

        Args:
            subscription_key: Azure Speech subscription key
            region: Azure region
            default_voice: Default voice name
        """
        self.subscription_key = subscription_key
        self.region = region
        self.default_voice = default_voice
        self.token_url = f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken"
        self.tts_url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        self._access_token: Optional[str] = None
        self._token_expires: float = 0

    async def _get_access_token(self) -> str:
        """Get or refresh access token."""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                headers={
                    "Ocp-Apim-Subscription-Key": self.subscription_key,
                    "Content-Length": "0",
                },
            )
            response.raise_for_status()

            self._access_token = response.text
            self._token_expires = time.time() + 540  # Token valid for 10 minutes
            return self._access_token

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text."""
        start_time = time.time()

        try:
            voice = request.voice or self.default_voice
            token = await self._get_access_token()

            # Map audio format
            format_map = {
                AudioFormat.MP3: "audio-24khz-48kbitrate-mono-mp3",
                AudioFormat.WAV: "riff-24khz-16bit-mono-pcm",
                AudioFormat.OGG: "ogg-24khz-16bit-mono-opus",
            }
            output_format = format_map.get(request.audio_format, "audio-24khz-48kbitrate-mono-mp3")

            # Build SSML
            ssml = self._build_ssml(request, voice)

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.tts_url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": output_format,
                        "User-Agent": "RhasspyVoiceAssistant",
                    },
                    content=ssml,
                )
                response.raise_for_status()

                audio_data = response.content

            elapsed_ms = (time.time() - start_time) * 1000

            return TTSResponse(
                audio_data=audio_data,
                audio_format=request.audio_format,
                model="neural",
                voice=voice,
                provider=self.provider_name,
                characters_used=len(request.text),
                cost_usd=self.estimate_cost(request),
                synthesis_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return TTSResponse(
                model="neural",
                voice=request.voice or self.default_voice,
                provider=self.provider_name,
                synthesis_time_ms=elapsed_ms,
                error=str(e),
            )

    def _build_ssml(self, request: TTSRequest, voice: str) -> str:
        """Build SSML from request."""
        # Extract language from voice name
        parts = voice.split("-")
        lang = "-".join(parts[:2]) if len(parts) >= 2 else "en-US"

        # Build prosody attributes
        prosody_attrs = []
        if request.speed != 1.0:
            rate = f"{int((request.speed - 1) * 100):+d}%"
            prosody_attrs.append(f'rate="{rate}"')
        if request.pitch != 0.0:
            pitch = f"{int(request.pitch):+d}%"
            prosody_attrs.append(f'pitch="{pitch}"')
        if request.volume != 0.0:
            volume = f"{int(request.volume):+d}%"
            prosody_attrs.append(f'volume="{volume}"')

        prosody_str = " ".join(prosody_attrs)

        # Build style if provided
        style_xml = ""
        if request.style:
            style_xml = f'<mstts:express-as style="{request.style}" styledegree="{request.style_degree}">'
            style_close = "</mstts:express-as>"
        else:
            style_close = ""

        # Handle SSML input
        if request.use_ssml:
            text_content = request.text
        else:
            text_content = request.text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        # Build full SSML
        if prosody_attrs:
            ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
                xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='{lang}'>
                <voice name='{voice}'>
                    {style_xml}
                    <prosody {prosody_str}>
                        {text_content}
                    </prosody>
                    {style_close}
                </voice>
            </speak>"""
        else:
            ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis'
                xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='{lang}'>
                <voice name='{voice}'>
                    {style_xml}
                    {text_content}
                    {style_close}
                </voice>
            </speak>"""

        return ssml

    def list_voices(self, language: Optional[str] = None) -> list[Voice]:
        """List available voices."""
        voices = [
            # English (US)
            Voice(id="en-US-JennyNeural", name="Jenny", language="en-US", gender=VoiceGender.FEMALE, description="Friendly, warm", provider=self.provider_name),
            Voice(id="en-US-GuyNeural", name="Guy", language="en-US", gender=VoiceGender.MALE, description="Friendly, casual", provider=self.provider_name),
            Voice(id="en-US-AriaNeural", name="Aria", language="en-US", gender=VoiceGender.FEMALE, description="Professional, clear", provider=self.provider_name),
            Voice(id="en-US-DavisNeural", name="Davis", language="en-US", gender=VoiceGender.MALE, description="Professional, confident", provider=self.provider_name),
            Voice(id="en-US-JaneNeural", name="Jane", language="en-US", gender=VoiceGender.FEMALE, description="Calm, soothing", provider=self.provider_name),
            Voice(id="en-US-JasonNeural", name="Jason", language="en-US", gender=VoiceGender.MALE, description="Casual, friendly", provider=self.provider_name),
            Voice(id="en-US-SaraNeural", name="Sara", language="en-US", gender=VoiceGender.FEMALE, description="Young, cheerful", provider=self.provider_name),
            Voice(id="en-US-TonyNeural", name="Tony", language="en-US", gender=VoiceGender.MALE, description="Narrator, storyteller", provider=self.provider_name),
            # English (UK)
            Voice(id="en-GB-SoniaNeural", name="Sonia", language="en-GB", gender=VoiceGender.FEMALE, description="Professional, British", provider=self.provider_name),
            Voice(id="en-GB-RyanNeural", name="Ryan", language="en-GB", gender=VoiceGender.MALE, description="Friendly, British", provider=self.provider_name),
            # Spanish
            Voice(id="es-ES-ElviraNeural", name="Elvira", language="es-ES", gender=VoiceGender.FEMALE, description="Professional", provider=self.provider_name),
            Voice(id="es-MX-DaliaNeural", name="Dalia", language="es-MX", gender=VoiceGender.FEMALE, description="Mexican Spanish", provider=self.provider_name),
            # French
            Voice(id="fr-FR-DeniseNeural", name="Denise", language="fr-FR", gender=VoiceGender.FEMALE, description="Professional", provider=self.provider_name),
            Voice(id="fr-FR-HenriNeural", name="Henri", language="fr-FR", gender=VoiceGender.MALE, description="Casual", provider=self.provider_name),
            # German
            Voice(id="de-DE-KatjaNeural", name="Katja", language="de-DE", gender=VoiceGender.FEMALE, description="Professional", provider=self.provider_name),
            Voice(id="de-DE-ConradNeural", name="Conrad", language="de-DE", gender=VoiceGender.MALE, description="Professional", provider=self.provider_name),
            # Japanese
            Voice(id="ja-JP-NanamiNeural", name="Nanami", language="ja-JP", gender=VoiceGender.FEMALE, description="Natural", provider=self.provider_name),
            Voice(id="ja-JP-KeitaNeural", name="Keita", language="ja-JP", gender=VoiceGender.MALE, description="Natural", provider=self.provider_name),
            # Chinese
            Voice(id="zh-CN-XiaoxiaoNeural", name="Xiaoxiao", language="zh-CN", gender=VoiceGender.FEMALE, description="Warm, natural", provider=self.provider_name),
            Voice(id="zh-CN-YunxiNeural", name="Yunxi", language="zh-CN", gender=VoiceGender.MALE, description="Professional", provider=self.provider_name),
        ]

        if language:
            voices = [v for v in voices if v.language.startswith(language)]

        return voices

    def list_models(self) -> list[str]:
        """List available TTS models."""
        return ["neural", "custom_neural"]

    def estimate_cost(self, request: TTSRequest) -> float:
        """Estimate synthesis cost in USD."""
        price_per_million = self.PRICING.get("neural", 16.00)
        characters = len(request.text)
        return (characters / 1_000_000) * price_per_million


class AzureSTTProvider(STTProvider):
    """Azure Cognitive Services Speech-to-Text provider.

    Features:
    - Real-time transcription
    - Batch transcription
    - Custom speech models
    - Speaker diarization
    - Pronunciation assessment
    - 100+ languages
    """

    provider_name = "azure"

    # Pricing per hour
    PRICING = {
        "standard": 1.00,
        "custom": 1.40,
    }

    def __init__(
        self,
        subscription_key: str,
        region: str = "eastus",
        default_language: str = "en-US",
    ):
        """Initialize Azure STT provider.

        Args:
            subscription_key: Azure Speech subscription key
            region: Azure region
            default_language: Default language code
        """
        self.subscription_key = subscription_key
        self.region = region
        self.default_language = default_language
        self.stt_url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

    async def transcribe(self, request: STTRequest) -> STTResponse:
        """Transcribe audio to text."""
        start_time = time.time()

        try:
            # Get audio data
            if request.audio_data:
                audio_data = request.audio_data
            elif request.audio_url:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.audio_url)
                    audio_data = resp.content
            elif request.audio_file:
                audio_data = request.audio_file.read()
            else:
                raise ValueError("No audio input provided")

            # Determine content type
            content_type_map = {
                AudioFormat.WAV: "audio/wav",
                AudioFormat.OGG: "audio/ogg",
                AudioFormat.MP3: "audio/mpeg",
            }
            content_type = content_type_map.get(
                request.audio_format,
                "audio/wav"
            )

            # Build params
            params = {
                "language": request.language or self.default_language,
                "format": "detailed",
            }

            if request.profanity_filter:
                params["profanity"] = "masked"

            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    self.stt_url,
                    headers={
                        "Ocp-Apim-Subscription-Key": self.subscription_key,
                        "Content-Type": content_type,
                        "Accept": "application/json",
                    },
                    params=params,
                    content=audio_data,
                )
                response.raise_for_status()

                result = response.json()

            # Parse response
            recognition_status = result.get("RecognitionStatus", "")

            if recognition_status != "Success":
                return STTResponse(
                    model=request.model or "standard",
                    provider=self.provider_name,
                    error=f"Recognition failed: {recognition_status}",
                )

            # Get best result
            nbest = result.get("NBest", [{}])
            best = nbest[0] if nbest else {}

            text = best.get("Display", "")
            confidence = best.get("Confidence", 0.0)

            # Parse words
            words = []
            for word_data in best.get("Words", []):
                words.append(TranscriptionWord(
                    word=word_data.get("Word", ""),
                    start_time=word_data.get("Offset", 0) / 10_000_000,  # 100ns to seconds
                    end_time=(word_data.get("Offset", 0) + word_data.get("Duration", 0)) / 10_000_000,
                    confidence=word_data.get("Confidence", confidence),
                ))

            segments = []
            if words:
                segments.append(TranscriptionSegment(
                    text=text,
                    start_time=words[0].start_time,
                    end_time=words[-1].end_time,
                    confidence=confidence,
                    words=words,
                ))

            # Calculate duration
            duration = result.get("Duration", 0) / 10_000_000  # 100ns to seconds

            elapsed_ms = (time.time() - start_time) * 1000

            return STTResponse(
                text=text,
                segments=segments,
                confidence=confidence,
                detected_language=request.language or self.default_language,
                audio_duration_seconds=duration,
                model=request.model or "standard",
                provider=self.provider_name,
                cost_usd=self.estimate_cost(duration),
                transcription_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return STTResponse(
                model=request.model or "standard",
                provider=self.provider_name,
                transcription_time_ms=elapsed_ms,
                error=str(e),
            )

    def list_models(self) -> list[str]:
        """List available STT models."""
        return ["standard", "custom"]

    def list_languages(self) -> list[str]:
        """List supported languages."""
        return [
            "en-US", "en-GB", "en-AU", "en-CA", "en-IN",
            "es-ES", "es-MX", "es-US",
            "fr-FR", "fr-CA",
            "de-DE", "de-AT", "de-CH",
            "it-IT", "pt-BR", "pt-PT",
            "ja-JP", "ko-KR",
            "zh-CN", "zh-TW", "zh-HK",
            "ru-RU", "ar-EG", "ar-SA",
            "hi-IN", "nl-NL", "pl-PL",
            "tr-TR", "vi-VN", "th-TH",
            "id-ID", "ms-MY", "fil-PH",
            "sv-SE", "da-DK", "fi-FI", "nb-NO",
            "cs-CZ", "el-GR", "hu-HU", "ro-RO",
            "sk-SK", "uk-UA", "he-IL",
        ]

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost in USD."""
        hours = duration_seconds / 3600
        return hours * self.PRICING.get("standard", 1.00)
