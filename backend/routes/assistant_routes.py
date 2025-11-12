"""
Assistant API Routes
Enterprise-grade with comprehensive logging and error handling
Handles assistant, vector store, thread, and file management
"""
import logging
import os
import tempfile

from flask import Blueprint, jsonify, request

from services.assistant_service import AssistantService
from utils.logging_utils import handle_error, log_request, log_response

logger = logging.getLogger(__name__)

assistant_bp = Blueprint('assistant', __name__)


def get_assistant_service():
    """Lazy initialization of AssistantService"""
    if not hasattr(get_assistant_service, '_instance'):
        get_assistant_service._instance = AssistantService()
    return get_assistant_service._instance


# ============ Assistant Management ============

@assistant_bp.route('/assistants', methods=['POST'])
def create_assistant():
    """Create a new assistant"""
    endpoint = '/api/assistants'
    
    try:
        data = request.json or {}
        
        # OpenAI API limitation: Only 1 vector store per assistant is allowed
        vector_store_ids = data.get('vector_store_ids', [])
        if vector_store_ids and len(vector_store_ids) > 1:
            return jsonify({
                "error": "OpenAI API only allows 1 vector store per assistant. Please select only 1 knowledge base."
            }), 400
        
        name = data.get('name', 'Rhasspy Assistant')
        instructions = data.get('instructions', 'You are Rhasspy, a helpful AI assistant.')
        model = data.get('model', 'gpt-4-turbo-preview')
        
        log_request(endpoint, assistant_name=name, model=model)
        
        reasoning_effort = data.get('reasoning_effort')
        if isinstance(reasoning_effort, str) and reasoning_effort.lower() == 'auto':
            reasoning_effort = None

        result = get_assistant_service().create_assistant(
            name=name,
            instructions=instructions,
            model=model,
            tools=data.get('tools'),
            vector_store_ids=vector_store_ids,
            reasoning_effort=reasoning_effort
        )
        
        log_response(endpoint, 201, assistant_id=result.get('id'))
        return jsonify(result), 201
        
    except Exception as e:
        return handle_error(endpoint, e, "Create assistant")


@assistant_bp.route('/assistants/<assistant_id>', methods=['GET'])
def get_assistant(assistant_id):
    """Get assistant details"""
    endpoint = f'/api/assistants/{assistant_id}'
    
    try:
        log_request(endpoint, assistant_id=assistant_id)
        
        result = get_assistant_service().get_assistant(assistant_id)
        
        log_response(endpoint, 200, assistant_name=result.get('name'))
        return jsonify(result), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Get assistant")


@assistant_bp.route('/assistants', methods=['GET'])
def list_assistants():
    """List all assistants"""
    endpoint = '/api/assistants'
    
    try:
        limit = request.args.get('limit', 20, type=int)
        
        log_request(endpoint, limit=limit)
        
        result = get_assistant_service().list_assistants(limit)
        
        log_response(endpoint, 200, count=len(result) if isinstance(result, list) else 0)
        return jsonify(result), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "List assistants")


