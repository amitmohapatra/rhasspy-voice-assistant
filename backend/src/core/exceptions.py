"""Custom exceptions for the AI Platform."""

from __future__ import annotations

from typing import Any


class AIError(Exception):
    """Base exception for AI Platform."""

    def __init__(
        self,
        message: str,
        code: str = "AI_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class ValidationError(AIError):
    """Validation error."""

    def __init__(
        self, message: str = "Validation failed", details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class AuthenticationError(AIError):
    """Authentication error."""

    def __init__(
        self,
        message: str = "Authentication required",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details,
        )


class AuthorizationError(AIError):
    """Authorization error."""

    def __init__(
        self,
        message: str = "Permission denied",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details,
        )


class NotFoundError(AIError):
    """Resource not found error."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if resource:
            details["resource"] = resource
        super().__init__(
            message=message,
            code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class RateLimitError(AIError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=details,
        )


class LLMError(AIError):
    """LLM provider error."""

    def __init__(
        self,
        message: str = "LLM request failed",
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if provider:
            details["provider"] = provider
        super().__init__(
            message=message,
            code="LLM_ERROR",
            status_code=502,
            details=details,
        )


class StorageError(AIError):
    """Storage operation error."""

    def __init__(
        self,
        message: str = "Storage operation failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="STORAGE_ERROR",
            status_code=500,
            details=details,
        )


class ToolExecutionError(AIError):
    """Tool execution error."""

    def __init__(
        self,
        message: str = "Tool execution failed",
        tool_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if tool_name:
            details["tool_name"] = tool_name
        super().__init__(
            message=message,
            code="TOOL_EXECUTION_ERROR",
            status_code=500,
            details=details,
        )


class ProviderError(AIError):
    """External provider error (APIs, services, etc.)."""

    def __init__(
        self,
        message: str = "Provider request failed",
        provider: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if provider:
            details["provider"] = provider
        super().__init__(
            message=message,
            code="PROVIDER_ERROR",
            status_code=502,
            details=details,
        )


class ConfigurationError(AIError):
    """Configuration error."""

    def __init__(
        self,
        message: str = "Configuration error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CONFIGURATION_ERROR",
            status_code=500,
            details=details,
        )


class QuotaExceededError(AIError):
    """Quota exceeded error."""

    def __init__(
        self,
        message: str = "Quota exceeded",
        quota_type: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        details = details or {}
        if quota_type:
            details["quota_type"] = quota_type
        super().__init__(
            message=message,
            code="QUOTA_EXCEEDED",
            status_code=402,
            details=details,
        )
