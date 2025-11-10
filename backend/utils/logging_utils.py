"""
Common logging utilities for enterprise-level logging and error handling
"""
import logging
import traceback
from typing import Any, Dict, Tuple

from flask import jsonify, request

logger = logging.getLogger(__name__)


def log_request(endpoint: str, **kwargs: Any) -> None:
    """
    Log incoming request details with structured data
    
    Args:
        endpoint: API endpoint being called
        **kwargs: Additional context to log
    """
    logger.info(
        "=== REQUEST START: %s ===",
        endpoint,
        extra={
            'endpoint': endpoint,
            'method': request.method,
            'remote_addr': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            **kwargs
        }
    )


def log_response(endpoint: str, status_code: int, **kwargs: Any) -> None:
    """
    Log response details with structured data
    
    Args:
        endpoint: API endpoint being called
        status_code: HTTP status code
        **kwargs: Additional context to log
    """
    logger.info(
        "=== REQUEST END: %s [%d] ===",
        endpoint,
        status_code,
        extra={
            'endpoint': endpoint,
            'status_code': status_code,
            **kwargs
        }
    )


def handle_error(endpoint: str, error: Exception, context: str = "") -> Tuple[Any, int]:
    """
    Centralized error handling with proper logging and status codes
    
    Args:
        endpoint: API endpoint where error occurred
        error: The exception that was raised
        context: Additional context about where/why error occurred
        
    Returns:
        Tuple of (jsonify response, status_code)
    """
    error_id = id(error)  # Unique error identifier for tracking
    
    # Log full stack trace with context
    logger.error(
        "ERROR [%s] in %s: %s - %s",
        error_id,
        endpoint,
        context,
        str(error),
        exc_info=True,
        extra={
            'error_id': error_id,
            'endpoint': endpoint,
            'context': context,
            'error_type': type(error).__name__,
            'stack_trace': traceback.format_exc()
        }
    )
    
    # Determine appropriate HTTP status code based on error type
    error_type = type(error).__name__
    if 'NotFound' in error_type or 'DoesNotExist' in error_type:
        status_code = 404
    elif 'Unauthorized' in error_type or 'Permission' in error_type or 'Forbidden' in error_type:
        status_code = 403
    elif 'Validation' in error_type or 'Invalid' in error_type or 'ValueError' in error_type:
        status_code = 400
    elif 'Timeout' in error_type:
        status_code = 504
    else:
        status_code = 500
    
    return jsonify({
        'error': str(error),
        'error_type': error_type,
        'error_id': error_id,
        'context': context
    }), status_code


def log_stream_error(error: Exception, context: str, **extra_context: Any) -> Dict[str, Any]:
    """
    Log streaming errors and return error chunk for SSE
    
    Args:
        error: The exception that was raised
        context: Context about where error occurred
        **extra_context: Additional context data to log
        
    Returns:
        Error chunk dictionary for SSE stream
    """
    error_id = id(error)
    
    logger.error(
        "ERROR [%s] in streaming: %s - %s",
        error_id,
        context,
        str(error),
        exc_info=True,
        extra={
            'error_id': error_id,
            'context': context,
            'error_type': type(error).__name__,
            'stack_trace': traceback.format_exc(),
            **extra_context
        }
    )
    
    return {
        'type': 'error',
        'error': str(error),
        'error_type': type(error).__name__,
        'error_id': error_id
    }

