"""
Audio routes for voice interactions
Clean, DRY code using common utilities
"""
import json
import logging

from flask import Blueprint, Response, jsonify, request

from services.audio_service import AudioService
from services.assistant_service import AssistantService
from utils.logging_utils import handle_error, log_request, log_response, log_stream_error
from utils.streaming_utils import generate_streaming_response, validate_audio_request
from utils.wakeword_utils import (
    WAKEWORD_MODEL,
    WAKEWORD_THRESHOLD,
    decode_audio_to_pcm16,
)

logger = logging.getLogger(__name__)

audio_bp = Blueprint('audio', __name__)


@audio_bp.route('/audio', methods=['POST'])
def process_audio_chat():
    """
    Audio chat endpoint - STT → Assistant → TTS streaming pipeline
    
    Input (multipart): audio file + thread_id + assistant_id
    Output: Server-Sent Events stream with transcription, assistant text, and audio chunks
    """
    endpoint = '/api/audio'
    
    logger.info("=" * 80)
    logger.info("🎤 [AUDIO ENDPOINT] Request received")
    logger.info("=" * 80)
    
    try:
        logger.info("📋 Request details: method=%s, content_type=%s", request.method, request.content_type)
        logger.info("📋 Form data keys: %s", list(request.form.keys()))
        logger.info("📋 Files keys: %s", list(request.files.keys()))
        
        error_response, status_code, audio_bytes = validate_audio_request(request.files, request.form)
        if error_response:
            logger.error("❌ Validation failed: %s", error_response)
            return error_response, status_code
        
        raw_thread_id = request.form.get('thread_id') or None
        raw_assistant_id = request.form.get('assistant_id') or None
        language = request.form.get('language', 'en-IN')  # Default to Indian English
        audio_file = request.files.get('audio')
        audio_filename = audio_file.filename if audio_file else 'unknown'
        
        logger.info("✅ Validation passed: audio_size=%d, language=%s, incoming_thread_id=%s, incoming_assistant_id=%s", 
                   len(audio_bytes), language, raw_thread_id, raw_assistant_id)
        
        assistant_service = AssistantService()
        assistant_id, thread_id, thread_created = assistant_service.prepare_conversation(
            assistant_id=raw_assistant_id,
            thread_id=raw_thread_id
        )
        
        logger.info(
            "🎯 Conversation context resolved: assistant_id=%s, thread_id=%s (thread_created=%s)",
            assistant_id,
            thread_id,
            thread_created
        )
        
        log_request(
            endpoint,
            audio_size=len(audio_bytes),
            audio_file_name=audio_filename,
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        
        audio_service = AudioService()
        
        def stream_audio_chat():
            try:
                logger.info("Starting STT for audio input (%d bytes, language: %s)", len(audio_bytes), language)
                try:
                    user_input = audio_service.speech_to_text(audio_bytes, language=language)
                    logger.info(
                        "STT completed - language: %s, preview: '%s' (%d chars)",
                        language,
                        user_input[:80] if user_input else "",
                        len(user_input) if user_input else 0
                    )
                    
                    if not user_input or len(user_input.strip()) < 3:
                        logger.warning("STT produced insufficient text: '%s'", user_input)
                        error_chunk = {'type': 'error', 'error': 'No speech detected or text too short'}
                        yield f"data: {json.dumps(error_chunk)}\n\n"
                        return
                    
                    yield f"data: {json.dumps({'type': 'input_text', 'text': user_input})}\n\n"
                except Exception as stt_error:
                    error_chunk = log_stream_error(
                        stt_error,
                        "Speech-to-text processing",
                        audio_size=len(audio_bytes)
                    )
                    yield f"data: {json.dumps(error_chunk)}\n\n"
                    return
                
                logger.info("Starting assistant streaming for audio chat turn")
                for chunk in generate_streaming_response(user_input, thread_id, assistant_id, "audio_chat"):
                    yield chunk
            
            except Exception as pipeline_error:
                error_chunk = log_stream_error(pipeline_error, "audio chat pipeline")
                yield f"data: {json.dumps(error_chunk)}\n\n"
        
        return Response(stream_audio_chat(), mimetype='text/event-stream')
    
    except Exception as exc:
        return handle_error(endpoint, exc, "Audio chat processing")


@audio_bp.route('/audio/wake-word', methods=['POST'])
def detect_wake_word():
    """
    Detect wake word using openWakeWord model
    
    Input: Multipart audio file
    Output: JSON with wake_word_detected, wake_word_score, wake_word_available
    """
    endpoint = '/api/audio/wake-word'
    
    try:
        # Validate audio file presence
        if 'audio' not in request.files:
            logger.warning("No audio file in wake word request")
            return jsonify({'error': 'Audio file is required'}), 400

        audio_file = request.files['audio']
        
        if not audio_file or audio_file.filename == '':
            logger.warning("Empty audio file in wake word request")
            return jsonify({'error': 'Audio file is empty'}), 400

        # Read audio bytes
        audio_file.seek(0)
        audio_bytes = audio_file.read()
        audio_size = len(audio_bytes)
        
        log_request(
            endpoint,
            audio_size=audio_size,
            audio_file_name=audio_file.filename
        )
        
        # Check if wake word model is available
        if not WAKEWORD_MODEL:
            logger.warning("Wake-word model not available")
            response_data = {
                'wake_word_detected': False,
                'wake_word_score': 0.0,
                'wake_word_available': False,
                'message': 'Wake-word model unavailable'
            }
            log_response(endpoint, 200, **response_data)
            return jsonify(response_data), 200

        # Decode audio to PCM16 format
        logger.debug("Decoding audio to PCM16 (%d bytes)", audio_size)
        try:
            pcm = decode_audio_to_pcm16(audio_bytes)
            logger.debug("PCM decoded: %s samples", pcm.size if pcm is not None else 0)
        except Exception as decode_error:
            logger.error(
                "Audio decoding failed: %s",
                str(decode_error),
                exc_info=True,
                extra={
                    'audio_size': audio_size,
                    'error_type': type(decode_error).__name__
                }
            )
            return handle_error(endpoint, decode_error, "Audio decoding")
        
        # Perform wake word detection
        wake_score = 0.0
        wake_detected = False
        
        if pcm is not None and pcm.size > 0:
            logger.debug("Running wake word prediction on %d samples", pcm.size)
            try:
                prediction = WAKEWORD_MODEL.predict(pcm)
                wake_score = float(prediction.get("hey_rhasspy", 0.0))
                wake_detected = wake_score >= WAKEWORD_THRESHOLD
                
                logger.info(
                    "Wake-word detection: score=%.3f, threshold=%.2f, detected=%s",
                    wake_score,
                    WAKEWORD_THRESHOLD,
                    wake_detected
                )
            except Exception as predict_error:
                logger.error(
                    "Wake word prediction failed: %s",
                    str(predict_error),
                    exc_info=True,
                    extra={
                        'pcm_size': pcm.size,
                        'error_type': type(predict_error).__name__
                    }
                )
                return handle_error(endpoint, predict_error, "Wake word prediction")
        else:
            logger.warning(
                "Wake-word PCM conversion failed or empty; skipping detection (audio_size=%d)",
                audio_size
            )

        response_data = {
            'wake_word_detected': wake_detected,
            'wake_word_score': wake_score,
            'wake_word_available': True
        }
        
        log_response(endpoint, 200, **response_data)
        return jsonify(response_data), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Wake word detection")
