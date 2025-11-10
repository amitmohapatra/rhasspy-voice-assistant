"""
Audio service for speech-to-text and text-to-speech using OpenAI APIs
Enterprise-grade with comprehensive logging and error handling
"""
import base64
import io
import logging
import re
import time
import traceback
from typing import Optional

from openai import OpenAI, RateLimitError

from config import Config

logger = logging.getLogger(__name__)


class AudioService:
    """
    Singleton service for audio processing using OpenAI APIs
    Provides STT (Speech-to-Text) and TTS (Text-to-Speech) functionality
    """
    _instance: Optional['AudioService'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AudioService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            config = Config.get_instance()
            self.openai_api_key = config.OPENAI_API_KEY
            self.default_voice = getattr(config, 'TTS_VOICE', 'nova')
            self.tts_model = getattr(config, 'TTS_MODEL', 'tts-1')
            self.stt_model = getattr(config, 'STT_MODEL', 'whisper-1')
            self.stt_prompts = getattr(config, 'STT_PROMPTS', {})
            self._initialized = True
            logger.info(
                "AudioService initialized - stt_model: %s, tts_model: %s, voice: %s, prompts_loaded: %d, api_key_configured: %s",
                self.stt_model,
                self.tts_model,
                self.default_voice,
                len(self.stt_prompts),
                bool(self.openai_api_key)
            )
    
    def speech_to_text(self, audio_file, language: str = "en-IN") -> str:
        """
        Convert speech to text using OpenAI Whisper API
        
        Args:
            audio_file: Audio file bytes or file-like object
            language: Language code (e.g., 'en-IN', 'hi', 'en', 'fr')
            
        Returns:
            Transcribed text string
            
        Raises:
            ValueError: If API key is not configured
            Exception: For API errors (rate limit, quota, etc.)
        """
        if not self.openai_api_key:
            logger.error("STT attempted without API key")
            raise ValueError("OPENAI_API_KEY is required for speech-to-text features")
        
        start_time = time.time()
        audio_size = 0
        
        try:
            client = OpenAI(api_key=self.openai_api_key)
            
            # Convert FileStorage to bytes if needed
            if hasattr(audio_file, 'read'):
                audio_file.seek(0)
                audio_bytes = audio_file.read()
            else:
                audio_bytes = audio_file
            
            audio_size = len(audio_bytes)
            logger.debug("STT processing audio: %d bytes, language: %s", audio_size, language)
            
            # Skip if audio is too small (likely silence)
            if audio_size < 3000:  # Less than 3KB is likely empty/silence
                logger.debug("Audio too small (%d bytes), likely silence - skipping STT", audio_size)
                return ""
            
            # Create a BytesIO object for OpenAI API
            audio_io = io.BytesIO(audio_bytes)
            audio_io.name = 'audio.webm'  # Set filename for API
            
            # Extract base language code (e.g., 'en-IN' -> 'en')
            base_language = language.split('-')[0] if language else 'en'
            
            # Get prompt for the language (improves accuracy and reduces hallucinations)
            prompt = self.stt_prompts.get(language) or self.stt_prompts.get(base_language, "")
            
            logger.debug(
                "Calling Whisper API - language: %s, base: %s, prompt_length: %d",
                language,
                base_language,
                len(prompt)
            )
            
            # Call Whisper API with language and prompt
            transcript = client.audio.transcriptions.create(
                model=self.stt_model,
                file=audio_io,
                language=base_language,  # Use base language (en, hi, fr, etc.)
                prompt=prompt if prompt else None,  # Context prompt to improve accuracy
                temperature=0  # Reduce hallucinations - stick to actual speech
            )
            
            result = transcript.text.strip()
            duration = time.time() - start_time
            
            logger.info(
                "STT completed - audio: %d bytes, language: %s, prompt: %s, text: %d chars, duration: %.2fs, preview: '%s'",
                audio_size,
                language,
                "yes" if prompt else "no",
                len(result),
                duration,
                result[:50] if result else "(empty)"
            )
            
            return result
            
        except RateLimitError as e:
            duration = time.time() - start_time
            logger.error(
                "STT rate limit error - audio: %d bytes, duration: %.2fs, error: %s",
                audio_size,
                duration,
                str(e),
                exc_info=True,
                extra={
                    'error_type': 'RateLimitError',
                    'audio_size': audio_size,
                    'duration': duration,
                    'stack_trace': traceback.format_exc()
                }
            )
            
            # Handle rate limit errors gracefully
            wait_time = 5  # Default wait time
            error_msg = str(e)
            if "try again in" in error_msg:
                # Extract wait time from error message
                match = re.search(r'try again in (\d+)s', error_msg)
                if match:
                    wait_time = min(int(match.group(1)), 10)  # Cap at 10 seconds
            
            raise Exception(f"Rate limit reached. Please wait {wait_time} seconds before trying again.")
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            logger.error(
                "STT failed - audio: %d bytes, duration: %.2fs, error: %s",
                audio_size,
                duration,
                error_msg,
                exc_info=True,
                extra={
                    'error_type': type(e).__name__,
                    'audio_size': audio_size,
                    'duration': duration,
                    'stack_trace': traceback.format_exc()
                }
            )
            
            # Provide helpful error messages
            if "quota" in error_msg.lower():
                raise Exception("OpenAI quota exceeded. Please check your billing at https://platform.openai.com/account/billing")
            
            raise Exception(f"Speech-to-text error: {error_msg}")
    
    def text_to_speech(self, text: str, voice: str = None) -> str:
        """
        Convert text to speech using OpenAI TTS API
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (nova, alloy, echo, fable, onyx, shimmer)
        
        Returns:
            Base64 encoded audio data (MP3 format)
            
        Raises:
            ValueError: If API key is not configured or text is empty
            Exception: For API errors
        """
        if not self.openai_api_key:
            logger.error("TTS attempted without API key")
            raise ValueError("OPENAI_API_KEY is required for text-to-speech features")
        
        if not text or not text.strip():
            logger.warning("TTS called with empty text")
            raise ValueError("Text cannot be empty for text-to-speech")
        
        start_time = time.time()
        text_length = len(text)
        voice_to_use = voice or self.default_voice
        
        try:
            client = OpenAI(api_key=self.openai_api_key)
            
            logger.debug(
                "TTS processing - text: %d chars, voice: %s, preview: '%s'",
                text_length,
                voice_to_use,
                text[:50]
            )
            
            # Call TTS API
            response = client.audio.speech.create(
                model=self.tts_model,  # Configurable TTS model
                voice=voice_to_use,
                input=text,
                speed=1.5  # Normal speed (can adjust 0.25 to 4.0)
            )
            
            audio_bytes = response.content
            audio_size = len(audio_bytes)
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
            duration = time.time() - start_time
            
            logger.info(
                "TTS completed - text: %d chars, audio: %d bytes, voice: %s, duration: %.2fs",
                text_length,
                audio_size,
                voice_to_use,
                duration
            )
            
            return audio_base64
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            logger.error(
                "TTS failed - text: %d chars, voice: %s, duration: %.2fs, error: %s",
                text_length,
                voice_to_use,
                duration,
                error_msg,
                exc_info=True,
                extra={
                    'error_type': type(e).__name__,
                    'text_length': text_length,
                    'text_preview': text[:100],
                    'voice': voice_to_use,
                    'duration': duration,
                    'stack_trace': traceback.format_exc()
                }
            )
            
            # Provide helpful error messages
            if "quota" in error_msg.lower():
                raise Exception("OpenAI quota exceeded. Please check your billing at https://platform.openai.com/account/billing")
            
            raise Exception(f"Text-to-speech error: {error_msg}")
    
    @classmethod
    def get_instance(cls) -> 'AudioService':
        """Get singleton instance"""
        return cls()
