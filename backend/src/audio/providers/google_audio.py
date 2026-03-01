"""Google Cloud Audio Providers - TTS and STT."""

from __future__ import annotations

import base64
import time
from typing import Optional, AsyncIterator

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


class GoogleTTSProvider(TTSProvider):
    """Google Cloud Text-to-Speech provider.

    Supports:
    - WaveNet: High-quality neural voices
    - Neural2: Latest neural technology
    - Studio: Professional studio voices
    - Standard: Basic synthesis

    Features:
    - 40+ languages and variants
    - 380+ voices
    - SSML support
    - Audio profiles (headphone, speaker, etc.)
    - Speaking rate and pitch control
    """

    provider_name = "google"

    # Voice types with pricing (per 1M characters)
    PRICING = {
        "Standard": 4.00,
        "WaveNet": 16.00,
        "Neural2": 16.00,
        "Studio": 160.00,
        "Polyglot": 16.00,
    }

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        default_voice: str = "en-US-Neural2-F",
    ):
        """Initialize Google TTS provider.

        Args:
            credentials_path: Path to service account JSON
            project_id: Google Cloud project ID
            default_voice: Default voice name
        """
        from google.cloud import texttospeech

        if credentials_path:
            self.client = texttospeech.TextToSpeechAsyncClient.from_service_account_file(
                credentials_path
            )
        else:
            self.client = texttospeech.TextToSpeechAsyncClient()

        self.project_id = project_id
        self.default_voice = default_voice
        self._voices_cache: Optional[list[Voice]] = None

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Synthesize speech from text."""
        from google.cloud import texttospeech

        start_time = time.time()

        try:
            voice_name = request.voice or self.default_voice

            # Parse voice name for language code
            parts = voice_name.split("-")
            language_code = "-".join(parts[:2]) if len(parts) >= 2 else "en-US"

            # Build synthesis input
            if request.use_ssml:
                synthesis_input = texttospeech.SynthesisInput(ssml=request.text)
            else:
                synthesis_input = texttospeech.SynthesisInput(text=request.text)

            # Build voice params
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name,
            )

            # Map audio format
            format_map = {
                AudioFormat.MP3: texttospeech.AudioEncoding.MP3,
                AudioFormat.WAV: texttospeech.AudioEncoding.LINEAR16,
                AudioFormat.OGG: texttospeech.AudioEncoding.OGG_OPUS,
            }
            audio_encoding = format_map.get(
                request.audio_format,
                texttospeech.AudioEncoding.MP3
            )

            # Build audio config
            audio_config = texttospeech.AudioConfig(
                audio_encoding=audio_encoding,
                speaking_rate=request.speed,
                pitch=request.pitch,
            )

            if request.sample_rate:
                audio_config.sample_rate_hertz = request.sample_rate.value

            # Synthesize
            response = await self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config,
            )

            elapsed_ms = (time.time() - start_time) * 1000

            return TTSResponse(
                audio_data=response.audio_content,
                audio_format=request.audio_format,
                model=self._get_voice_type(voice_name),
                voice=voice_name,
                provider=self.provider_name,
                characters_used=len(request.text),
                cost_usd=self.estimate_cost(request),
                synthesis_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return TTSResponse(
                model="Neural2",
                voice=request.voice or self.default_voice,
                provider=self.provider_name,
                synthesis_time_ms=elapsed_ms,
                error=str(e),
            )

    def list_voices(self, language: Optional[str] = None) -> list[Voice]:
        """List available voices."""
        # Return a subset of popular voices
        voices = [
            Voice(id="en-US-Neural2-F", name="Neural2 Female", language="en-US", gender=VoiceGender.FEMALE, provider=self.provider_name),
            Voice(id="en-US-Neural2-A", name="Neural2 Male A", language="en-US", gender=VoiceGender.MALE, provider=self.provider_name),
            Voice(id="en-US-Neural2-D", name="Neural2 Male D", language="en-US", gender=VoiceGender.MALE, provider=self.provider_name),
            Voice(id="en-US-Neural2-J", name="Neural2 Male J", language="en-US", gender=VoiceGender.MALE, provider=self.provider_name),
            Voice(id="en-US-Wavenet-F", name="WaveNet Female", language="en-US", gender=VoiceGender.FEMALE, provider=self.provider_name),
            Voice(id="en-US-Wavenet-D", name="WaveNet Male", language="en-US", gender=VoiceGender.MALE, provider=self.provider_name),
            Voice(id="en-GB-Neural2-A", name="British Neural2 Female", language="en-GB", gender=VoiceGender.FEMALE, provider=self.provider_name),
            Voice(id="en-GB-Neural2-B", name="British Neural2 Male", language="en-GB", gender=VoiceGender.MALE, provider=self.provider_name),
            Voice(id="es-ES-Neural2-A", name="Spanish Neural2 Female", language="es-ES", gender=VoiceGender.FEMALE, provider=self.provider_name),
            Voice(id="fr-FR-Neural2-A", name="French Neural2 Female", language="fr-FR", gender=VoiceGender.FEMALE, provider=self.provider_name),
            Voice(id="de-DE-Neural2-A", name="German Neural2 Female", language="de-DE", gender=VoiceGender.FEMALE, provider=self.provider_name),
            Voice(id="ja-JP-Neural2-B", name="Japanese Neural2 Female", language="ja-JP", gender=VoiceGender.FEMALE, provider=self.provider_name),
        ]

        if language:
            voices = [v for v in voices if v.language.startswith(language)]

        return voices

    async def fetch_all_voices(self) -> list[Voice]:
        """Fetch all voices from the API."""
        response = await self.client.list_voices()

        voices = []
        for v in response.voices:
            gender = VoiceGender.NEUTRAL
            if v.ssml_gender.name == "MALE":
                gender = VoiceGender.MALE
            elif v.ssml_gender.name == "FEMALE":
                gender = VoiceGender.FEMALE

            for lang in v.language_codes:
                voices.append(Voice(
                    id=v.name,
                    name=v.name,
                    language=lang,
                    gender=gender,
                    provider=self.provider_name,
                    metadata={"natural_sample_rate_hertz": v.natural_sample_rate_hertz},
                ))

        self._voices_cache = voices
        return voices

    def list_models(self) -> list[str]:
        """List available TTS models."""
        return ["Standard", "WaveNet", "Neural2", "Studio", "Polyglot"]

    def estimate_cost(self, request: TTSRequest) -> float:
        """Estimate synthesis cost in USD."""
        voice_type = self._get_voice_type(request.voice or self.default_voice)
        price_per_million = self.PRICING.get(voice_type, 16.00)
        characters = len(request.text)
        return (characters / 1_000_000) * price_per_million

    def _get_voice_type(self, voice_name: str) -> str:
        """Extract voice type from voice name."""
        if "Neural2" in voice_name:
            return "Neural2"
        elif "Wavenet" in voice_name or "WaveNet" in voice_name:
            return "WaveNet"
        elif "Studio" in voice_name:
            return "Studio"
        elif "Polyglot" in voice_name:
            return "Polyglot"
        else:
            return "Standard"


class GoogleSTTProvider(STTProvider):
    """Google Cloud Speech-to-Text provider.

    Supports:
    - Chirp: Latest universal model
    - Long: For audio > 1 minute
    - Short: For audio < 1 minute
    - Phone Call: Optimized for telephony
    - Video: Optimized for video content

    Features:
    - 125+ languages
    - Real-time streaming
    - Speaker diarization
    - Word-level timestamps
    - Automatic punctuation
    - Multi-channel recognition
    """

    provider_name = "google"

    # Pricing per minute
    PRICING = {
        "default": 0.016,
        "phone_call": 0.016,
        "video": 0.024,
        "chirp": 0.016,
    }

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
        default_model: str = "default",
    ):
        """Initialize Google STT provider.

        Args:
            credentials_path: Path to service account JSON
            project_id: Google Cloud project ID
            default_model: Default recognition model
        """
        from google.cloud import speech

        if credentials_path:
            self.client = speech.SpeechAsyncClient.from_service_account_file(
                credentials_path
            )
        else:
            self.client = speech.SpeechAsyncClient()

        self.project_id = project_id
        self.default_model = default_model

    async def transcribe(self, request: STTRequest) -> STTResponse:
        """Transcribe audio to text."""
        from google.cloud import speech

        start_time = time.time()

        try:
            # Get audio data
            if request.audio_data:
                audio_content = request.audio_data
            elif request.audio_url:
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(request.audio_url)
                    audio_content = resp.content
            elif request.audio_file:
                audio_content = request.audio_file.read()
            else:
                raise ValueError("No audio input provided")

            # Determine encoding
            encoding_map = {
                AudioFormat.WAV: speech.RecognitionConfig.AudioEncoding.LINEAR16,
                AudioFormat.FLAC: speech.RecognitionConfig.AudioEncoding.FLAC,
                AudioFormat.OGG: speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
                AudioFormat.MP3: speech.RecognitionConfig.AudioEncoding.MP3,
            }
            encoding = encoding_map.get(
                request.audio_format,
                speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
            )

            # Build recognition config
            config = speech.RecognitionConfig(
                encoding=encoding,
                sample_rate_hertz=request.sample_rate or 16000,
                language_code=request.language or "en-US",
                enable_automatic_punctuation=request.punctuate,
                enable_word_time_offsets=request.word_timestamps,
                profanity_filter=request.profanity_filter,
            )

            if request.speaker_diarization:
                config.diarization_config = speech.SpeakerDiarizationConfig(
                    enable_speaker_diarization=True,
                    min_speaker_count=1,
                    max_speaker_count=request.max_speakers,
                )

            if request.vocabulary:
                config.speech_contexts = [
                    speech.SpeechContext(phrases=request.vocabulary)
                ]

            # Build audio
            audio = speech.RecognitionAudio(content=audio_content)

            # Recognize
            response = await self.client.recognize(config=config, audio=audio)

            # Parse results
            text = ""
            segments = []
            confidence = 0.0

            for result in response.results:
                if result.alternatives:
                    alt = result.alternatives[0]
                    text += alt.transcript + " "
                    confidence = max(confidence, alt.confidence)

                    words = []
                    for word_info in alt.words:
                        words.append(TranscriptionWord(
                            word=word_info.word,
                            start_time=word_info.start_time.total_seconds(),
                            end_time=word_info.end_time.total_seconds(),
                            confidence=confidence,
                            speaker=word_info.speaker_tag if hasattr(word_info, "speaker_tag") else None,
                        ))

                    if words:
                        segments.append(TranscriptionSegment(
                            text=alt.transcript,
                            start_time=words[0].start_time,
                            end_time=words[-1].end_time,
                            confidence=confidence,
                            words=words,
                        ))

            text = text.strip()

            elapsed_ms = (time.time() - start_time) * 1000

            return STTResponse(
                text=text,
                segments=segments,
                confidence=confidence,
                detected_language=request.language,
                model=request.model or self.default_model,
                provider=self.provider_name,
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
        return ["default", "phone_call", "video", "command_and_search", "chirp"]

    def list_languages(self) -> list[str]:
        """List supported languages."""
        return [
            "en-US", "en-GB", "en-AU", "en-IN",
            "es-ES", "es-MX", "es-US",
            "fr-FR", "fr-CA",
            "de-DE", "it-IT", "pt-BR", "pt-PT",
            "ja-JP", "ko-KR", "zh-CN", "zh-TW",
            "ru-RU", "ar-EG", "hi-IN", "nl-NL",
            "pl-PL", "tr-TR", "vi-VN", "th-TH",
            "id-ID", "ms-MY", "fil-PH",
        ]

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estimate transcription cost in USD."""
        minutes = duration_seconds / 60
        return minutes * self.PRICING.get(self.default_model, 0.016)