@assistant_bp.route('/assistants/<assistant_id>', methods=['PUT'])
def update_assistant(assistant_id):
    """Update assistant configuration"""
    endpoint = f'/api/assistants/{assistant_id}'
    
    try:
        data = request.json or {}
        
        logger.info(f"UPDATE ASSISTANT REQUEST - ID: {assistant_id}, Data: {data}")
        log_request(endpoint, assistant_id=assistant_id, updates=list(data.keys()))

        # Check if reasoning_effort was explicitly provided in the request
        reasoning_effort_sentinel = object()
        reasoning_effort = data.get('reasoning_effort', reasoning_effort_sentinel)
        reasoning_effort_provided = reasoning_effort is not reasoning_effort_sentinel
        
        # Convert 'auto' string or None to None (which means omit the field for OpenAI API)
        if reasoning_effort_provided:
            if isinstance(reasoning_effort, str) and reasoning_effort.lower() == 'auto':
                reasoning_effort = None
            # Also handle explicit null from frontend
            if reasoning_effort is None or reasoning_effort == 'null' or reasoning_effort == '':
                reasoning_effort = None
        
        # Get tools and vector_store_ids - these can be empty arrays
        tools = data.get('tools')
        vector_store_ids = data.get('vector_store_ids', [])  # Default to empty array if not provided
        
        # OpenAI API limitation: Only 1 vector store per assistant is allowed
        if vector_store_ids and len(vector_store_ids) > 1:
            return jsonify({
                "error": "OpenAI API only allows 1 vector store per assistant. Please select only 1 knowledge base."
            }), 400
        
        # Only pass reasoning_effort if it was explicitly provided
        update_kwargs = {
            'assistant_id': assistant_id,
            'name': data.get('name'),
            'instructions': data.get('instructions'),
            'model': None,  # model updates are not supported
            'tools': tools,  # Can be empty array []
            'vector_store_ids': vector_store_ids,  # Can be empty array []
        }
        
        # Only include reasoning_effort if it was explicitly provided in the request
        if reasoning_effort_provided:
            update_kwargs['reasoning_effort'] = reasoning_effort
            update_kwargs['reasoning_effort_provided'] = True
        else:
            update_kwargs['reasoning_effort_provided'] = False
        
        result = get_assistant_service().update_assistant(**update_kwargs)
        
        logger.info(f"UPDATE ASSISTANT SUCCESS - ID: {assistant_id}")
        log_response(endpoint, 200, assistant_id=assistant_id)
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"UPDATE ASSISTANT FAILED - ID: {assistant_id}, Error: {str(e)}")
        return handle_error(endpoint, e, "Update assistant")


@assistant_bp.route('/assistants/<assistant_id>', methods=['DELETE'])
def delete_assistant(assistant_id):
    """Delete an assistant"""
    endpoint = f'/api/assistants/{assistant_id}'
    
    try:
        logger.info(f"DELETE ASSISTANT REQUEST - ID: {assistant_id}")
        log_request(endpoint, assistant_id=assistant_id)
        
        result = get_assistant_service().delete_assistant(assistant_id)
        
        logger.info(f"DELETE ASSISTANT SUCCESS - ID: {assistant_id}, Result: {result}")
        log_response(endpoint, 200, deleted=result)
        return jsonify({"deleted": result}), 200
        
    except Exception as e:
        logger.error(f"DELETE ASSISTANT FAILED - ID: {assistant_id}, Error: {str(e)}")
        return handle_error(endpoint, e, "Delete assistant")


# ============ Vector Store Management ============

@assistant_bp.route('/vector-stores', methods=['POST'])
def create_vector_store():
    """Create a new vector store"""
    endpoint = '/api/vector-stores'
    
    try:
        data = request.json or {}
        name = data.get('name', 'New Vector Store')
        
        log_request(endpoint, vector_store_name=name, file_count=len(data.get('file_ids', [])))
        
        result = get_assistant_service().create_vector_store(
            name=name,
            file_ids=data.get('file_ids')
        )
        
        log_response(endpoint, 201, vector_store_id=result.get('id'))
        return jsonify(result), 201
        
    except Exception as e:
        return handle_error(endpoint, e, "Create vector store")


@assistant_bp.route('/vector-stores/<vector_store_id>', methods=['GET'])
def get_vector_store(vector_store_id):
    """Get vector store details"""
    endpoint = f'/api/vector-stores/{vector_store_id}'
    
    try:
        log_request(endpoint, vector_store_id=vector_store_id)
        
        result = get_assistant_service().get_vector_store(vector_store_id)
        
        log_response(endpoint, 200, vector_store_name=result.get('name'))
        return jsonify(result), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Get vector store")


@assistant_bp.route('/vector-stores', methods=['GET'])
def list_vector_stores():
    """List all vector stores"""
    endpoint = '/api/vector-stores'
    
    try:
        # Validate and sanitize limit parameter
        limit_arg = request.args.get('limit', 20, type=int)
        # OpenAI API typically has a max limit of 100 for list operations
        # Cap it to prevent bad requests
        limit = min(max(1, limit_arg), 100) if limit_arg else 20
        
        log_request(endpoint, limit=limit, original_limit=limit_arg)
        
        result = get_assistant_service().list_vector_stores(limit)
        
        log_response(endpoint, 200, count=len(result) if isinstance(result, list) else 0)
        return jsonify(result), 200
        
    except ValueError as e:
        logger.warning(f"Invalid limit parameter in list_vector_stores: {request.args.get('limit')}")
        return jsonify({"error": "Invalid limit parameter. Must be an integer between 1 and 100."}), 400
    except Exception as e:
        return handle_error(endpoint, e, "List vector stores")


