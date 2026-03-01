"""Voice Activity Detection (VAD) for real-time conversation.

Supports multiple VAD backends:
- WebRTC VAD (fast, good for real-time)
- Silero VAD (more accurate, ML-based)
- Energy-based VAD (simple threshold)
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Any
import numpy as np

logger = logging.getLogger(__name__)


class VADBackend(str, Enum):
    """Available VAD backends."""
    WEBRTC = "webrtc"
    SILERO = "silero"
    ENERGY = "energy"


class SpeechState(str, Enum):
    """Current speech state."""
    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEAKING = "speaking"
    SPEECH_END = "speech_end"


@dataclass
class VADConfig:
    """VAD configuration."""
    backend: VADBackend = VADBackend.ENERGY
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # 10, 20, or 30 ms

    # Energy-based VAD
    energy_threshold: float = 0.01

    # WebRTC VAD
    webrtc_aggressiveness: int = 3  # 0-3, higher = more aggressive

    # Speech detection timing
    speech_pad_ms: int = 300  # Padding around speech
    min_speech_duration_ms: int = 250  # Minimum speech duration
    max_silence_duration_ms: int = 500  # Max silence before speech end

    # Interruption detection
    interruption_threshold_ms: int = 200  # Time to detect interruption


@dataclass
class VADResult:
    """Result from VAD processing."""
    state: SpeechState
    is_speech: bool
    confidence: float
    speech_duration_ms: int
    silence_duration_ms: int
    should_interrupt: bool


class BaseVAD(ABC):
    """Base class for VAD implementations."""

    def __init__(self, config: VADConfig):
        self.config = config
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        self._last_state = SpeechState.SILENCE

    @abstractmethod
    def process_frame(self, audio_frame: bytes) -> bool:
        """Process a single audio frame and return True if speech detected."""
        pass

    def process(self, audio_frame: bytes) -> VADResult:
        """Process audio frame and return full VAD result."""
        is_speech = self.process_frame(audio_frame)

        frame_duration_ms = self.config.frame_duration_ms

        if is_speech:
            self._speech_frames += 1
            self._silence_frames = 0
        else:
            self._silence_frames += 1
            if self._is_speaking:
                pass  # Keep counting silence during speech
            else:
                self._speech_frames = 0

        speech_duration_ms = self._speech_frames * frame_duration_ms
        silence_duration_ms = self._silence_frames * frame_duration_ms

        # State machine
        state = self._last_state
        should_interrupt = False

        if not self._is_speaking:
            if speech_duration_ms >= self.config.min_speech_duration_ms:
                self._is_speaking = True
                state = SpeechState.SPEECH_START
        else:
            if silence_duration_ms >= self.config.max_silence_duration_ms:
                self._is_speaking = False
                state = SpeechState.SPEECH_END
                self._speech_frames = 0
                self._silence_frames = 0
            elif is_speech:
                state = SpeechState.SPEAKING
                # Check for interruption (speech during expected silence)
                if speech_duration_ms >= self.config.interruption_threshold_ms:
                    should_interrupt = True

        if not self._is_speaking and not is_speech:
            state = SpeechState.SILENCE

        self._last_state = state

        return VADResult(
            state=state,
            is_speech=is_speech,
            confidence=1.0 if is_speech else 0.0,
            speech_duration_ms=speech_duration_ms,
            silence_duration_ms=silence_duration_ms,
            should_interrupt=should_interrupt,
        )

    def reset(self):
        """Reset VAD state."""
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        self._last_state = SpeechState.SILENCE


class EnergyVAD(BaseVAD):
    """Simple energy-based VAD."""

    def process_frame(self, audio_frame: bytes) -> bool:
        """Detect speech based on audio energy."""
        # Convert bytes to numpy array
        audio = np.frombuffer(audio_frame, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0  # Normalize to [-1, 1]

        # Calculate RMS energy
        energy = np.sqrt(np.mean(audio ** 2))

        return energy > self.config.energy_threshold


class WebRTCVAD(BaseVAD):
    """WebRTC-based VAD (requires webrtcvad package)."""

    def __init__(self, config: VADConfig):
        super().__init__(config)
        self._vad = None

    def _get_vad(self):
        if self._vad is None:
            try:
                import webrtcvad
                self._vad = webrtcvad.Vad(self.config.webrtc_aggressiveness)
            except ImportError:
                raise ImportError("webrtcvad is required for WebRTC VAD backend")
        return self._vad

    def process_frame(self, audio_frame: bytes) -> bool:
        """Detect speech using WebRTC VAD."""
        vad = self._get_vad()

        # WebRTC VAD expects specific frame sizes
        # 10ms: 160 samples, 20ms: 320 samples, 30ms: 480 samples (at 16kHz)
        expected_samples = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
        expected_bytes = expected_samples * 2  # 16-bit audio

        if len(audio_frame) != expected_bytes:
            # Pad or truncate
            if len(audio_frame) < expected_bytes:
                audio_frame = audio_frame + b'\x00' * (expected_bytes - len(audio_frame))
            else:
                audio_frame = audio_frame[:expected_bytes]

        try:
            return vad.is_speech(audio_frame, self.config.sample_rate)
        except Exception as e:
            logger.warning(f"WebRTC VAD error: {e}")
            return False


class SileroVAD(BaseVAD):
    """Silero VAD (ML-based, more accurate)."""

    def __init__(self, config: VADConfig):
        super().__init__(config)
        self._model = None
        self._utils = None

    def _get_model(self):
        if self._model is None:
            try:
                import torch
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=True,
                )
                self._model = model
                self._utils = utils
            except Exception as e:
                logger.error(f"Failed to load Silero VAD: {e}")
                raise ImportError("torch and silero-vad are required for Silero VAD backend")
        return self._model

    def process_frame(self, audio_frame: bytes) -> bool:
        """Detect speech using Silero VAD."""
        import torch

        model = self._get_model()

        # Convert bytes to tensor
        audio = np.frombuffer(audio_frame, dtype=np.int16).astype(np.float32)
        audio = audio / 32768.0
        audio_tensor = torch.from_numpy(audio)

        # Get speech probability
        speech_prob = model(audio_tensor, self.config.sample_rate).item()

        return speech_prob > 0.5


def create_vad(config: VADConfig | None = None) -> BaseVAD:
    """Create a VAD instance based on configuration."""
    if config is None:
        config = VADConfig()

    if config.backend == VADBackend.WEBRTC:
        return WebRTCVAD(config)
    elif config.backend == VADBackend.SILERO:
        return SileroVAD(config)
    else:
        return EnergyVAD(config)


class ConversationVADManager:
    """Manages VAD for real-time conversation with interruption support.

    This class handles:
    - Detecting when user starts speaking
    - Detecting when user interrupts the AI
    - Managing turn-taking in conversation
    """

    def __init__(
        self,
        config: VADConfig | None = None,
        on_speech_start: Callable[[], Any] | None = None,
        on_speech_end: Callable[[bytes], Any] | None = None,
        on_interruption: Callable[[], Any] | None = None,
    ):
        self.config = config or VADConfig()
        self.vad = create_vad(self.config)

        # Callbacks
        self.on_speech_start = on_speech_start
        self.on_speech_end = on_speech_end
        self.on_interruption = on_interruption

        # State
        self._audio_buffer: list[bytes] = []
        self._is_ai_speaking = False
        self._is_user_speaking = False
        self._lock = asyncio.Lock()

    async def set_ai_speaking(self, speaking: bool):
        """Set whether the AI is currently speaking."""
        async with self._lock:
            self._is_ai_speaking = speaking
            if not speaking:
                # Reset VAD when AI stops speaking
                self.vad.reset()

    async def process_audio(self, audio_chunk: bytes) -> VADResult:
        """Process incoming audio and handle conversation flow.

        Args:
            audio_chunk: Raw audio bytes (16-bit PCM, 16kHz mono)

        Returns:
            VADResult with current state and actions
        """
        async with self._lock:
            result = self.vad.process(audio_chunk)

            # Handle speech start
            if result.state == SpeechState.SPEECH_START:
                if self._is_ai_speaking:
                    # User interrupted the AI
                    result = VADResult(
                        state=result.state,
                        is_speech=result.is_speech,
                        confidence=result.confidence,
                        speech_duration_ms=result.speech_duration_ms,
                        silence_duration_ms=result.silence_duration_ms,
                        should_interrupt=True,
                    )
                    if self.on_interruption:
                        await self._safe_callback(self.on_interruption)
                else:
                    self._is_user_speaking = True
                    self._audio_buffer = [audio_chunk]
                    if self.on_speech_start:
                        await self._safe_callback(self.on_speech_start)

            # Collect audio during speech
            elif result.state == SpeechState.SPEAKING:
                if self._is_user_speaking:
                    self._audio_buffer.append(audio_chunk)

            # Handle speech end
            elif result.state == SpeechState.SPEECH_END:
                if self._is_user_speaking:
                    self._audio_buffer.append(audio_chunk)
                    # Combine all audio
                    full_audio = b''.join(self._audio_buffer)
                    self._audio_buffer = []
                    self._is_user_speaking = False

                    if self.on_speech_end:
                        await self._safe_callback(self.on_speech_end, full_audio)

            return result

    async def _safe_callback(self, callback: Callable, *args):
        """Safely execute a callback."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")

    def reset(self):
        """Reset all state."""
        self.vad.reset()
        self._audio_buffer = []
        self._is_ai_speaking = False
        self._is_user_speaking = False


