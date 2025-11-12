"""
Configuration settings using singleton pattern
All environment variables are loaded here and accessed through Config singleton
"""
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class Config:
    """
    Singleton configuration class for application settings
    All os.getenv calls should be centralized here
    """
    _instance: Optional['Config'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            # OpenAI API Key (required for all AI features)
            self.OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
            self.OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL', '').strip() or None
            
            # Logging Level
            self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
            
            # Wake Word Detection Threshold (0.0 to 1.0)
            self.WAKEWORD_THRESHOLD = float(os.getenv('WAKEWORD_THRESHOLD', '0.5'))
            
            # Load defaults from JSON configuration (if present)
            defaults_path = os.path.join(os.path.dirname(__file__), 'defaults.json')
            self.DEFAULT_ASSISTANT_NAME = 'Rhasspy Assistant'
            self.DEFAULT_ASSISTANT_INSTRUCTIONS = 'You are Rhasspy, a helpful AI assistant.'
            self.DEFAULT_ASSISTANT_MODEL = 'gpt-4o-mini'
            self.DEFAULT_STT_MODEL = 'whisper-1'
            self.DEFAULT_TTS_MODEL = 'tts-1'
            self.DEFAULT_TTS_VOICE = 'nova'
            self.STT_PROMPTS = {}
            
            if os.path.exists(defaults_path):
                try:
                    with open(defaults_path, 'r', encoding='utf-8') as defaults_file:
                        defaults_data = json.load(defaults_file)
                        assistant_defaults = defaults_data.get('default_assistant', {})
                        self.DEFAULT_ASSISTANT_NAME = assistant_defaults.get('name', self.DEFAULT_ASSISTANT_NAME)
                        self.DEFAULT_ASSISTANT_INSTRUCTIONS = assistant_defaults.get('instructions', self.DEFAULT_ASSISTANT_INSTRUCTIONS)
                        self.DEFAULT_ASSISTANT_MODEL = assistant_defaults.get('model', self.DEFAULT_ASSISTANT_MODEL)
                        
                        audio_defaults = defaults_data.get('audio', {})
                        self.DEFAULT_STT_MODEL = audio_defaults.get('stt_model', self.DEFAULT_STT_MODEL)
                        self.DEFAULT_TTS_MODEL = audio_defaults.get('tts_model', self.DEFAULT_TTS_MODEL)
                        self.DEFAULT_TTS_VOICE = audio_defaults.get('voice', self.DEFAULT_TTS_VOICE)
                        self.STT_PROMPTS = audio_defaults.get('stt_prompts', {})
                except Exception as exc:
                    logger.warning("Failed to load defaults.json: %s. Falling back to hard-coded defaults.", exc)
            
            # Allow environment variables to override defaults
            self.TTS_VOICE = os.getenv('TTS_VOICE', self.DEFAULT_TTS_VOICE)
            self.TTS_MODEL = os.getenv('TTS_MODEL', self.DEFAULT_TTS_MODEL)
            self.STT_MODEL = os.getenv('STT_MODEL', self.DEFAULT_STT_MODEL)
            
            self._initialized = True
            
            # Log configuration on initialization
            logger.info(
                "Config initialized - api_key_configured: %s, stt_model: %s, tts_model: %s, tts_voice: %s, log_level: %s, wakeword_threshold: %.2f",
                bool(self.OPENAI_API_KEY),
                self.STT_MODEL,
                self.TTS_MODEL,
                self.TTS_VOICE,
                self.LOG_LEVEL,
                self.WAKEWORD_THRESHOLD
            )
    
    @classmethod
    def get_instance(cls) -> 'Config':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


# Initialize global singleton instance on module import
config = Config.get_instance()