@assistant_bp.route('/vector-stores/<vector_store_id>', methods=['PUT'])
def update_vector_store(vector_store_id):
    """Update vector store name"""
    endpoint = f'/api/vector-stores/{vector_store_id}'
    
    try:
        data = request.json or {}
        name = data.get('name')
        
        if not name:
            logger.warning("Missing name in update request")
            return jsonify({"error": "Name is required"}), 400
        
        log_request(endpoint, vector_store_id=vector_store_id, vector_store_name=name)
        
        result = get_assistant_service().update_vector_store(
            vector_store_id=vector_store_id,
            name=name
        )
        
        log_response(endpoint, 200, vector_store_id=vector_store_id)
        return jsonify(result), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Update vector store")


@assistant_bp.route('/vector-stores/<vector_store_id>', methods=['DELETE'])
def delete_vector_store(vector_store_id):
    """Delete a vector store"""
    endpoint = f'/api/vector-stores/{vector_store_id}'
    
    try:
        log_request(endpoint, vector_store_id=vector_store_id)
        
        result = get_assistant_service().delete_vector_store(vector_store_id)
        
        log_response(endpoint, 200, deleted=result)
        return jsonify({"deleted": result}), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Delete vector store")


# ============ File Management ============

@assistant_bp.route('/files', methods=['GET'])
def list_files():
    """List all files"""
    endpoint = '/api/files'
    
    try:
        log_request(endpoint)
        
        files = get_assistant_service().list_files()
        
        log_response(endpoint, 200, count=len(files) if isinstance(files, list) else 0)
        return jsonify(files), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "List files")


@assistant_bp.route('/files/<file_id>', methods=['GET'])
def get_file(file_id):
    """Get file details"""
    endpoint = f'/api/files/{file_id}'
    
    try:
        log_request(endpoint, file_id=file_id)
        
        file_info = get_assistant_service().get_file(file_id)
        
        log_response(endpoint, 200, file_name=file_info.get('filename'))
        return jsonify(file_info), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Get file")


@assistant_bp.route('/files', methods=['POST'])
def upload_file():
    """Upload a file to OpenAI"""
    endpoint = '/api/files'
    
    try:
        if 'file' not in request.files:
            logger.warning("No file in upload request")
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            logger.warning("Empty filename in upload request")
            return jsonify({"error": "Empty filename"}), 400
        
        log_request(endpoint, file_name=file.filename)
        
        # Read file bytes and upload with original filename
        # This preserves the file extension for OpenAI's type detection
        file_bytes = file.read()
        file_id = get_assistant_service().upload_file_from_bytes(
            file_bytes=file_bytes,
            filename=file.filename,
            purpose="assistants"
        )
        logger.info("File uploaded successfully: %s -> %s", file.filename, file_id)
        
        log_response(endpoint, 201, file_id=file_id, file_name=file.filename)
        return jsonify({"file_id": file_id, "filename": file.filename}), 201
    
    except Exception as e:
        return handle_error(endpoint, e, "Upload file")


