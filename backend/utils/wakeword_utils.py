"""
Utilities for wake-word detection.
"""
import logging
import shutil
import subprocess
from typing import Optional

import numpy as np  # type: ignore[attr-defined]

from config import config

logger = logging.getLogger(__name__)

WAKEWORD_MODEL = None
WAKEWORD_THRESHOLD = config.WAKEWORD_THRESHOLD
FFMPEG_PATH = shutil.which('ffmpeg')

try:  # pragma: no cover
    from openwakeword.model import Model as WakeWordModel  # type: ignore[attr-defined]
    from openwakeword.utils import download_models as download_wakeword_models  # type: ignore[attr-defined]
    WAKEWORD_AVAILABLE = True
except Exception as wakeword_error:  # pragma: no cover
    logger.warning("openWakeWord unavailable: %s", wakeword_error)
    WAKEWORD_AVAILABLE = False


def init_wakeword_model():
    """Initialise the hey_rhasspy wake-word model (download if needed)."""
    global WAKEWORD_MODEL
    if not WAKEWORD_AVAILABLE or WAKEWORD_MODEL is not None:
        return
    try:
        download_models_if_needed()
        WAKEWORD_MODEL = WakeWordModel(wakeword_models=["hey_rhasspy"])
        logger.info("openWakeWord model 'hey_rhasspy' loaded")
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to initialise openWakeWord model: %s", exc)
        WAKEWORD_MODEL = None


def download_models_if_needed():
    """Ensure wake-word models exist."""
    try:
        download_wakeword_models(model_names=["hey_rhasspy"])
    except Exception as exc:  # pragma: no cover
        logger.warning("Could not download wake-word models: %s", exc)


def decode_audio_to_pcm16(audio_bytes: bytes, sample_rate: int = 16000) -> Optional[np.ndarray]:
    """Convert encoded audio (webm/opus) to 16 kHz PCM using ffmpeg."""
    if not audio_bytes:
        return None
    if not FFMPEG_PATH:
        logger.warning("ffmpeg not found - wake-word detection disabled")
        return None
    try:
        process = subprocess.Popen(
            [
                FFMPEG_PATH,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                "pipe:0",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-f",
                "s16le",
                "pipe:1",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pcm_data, stderr = process.communicate(audio_bytes)
        if process.returncode != 0:
            if stderr:
                logger.warning("ffmpeg decode failed: %s", stderr.decode('utf-8', errors='ignore'))
            return None
        if not pcm_data:
            return None
        return np.frombuffer(pcm_data, dtype=np.int16)
    except Exception as exc:  # pragma: no cover
        logger.warning("ffmpeg conversion error: %s", exc)
        return None


init_wakeword_model()


