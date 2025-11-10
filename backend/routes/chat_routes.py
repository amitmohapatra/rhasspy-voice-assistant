"""
Chat routes for conversation handling
Clean, DRY code using common utilities
"""
import logging

from flask import Blueprint, Response, jsonify, request

from services.assistant_service import AssistantService
from services.audio_service import AudioService
from services.emotion_service import EmotionService
from utils.logging_utils import handle_error, log_request, log_response
from utils.streaming_utils import generate_streaming_response, validate_chat_request

logger = logging.getLogger(__name__)

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/greeting', methods=['POST'])
def greeting():
    """
    Handle initial greeting with SSE streaming (consistent with conversation flow)
    
    Input (JSON): {"message": "greeting text", "assistant_id": "..."}
    Output: Server-Sent Events stream with thread_id, text, and audio chunks
    """
    endpoint = '/api/chats/greeting'
    
    try:
        data = request.json or {}
        greeting_message = data.get('message', 'Namaste! I am Rhasspy, your AI assistant. How can I help you today?')
        assistant_id = data.get('assistant_id') or None
        
        log_request(
            endpoint,
            message_preview=greeting_message[:50],
            assistant_id=assistant_id
        )
        
        # Initialize assistant service and prepare conversation context
        assistant_service = AssistantService()
        assistant_id, thread_id, _ = assistant_service.prepare_conversation(
            assistant_id=assistant_id,
            thread_id=None,
            force_new_thread=True
        )
        logger.info("🎯 Greeting context - assistant_id=%s, thread_id=%s", assistant_id, thread_id)
        
        # Use streaming generator for greeting (same as conversation flow)
        # This will generate TTS and stream it back
        return Response(
            generate_streaming_response(
                greeting_message, 
                thread_id, 
                assistant_id, 
                "greeting",
                is_greeting=True  # Flag to indicate this is a greeting (no assistant API call)
            ),
            mimetype='text/event-stream'
        )
        
    except Exception as e:
        return handle_error(endpoint, e, "Greeting endpoint")


@chat_bp.route('', methods=['POST'])
def chat_text():
    """
    Text-only chat endpoint with streaming
    
    Input (JSON): {"message": "text", "thread_id": "...", "assistant_id": "..."}
    Output: Server-Sent Events stream with text and audio chunks
    """
    endpoint = '/api/chats'
    
    try:
        data = request.json or {}
        
        # Validate request
        error_response, status_code = validate_chat_request(data, require_message=True)
        if error_response:
            return error_response, status_code
        
        user_input = data.get('message', '').strip()
        thread_id = data.get('thread_id') or None
        assistant_id = data.get('assistant_id') or None
        
        assistant_service = AssistantService()
        assistant_id, thread_id, thread_created = assistant_service.prepare_conversation(
            assistant_id=assistant_id,
            thread_id=thread_id
        )
        logger.info(
            "🎯 Text chat context resolved: assistant_id=%s, thread_id=%s (thread_created=%s)",
            assistant_id,
            thread_id,
            thread_created
        )
        
        log_request(
            endpoint,
            message_preview=user_input[:50],
            message_length=len(user_input),
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        
        # Use common streaming generator
        return Response(
            generate_streaming_response(user_input, thread_id, assistant_id, "text_chat"),
            mimetype='text/event-stream'
        )
        
    except Exception as e:
        return handle_error(endpoint, e, "Text chat initialization")