@assistant_bp.route('/vector-stores/<vector_store_id>/files', methods=['POST'])
def add_file_to_vector_store(vector_store_id):
    """Add a file to a vector store"""
    endpoint = f'/api/vector-stores/{vector_store_id}/files'
    
    try:
        file_id = None
        
        # Check if uploading a new file or adding existing file
        if 'file' in request.files:
            # Upload new file
            file = request.files['file']
            if file.filename == '':
                logger.warning("Empty filename in file upload")
                return jsonify({"error": "Empty filename"}), 400
            
            log_request(endpoint, vector_store_id=vector_store_id, file_name=file.filename, action='upload')
            
            # Read file bytes and upload with original filename
            # This preserves the file extension for OpenAI's type detection
            file_bytes = file.read()
            file_id = get_assistant_service().upload_file_from_bytes(
                file_bytes=file_bytes,
                filename=file.filename,
                purpose="assistants"
            )
            logger.info("File uploaded: %s -> %s", file.filename, file_id)
        else:
            # Use existing file_id
            data = request.json or {}
            file_id = data.get('file_id')
            if not file_id:
                logger.warning("No file_id provided")
                return jsonify({"error": "No file_id provided"}), 400
            
            log_request(endpoint, vector_store_id=vector_store_id, file_id=file_id, action='add_existing')
        
        # Add to vector store
        result = get_assistant_service().add_file_to_vector_store(vector_store_id, file_id)
        logger.info("File %s added to vector store %s", file_id, vector_store_id)
        
        log_response(endpoint, 201, file_id=file_id, vector_store_id=vector_store_id)
        return jsonify(result), 201
    
    except Exception as e:
        return handle_error(endpoint, e, "Add file to vector store")


@assistant_bp.route('/vector-stores/<vector_store_id>/files', methods=['GET'])
def list_vector_store_files(vector_store_id):
    """List files in a vector store"""
    endpoint = f'/api/vector-stores/{vector_store_id}/files'
    
    try:
        limit = request.args.get('limit', 100, type=int)
        
        log_request(endpoint, vector_store_id=vector_store_id, limit=limit)
        
        result = get_assistant_service().list_vector_store_files(vector_store_id, limit)
        
        log_response(endpoint, 200, count=len(result) if isinstance(result, list) else 0)
        return jsonify(result), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "List vector store files")


@assistant_bp.route('/vector-stores/<vector_store_id>/files/<file_id>', methods=['DELETE'])
def delete_vector_store_file(vector_store_id, file_id):
    """Remove a file from a vector store"""
    endpoint = f'/api/vector-stores/{vector_store_id}/files/{file_id}'
    
    try:
        log_request(endpoint, vector_store_id=vector_store_id, file_id=file_id)
        
        result = get_assistant_service().delete_vector_store_file(vector_store_id, file_id)
        
        log_response(endpoint, 200, deleted=result)
        return jsonify({"deleted": result}), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Delete vector store file")


@assistant_bp.route('/files/<file_id>', methods=['DELETE'])
def delete_file(file_id):
    """Delete a file from OpenAI"""
    endpoint = f'/api/files/{file_id}'
    
    try:
        log_request(endpoint, file_id=file_id)
        
        result = get_assistant_service().delete_file(file_id)
        
        log_response(endpoint, 200, deleted=result)
        return jsonify({"deleted": result}), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Delete file")


# ============ Thread Management ============

@assistant_bp.route('/threads', methods=['POST'])
def create_thread():
    """Create a new conversation thread"""
    endpoint = '/api/threads'
    
    try:
        data = request.json or {}
        messages = data.get('messages')
        
        log_request(endpoint, has_messages=bool(messages))
        
        thread_id = get_assistant_service().create_thread(messages)
        
        log_response(endpoint, 201, thread_id=thread_id)
        return jsonify({"thread_id": thread_id}), 201
        
    except Exception as e:
        return handle_error(endpoint, e, "Create thread")


@assistant_bp.route('/threads/<thread_id>/messages', methods=['GET'])
def get_thread_messages(thread_id):
    """Get messages from a thread"""
    endpoint = f'/api/threads/{thread_id}/messages'
    
    try:
        limit = request.args.get('limit', 20, type=int)
        
        log_request(endpoint, thread_id=thread_id, limit=limit)
        
        result = get_assistant_service().get_thread_messages(thread_id, limit)
        
        log_response(endpoint, 200, message_count=len(result) if isinstance(result, list) else 0)
        return jsonify(result), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Get thread messages")


@assistant_bp.route('/threads/<thread_id>', methods=['DELETE'])
def delete_thread(thread_id):
    """Delete a thread"""
    endpoint = f'/api/threads/{thread_id}'
    
    try:
        log_request(endpoint, thread_id=thread_id)
        
        result = get_assistant_service().delete_thread(thread_id)
        
        log_response(endpoint, 200, deleted=result)
        return jsonify({"deleted": result}), 200
        
    except Exception as e:
        return handle_error(endpoint, e, "Delete thread")