class RealtimeConversationSession:
    """Full real-time conversation session with VAD, STT, TTS, and LLM.

    This class orchestrates:
    - VAD for speech detection and interruption
    - STT for transcribing user speech
    - LLM for generating responses
    - TTS for synthesizing AI speech
    - WebSocket communication for real-time updates
    """

    def __init__(
        self,
        session_id: str,
        vad_config: VADConfig | None = None,
    ):
        self.session_id = session_id
        self.vad_manager = ConversationVADManager(
            config=vad_config,
            on_speech_start=self._on_user_speech_start,
            on_speech_end=self._on_user_speech_end,
            on_interruption=self._on_user_interruption,
        )

        # State
        self._is_active = False
        self._current_response_task: asyncio.Task | None = None
        self._message_queue: asyncio.Queue = asyncio.Queue()

        # Callbacks (set by the caller)
        self.on_transcription: Callable[[str], Any] | None = None
        self.on_response_start: Callable[[], Any] | None = None
        self.on_response_chunk: Callable[[str, bytes], Any] | None = None
        self.on_response_end: Callable[[], Any] | None = None
        self.on_error: Callable[[str], Any] | None = None

        # Services (injected)
        self.stt_service = None
        self.tts_service = None
        self.llm_service = None

    async def start(self):
        """Start the conversation session."""
        self._is_active = True
        logger.info(f"Started conversation session {self.session_id}")

    async def stop(self):
        """Stop the conversation session."""
        self._is_active = False

        # Cancel any pending response
        if self._current_response_task:
            self._current_response_task.cancel()
            try:
                await self._current_response_task
            except asyncio.CancelledError:
                pass

        self.vad_manager.reset()
        logger.info(f"Stopped conversation session {self.session_id}")

    async def process_audio_chunk(self, audio_chunk: bytes):
        """Process incoming audio chunk."""
        if not self._is_active:
            return

        result = await self.vad_manager.process_audio(audio_chunk)

        # Return VAD state for client
        return {
            "state": result.state.value,
            "is_speech": result.is_speech,
            "should_interrupt": result.should_interrupt,
        }

    async def _on_user_speech_start(self):
        """Called when user starts speaking."""
        logger.debug("User speech started")

    async def _on_user_speech_end(self, audio: bytes):
        """Called when user finishes speaking with full audio."""
        logger.debug(f"User speech ended, {len(audio)} bytes")

        # Transcribe
        if self.stt_service:
            try:
                transcription = await self.stt_service.transcribe(audio)
                if self.on_transcription:
                    await self._safe_callback(self.on_transcription, transcription)

                # Generate response
                await self._generate_response(transcription)
            except Exception as e:
                logger.error(f"Transcription error: {e}")
                if self.on_error:
                    await self._safe_callback(self.on_error, str(e))

    async def _on_user_interruption(self):
        """Called when user interrupts the AI."""
        logger.debug("User interrupted")

        # Cancel current response
        if self._current_response_task:
            self._current_response_task.cancel()
            try:
                await self._current_response_task
            except asyncio.CancelledError:
                pass

        await self.vad_manager.set_ai_speaking(False)

    async def _generate_response(self, user_message: str):
        """Generate and stream AI response."""
        if not self.llm_service or not self.tts_service:
            return

        # Cancel any existing response
        if self._current_response_task:
            self._current_response_task.cancel()

        self._current_response_task = asyncio.create_task(
            self._response_task(user_message)
        )

    async def _response_task(self, user_message: str):
        """Task to generate response with streaming TTS."""
        try:
            await self.vad_manager.set_ai_speaking(True)

            if self.on_response_start:
                await self._safe_callback(self.on_response_start)

            # Stream LLM response
            full_text = ""
            sentence_buffer = ""

            async for chunk in self.llm_service.stream_response(user_message):
                full_text += chunk
                sentence_buffer += chunk

                # Check for sentence boundaries
                for punct in ['.', '!', '?', '\n']:
                    if punct in sentence_buffer:
                        sentences = sentence_buffer.split(punct)
                        for sentence in sentences[:-1]:
                            sentence = sentence.strip()
                            if sentence:
                                # Generate TTS for this sentence
                                audio = await self.tts_service.synthesize(sentence + punct)
                                if self.on_response_chunk:
                                    await self._safe_callback(
                                        self.on_response_chunk,
                                        sentence + punct,
                                        audio
                                    )
                        sentence_buffer = sentences[-1]

            # Handle remaining text
            if sentence_buffer.strip():
                audio = await self.tts_service.synthesize(sentence_buffer)
                if self.on_response_chunk:
                    await self._safe_callback(self.on_response_chunk, sentence_buffer, audio)

            if self.on_response_end:
                await self._safe_callback(self.on_response_end)

        except asyncio.CancelledError:
            logger.debug("Response cancelled due to interruption")
            raise
        except Exception as e:
            logger.error(f"Response generation error: {e}")
            if self.on_error:
                await self._safe_callback(self.on_error, str(e))
        finally:
            await self.vad_manager.set_ai_speaking(False)

    async def _safe_callback(self, callback: Callable, *args):
        """Safely execute a callback."""
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"Callback error: {e}")
