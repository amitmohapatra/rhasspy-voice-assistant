"""
Common streaming utilities for chat endpoints
"""
import json
import logging
from typing import Generator

from services.assistant_service import AssistantService
from services.audio_service import AudioService
from services.emotion_service import EmotionService
from utils.logging_utils import log_stream_error
from utils.text_filters import filter_unwanted_phrases

logger = logging.getLogger(__name__)


def generate_streaming_response(
    user_input: str,
    thread_id: str,
    assistant_id: str,
    context: str = "chat",
    is_greeting: bool = False
) -> Generator[str, None, None]:
    """
    Generate assistant streaming response with text and audio chunks
    
    Args:
        user_input: User's message text
        thread_id: Conversation thread ID
        assistant_id: Assistant ID
        context: Context for logging (e.g., "text_chat", "audio_chat", "greeting")
        is_greeting: If True, skip assistant API call and just generate TTS for the greeting text
        
    Yields:
        SSE formatted data strings
    """
    # Initialize services
    assistant_service = AssistantService()
    audio_service = AudioService()
    emotion_service = EmotionService()
    
    if assistant_id:
        assistant_service.assistant_id = assistant_id
        yield f"data: {json.dumps({'type': 'assistant_id', 'assistant_id': assistant_id})}\n\n"
    
    # State tracking
    accumulated_text = ""
    current_thread_id = thread_id
    chunk_count = 0
    sentence_buffer = ""
    audio_chunk_count = 0
    
    try:
        logger.info("Starting streaming response for %s (is_greeting=%s)", context, is_greeting)
        
        # Send thread_id immediately
        if thread_id:
            yield f"data: {json.dumps({'type': 'thread_id', 'thread_id': thread_id})}\n\n"
        
        # For greetings, skip assistant API call and just stream the greeting text + TTS
        if is_greeting:
            logger.info("Greeting mode: streaming pre-defined message with TTS")
            
            # Stream the greeting text
            yield f"data: {json.dumps({'type': 'text', 'text': user_input})}\n\n"
            accumulated_text = user_input
            
            # Generate and stream TTS audio for the greeting
            try:
                logger.debug("Generating TTS for greeting: %d chars", len(user_input))
                audio_data = audio_service.text_to_speech(user_input)
                if audio_data:
                    audio_chunk_count += 1
                    yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': audio_data, 'text': user_input})}\n\n"
                    logger.info("Greeting TTS generated: %d bytes", len(audio_data))
                else:
                    logger.warning("No audio generated for greeting")
            except Exception as tts_error:
                logger.error("TTS generation failed for greeting: %s", str(tts_error), exc_info=True)
                error_chunk = log_stream_error(tts_error, "greeting TTS generation")
                yield f"data: {json.dumps(error_chunk)}\n\n"
            
            # Send done event
            yield f"data: {json.dumps({'type': 'done', 'total_chunks': 1, 'audio_chunks': audio_chunk_count})}\n\n"
            logger.info("Greeting stream complete: 1 text chunk, %d audio chunks", audio_chunk_count)
            return
        
        # Normal conversation flow - call assistant API
        for chunk in assistant_service.chat_with_assistant_stream(
            message=user_input,
            thread_id=thread_id,
            assistant_id=assistant_id
        ):
            chunk_count += 1
            
            if chunk['type'] == 'thread_id':
                current_thread_id = chunk['thread_id']
                logger.debug("Thread ID: %s", current_thread_id)
                yield f"data: {json.dumps(chunk)}\n\n"
            
            elif chunk['type'] == 'text':
                text_delta = chunk['text']
                accumulated_text += text_delta
                sentence_buffer += text_delta
                
                logger.debug("Text chunk #%d: %s", chunk_count, text_delta[:30])
                yield f"data: {json.dumps(chunk)}\n\n"
                
                if any(sentence_buffer.rstrip().endswith(p) for p in ['.', '!', '?', '\n']):
                    sentence = sentence_buffer.strip()
                    if len(sentence) > 3:
                        logger.debug("Generating TTS for sentence: %s", sentence[:50])
                        try:
                            audio_data = audio_service.text_to_speech(sentence)
                            audio_chunk_count += 1
                            audio_chunk = {
                                'type': 'audio_chunk',
                                'audio': audio_data,
                                'text': sentence
                            }
                            logger.debug("Audio chunk #%d generated: %d bytes", audio_chunk_count, len(audio_data))
                            yield f"data: {json.dumps(audio_chunk)}\n\n"
                        except Exception as tts_error:
                            logger.error("TTS failed for sentence: %s", str(tts_error), exc_info=True)
                    sentence_buffer = ""
            
            elif chunk['type'] == 'done':
                logger.info("Stream complete, processing final chunks")
                
                if sentence_buffer.strip():
                    sentence = sentence_buffer.strip()
                    if len(sentence) > 3:
                        logger.debug("Generating TTS for final sentence: %s", sentence[:50])
                        try:
                            audio_data = audio_service.text_to_speech(sentence)
                            audio_chunk_count += 1
                            audio_chunk = {
                                'type': 'audio_chunk',
                                'audio': audio_data,
                                'text': sentence
                            }
                            logger.debug("Final audio chunk generated: %d bytes", len(audio_data))
                            yield f"data: {json.dumps(audio_chunk)}\n\n"
                        except Exception as tts_error:
                            logger.error("TTS failed for final sentence: %s", str(tts_error), exc_info=True)
                sentence_buffer = ""
                
                # Analyze emotion for complete response
                logger.debug("Analyzing emotion for complete response")
                try:
                    filtered_text = filter_unwanted_phrases(accumulated_text)
                    emotion = emotion_service.analyze_emotion(filtered_text)
                    logger.debug("Emotion analysis: %s", emotion)
                except Exception as emotion_error:
                    logger.warning("Emotion analysis failed: %s", str(emotion_error))
                    emotion = {'emotion': 'neutral', 'intensity': 0.5}
                
                final_chunk = {
                    'type': 'done',
                    'thread_id': current_thread_id,
                    'assistant_id': assistant_id,
                    'emotion': emotion,
                    'full_text': filtered_text
                }
                yield f"data: {json.dumps(final_chunk)}\n\n"
                
                logger.info(
                    "%s stream completed - text_chunks: %d, audio_chunks: %d, chars: %d",
                    context,
                    chunk_count,
                    audio_chunk_count,
                    len(accumulated_text)
                )
            
            elif chunk['type'] == 'error':
                logger.error("Stream error chunk received: %s", chunk.get('error'))
                yield f"data: {json.dumps(chunk)}\n\n"
                break
    
    except Exception as e:
        error_chunk = log_stream_error(
            e,
            f"{context} streaming",
            accumulated_text_length=len(accumulated_text),
            chunk_count=chunk_count,
            audio_chunk_count=audio_chunk_count
        )
        yield f"data: {json.dumps(error_chunk)}\n\n"


