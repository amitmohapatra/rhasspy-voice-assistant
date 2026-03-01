"""Error response schemas for API documentation.

These schemas document all possible error responses in the API.
"""

from enum import Enum
from typing import Any

from pydantic import Field

from src.schemas.base import BaseSchema


class ErrorCode(str, Enum):
    """Error codes returned by the API."""

    # Validation errors (400)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Authentication errors (401)
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"

    # Authorization errors (403)
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_ROLE = "INSUFFICIENT_ROLE"

    # Not found errors (404)
    NOT_FOUND = "NOT_FOUND"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    ASSISTANT_NOT_FOUND = "ASSISTANT_NOT_FOUND"
    CONVERSATION_NOT_FOUND = "CONVERSATION_NOT_FOUND"
    KNOWLEDGE_BASE_NOT_FOUND = "KNOWLEDGE_BASE_NOT_FOUND"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
    ORGANIZATION_NOT_FOUND = "ORGANIZATION_NOT_FOUND"

    # Conflict errors (409)
    CONFLICT = "CONFLICT"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    SLUG_ALREADY_EXISTS = "SLUG_ALREADY_EXISTS"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"

    # Rate limit errors (429)
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"

    # Server errors (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"

    # External service errors (502)
    LLM_ERROR = "LLM_ERROR"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    STT_ERROR = "STT_ERROR"
    TTS_ERROR = "TTS_ERROR"
    EMBEDDING_ERROR = "EMBEDDING_ERROR"

    # Tool errors
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"

    # Storage errors
    STORAGE_ERROR = "STORAGE_ERROR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"


class ErrorDetail(BaseSchema):
    """Detailed error information."""

    field: str | None = Field(
        default=None,
        description="The field that caused the error (for validation errors)",
        json_schema_extra={"example": "email"}
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        json_schema_extra={"example": "Invalid email format"}
    )
    value: Any = Field(
        default=None,
        description="The invalid value that was provided",
        json_schema_extra={"example": "not-an-email"}
    )


class ErrorResponse(BaseSchema):
    """Standard error response format.

    All API errors follow this format for consistency.
    """

    error: str = Field(
        ...,
        description="Error code for programmatic handling",
        json_schema_extra={"example": "VALIDATION_ERROR"}
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        json_schema_extra={"example": "Validation failed"}
    )
    details: list[ErrorDetail] | dict[str, Any] | None = Field(
        default=None,
        description="Additional error details",
        json_schema_extra={
            "example": [
                {"field": "email", "message": "Invalid email format", "value": "not-an-email"}
            ]
        }
    )
    request_id: str | None = Field(
        default=None,
        description="Request ID for debugging and support",
        json_schema_extra={"example": "req_abc123xyz"}
    )


class ValidationErrorResponse(BaseSchema):
    """Validation error response (HTTP 400)."""

    error: str = Field(
        default="VALIDATION_ERROR",
        description="Error code",
        json_schema_extra={"example": "VALIDATION_ERROR"}
    )
    message: str = Field(
        default="Validation failed",
        description="Error message",
        json_schema_extra={"example": "Validation failed"}
    )
    details: list[ErrorDetail] = Field(
        default_factory=list,
        description="List of validation errors",
        json_schema_extra={
            "example": [
                {"field": "email", "message": "Invalid email format", "value": "not-an-email"},
                {"field": "password", "message": "Password must be at least 8 characters", "value": "short"}
            ]
        }
    )


class AuthenticationErrorResponse(BaseSchema):
    """Authentication error response (HTTP 401)."""

    error: str = Field(
        default="AUTHENTICATION_ERROR",
        description="Error code",
        json_schema_extra={"example": "AUTHENTICATION_ERROR"}
    )
    message: str = Field(
        default="Authentication required",
        description="Error message",
        json_schema_extra={"example": "Invalid email or password"}
    )


class AuthorizationErrorResponse(BaseSchema):
    """Authorization error response (HTTP 403)."""

    error: str = Field(
        default="AUTHORIZATION_ERROR",
        description="Error code",
        json_schema_extra={"example": "AUTHORIZATION_ERROR"}
    )
    message: str = Field(
        default="Permission denied",
        description="Error message",
        json_schema_extra={"example": "You don't have permission to access this resource"}
    )


class NotFoundErrorResponse(BaseSchema):
    """Not found error response (HTTP 404)."""

    error: str = Field(
        default="NOT_FOUND",
        description="Error code",
        json_schema_extra={"example": "NOT_FOUND"}
    )
    message: str = Field(
        default="Resource not found",
        description="Error message",
        json_schema_extra={"example": "Assistant not found"}
    )
    resource: str | None = Field(
        default=None,
        description="The type of resource that was not found",
        json_schema_extra={"example": "assistant"}
    )
    resource_id: str | None = Field(
        default=None,
        description="The ID of the resource that was not found",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )


class RateLimitErrorResponse(BaseSchema):
    """Rate limit error response (HTTP 429)."""

    error: str = Field(
        default="RATE_LIMIT_EXCEEDED",
        description="Error code",
        json_schema_extra={"example": "RATE_LIMIT_EXCEEDED"}
    )
    message: str = Field(
        default="Rate limit exceeded",
        description="Error message",
        json_schema_extra={"example": "Too many requests. Please try again later."}
    )
    retry_after: int | None = Field(
        default=None,
        description="Number of seconds to wait before retrying",
        json_schema_extra={"example": 60}
    )
    limit: int | None = Field(
        default=None,
        description="The rate limit that was exceeded",
        json_schema_extra={"example": 100}
    )
    remaining: int | None = Field(
        default=None,
        description="Number of requests remaining",
        json_schema_extra={"example": 0}
    )


class InternalErrorResponse(BaseSchema):
    """Internal server error response (HTTP 500)."""

    error: str = Field(
        default="INTERNAL_ERROR",
        description="Error code",
        json_schema_extra={"example": "INTERNAL_ERROR"}
    )
    message: str = Field(
        default="An internal error occurred",
        description="Error message",
        json_schema_extra={"example": "An unexpected error occurred. Please try again later."}
    )
    request_id: str | None = Field(
        default=None,
        description="Request ID for support reference",
        json_schema_extra={"example": "req_abc123xyz"}
    )


class ProviderErrorResponse(BaseSchema):
    """External provider error response (HTTP 502)."""

    error: str = Field(
        default="PROVIDER_ERROR",
        description="Error code",
        json_schema_extra={"example": "LLM_ERROR"}
    )
    message: str = Field(
        default="External service error",
        description="Error message",
        json_schema_extra={"example": "OpenAI API returned an error"}
    )
    provider: str | None = Field(
        default=None,
        description="The provider that failed",
        json_schema_extra={"example": "openai"}
    )
    provider_message: str | None = Field(
        default=None,
        description="Error message from the provider",
        json_schema_extra={"example": "Rate limit exceeded"}
    )


# Common response documentation for routes
ERROR_RESPONSES = {
    400: {"model": ValidationErrorResponse, "description": "Validation error - Invalid request data"},
    401: {"model": AuthenticationErrorResponse, "description": "Authentication error - Invalid or missing credentials"},
    403: {"model": AuthorizationErrorResponse, "description": "Authorization error - Insufficient permissions"},
    404: {"model": NotFoundErrorResponse, "description": "Not found - Resource does not exist"},
    429: {"model": RateLimitErrorResponse, "description": "Rate limit exceeded - Too many requests"},
    500: {"model": InternalErrorResponse, "description": "Internal server error"},
    502: {"model": ProviderErrorResponse, "description": "Provider error - External service failure"},
}
