"""
Main Flask application for 3D Avatar Chat System
"""
import logging
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from config import Config
from routes.assistant_routes import assistant_bp
from routes.audio_routes import audio_bp
from routes.chat_routes import chat_bp
from services.audio_service import AudioService


def load_environment():
    """Load environment variables before importing other modules."""
    try:
        base_dir = os.path.dirname(__file__)
        backend_env = os.path.join(base_dir, '.env')
        root_env = os.path.join(base_dir, '..', '.env')

        if os.path.exists(backend_env):
            load_dotenv(backend_env)
        elif os.path.exists(root_env):
            load_dotenv(root_env)
        else:
            logging.warning("No .env file found. Using system environment variables.")
    except PermissionError as exc:
        logging.warning(
            "Could not read .env file due to permission error: %s. "
            "Continuing with existing environment variables.",
            exc,
        )
    except Exception as exc:
        logging.warning(
            "Unexpected error while loading .env: %s. "
            "Continuing with existing environment variables.",
            exc,
        )


# Load environment first
load_environment()

# Import config to initialize singleton
from config import config

# Configure logging with rotation
from utils.log_config import setup_logging, get_logger

setup_logging(log_level=config.LOG_LEVEL)
logger = get_logger(__name__)
logger.info("app.py module loaded with LOG_LEVEL=%s", config.LOG_LEVEL)

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Register blueprints
app.register_blueprint(assistant_bp, url_prefix='/api')
app.register_blueprint(audio_bp, url_prefix='/api')
app.register_blueprint(chat_bp, url_prefix='/api/chats')


# ============ Health Check Endpoints ============

@app.route('/')
def index():
    """Root endpoint"""
    return "Rhasspy AI Avatar Backend"


@app.route('/api/status')
def status():
    """API status check"""
    return jsonify({'status': 'ok', 'message': 'Rhasspy backend is running'})


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    config = Config.get_instance()
    return jsonify({
        'status': 'healthy',
        'llm_provider': 'openai',
        'audio_available': bool(config.OPENAI_API_KEY),
        'api_key_configured': bool(config.OPENAI_API_KEY)
    }), 200


# ============ Diagnostic Endpoints ============

@app.route('/api/text-to-speech', methods=['POST'])
def text_to_speech_endpoint():
    """Diagnostic endpoint to convert text to speech and return base64 audio."""
    try:
        payload = request.json or {}
        text = payload.get('text', '')
        voice = payload.get('voice')

        if not text:
            return jsonify({'error': 'Text is required'}), 400

        audio_service = AudioService()
        audio_data = audio_service.text_to_speech(text, voice=voice)
        logger.info(
            "Diagnostic TTS generated audio (length=%d, voice=%s)",
            len(audio_data) if audio_data else 0,
            voice or audio_service.default_voice,
        )

        return jsonify({
            'audio': audio_data,
            'audio_length': len(audio_data) if audio_data else 0,
            'voice': voice or audio_service.default_voice,
        }), 200
    except Exception as exc:
        logger.exception("Diagnostic TTS failed")
        return jsonify({'error': str(exc)}), 500


@app.route('/api/speech-to-text', methods=['POST'])
def speech_to_text_endpoint():
    """Diagnostic endpoint to convert uploaded audio to text using Whisper."""
    try:
        if 'audio' not in request.files:
            return jsonify({'error': 'Audio file is required'}), 400

        audio_file = request.files['audio']
        audio_bytes = audio_file.read()

        if not audio_bytes:
            return jsonify({'error': 'Empty audio file'}), 400

        audio_service = AudioService()
        transcript = audio_service.speech_to_text(audio_bytes)
        logger.info(
            "Diagnostic STT produced transcript (chars=%d)",
            len(transcript) if transcript else 0,
        )

        return jsonify({
            'text': transcript or '',
            'length': len(transcript) if transcript else 0,
        }), 200
    except Exception as exc:
        logger.exception("Diagnostic STT failed")
        return jsonify({'error': str(exc)}), 500


if __name__ == '__main__':
    # Disable Flask's automatic .env loading since we handle it above
    app.config['ENV'] = 'development'
    app.run(debug=True, host='0.0.0.0', port=5000, load_dotenv=False)