def validate_chat_request(
    data: dict,
    require_message: bool = True,
    require_thread: bool = False,
    require_assistant: bool = False
) -> tuple:
    """
    Validate common chat request parameters
    
    Args:
        data: Request data dictionary
        require_message: Whether to require message field
        
    Returns:
        Tuple of (error_response, status_code) or (None, None) if valid
    """
    from flask import jsonify
    
    if require_message:
        message = data.get('message', '').strip()
        if not message:
            logger.warning("Empty or missing message in request")
            return jsonify({'error': 'Message is required and cannot be empty'}), 400
    
    thread_id = data.get('thread_id')
    if require_thread and not thread_id:
        logger.warning("Missing thread_id in request")
        return jsonify({'error': 'thread_id is required'}), 400
    
    assistant_id = data.get('assistant_id')
    if require_assistant and not assistant_id:
        logger.warning("Missing assistant_id in request")
        return jsonify({'error': 'assistant_id is required'}), 400
    
    return None, None


def validate_audio_request(
    files: dict,
    form: dict,
    require_thread: bool = False,
    require_assistant: bool = False
) -> tuple:
    """
    Validate audio request parameters
    
    Args:
        files: Request files dictionary
        form: Request form dictionary
        
    Returns:
        Tuple of (error_response, status_code, audio_bytes) or (None, None, audio_bytes) if valid
    """
    from flask import jsonify
    
    # Validate audio file
    audio_file = files.get('audio')
    if not audio_file:
        logger.warning("No audio file in request")
        return jsonify({'error': 'Audio file is required'}), 400, None
    
    if not audio_file or audio_file.filename == '':
        logger.warning("Empty audio file in request")
        return jsonify({'error': 'Audio file is empty'}), 400, None
    
    # Read audio bytes
    audio_bytes = audio_file.read()
    if not audio_bytes:
        logger.warning("Empty audio file content")
        return jsonify({'error': 'Empty audio file'}), 400, None
    
    # Validate thread_id and assistant_id
    thread_id = form.get('thread_id')
    if require_thread and not thread_id:
        logger.warning("Missing thread_id in audio request")
        return jsonify({'error': 'thread_id is required'}), 400, None
    
    assistant_id = form.get('assistant_id')
    if require_assistant and not assistant_id:
        logger.warning("Missing assistant_id in audio request")
        return jsonify({'error': 'assistant_id is required'}), 400, None
    
    return None, None, audio_bytes

