"""Base LLM Provider interface.

This module defines the abstract base class and data models for all LLM providers.
Provider implementations should inherit from LLMProvider and implement all
abstract methods.

Design Principles:
- Single Responsibility: Each class has one clear purpose
- Open/Closed: Easy to extend with new providers without modifying base
- Interface Segregation: Clear, minimal interface for providers
- Dependency Inversion: Providers depend on abstractions, not concretions
"""

from __future__ import annotations

import fnmatch
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from src.models.capability import CapabilityType


# ==================== Data Models ====================

class Message(BaseModel):
    """Chat message in a conversation.

    Attributes:
        role: Message role (system, user, assistant, tool)
        content: Message content
        name: Optional name for tool messages
        tool_calls: Tool calls made by assistant
        tool_call_id: ID of tool call being responded to
    """
    role: str
    content: str
    name: str | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None

    class Config:
        frozen = True  # Immutable for safety


class ToolDefinition(BaseModel):
    """Tool/function definition for function calling.

    Follows OpenAI's tool definition format as the standard.
    For built-in tools like web_search, function is optional.
    """
    type: str = "function"
    function: dict[str, Any] | None = None  # Optional for built-in tools like web_search


class CompletionRequest(BaseModel):
    """Request for LLM completion.

    Contains all parameters needed for a completion request.
    Provider-specific options can be passed via extra_options.
    Tools are passed as provider-native dicts (converted by ToolResolver).
    """
    messages: list[Message]
    model: str
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=1)
    top_p: float = Field(default=1.0, ge=0, le=1)
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict | None = None
    stream: bool = True
    connectors: list[dict[str, Any]] | None = None  # Cohere connectors (separate API param)
    extra_options: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    """Tool call from LLM response.

    Represents a function call that the LLM wants to make.
    For OpenAI Responses API, name and arguments are stored directly.
    For legacy Chat Completions API, function dict is used.
    """
    id: str
    type: str = "function"
    name: str = ""  # Direct name (Responses API format)
    arguments: str = ""  # Direct arguments (Responses API format)
    function: dict[str, Any] | None = None  # Legacy: Contains name, arguments


class CompletionResponse(BaseModel):
    """Response from non-streaming LLM completion.

    Contains the full response including content, tool calls, and usage stats.
    """
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    finish_reason: str = "stop"

    # Usage statistics
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    # Model info
    model: str = ""


class StreamDelta(BaseModel):
    """Streaming delta update.

    Represents a single chunk in a streaming response.
    Types: 'text' for content, 'tool_call' for tool calls, 'finish' for end.
    """
    type: str  # text, tool_call, finish
    content: str | None = None
    tool_call: ToolCall | None = None
    finish_reason: str | None = None

    # Usage (only on finish)
    input_tokens: int | None = None
    output_tokens: int | None = None


# ==================== Base Provider ====================

class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All LLM provider implementations must inherit from this class and
    implement all abstract methods. This ensures a consistent interface
    across all providers.

    Attributes:
        provider_name: Unique identifier for the provider

    Example:
        class MyProvider(LLMProvider):
            provider_name = "myprovider"

            async def complete(self, request: CompletionRequest) -> CompletionResponse:
                # Implementation
                pass
    """

    provider_name: str = "base"

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion.

        Args:
            request: Completion request with messages and parameters

        Returns:
            CompletionResponse with content, tool calls, and usage stats

        Raises:
            LLMError: If the completion request fails
        """
        pass

    @abstractmethod
    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion - yields delta updates.

        Args:
            request: Completion request with messages and parameters

        Yields:
            StreamDelta objects for text content, tool calls, and finish

        Raises:
            LLMError: If the streaming request fails
        """
        pass

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for texts.

        Args:
            texts: List of strings to embed
            model: Optional model override

        Returns:
            List of embedding vectors

        Raises:
            LLMError: If embedding generation fails
        """
        pass

    @abstractmethod
    def list_models(self) -> list[str]:
        """List available models for this provider.

        Returns:
            List of model identifiers
        """
        pass

    @abstractmethod
    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling/tools.

        Args:
            model: Model identifier to check

        Returns:
            True if the model supports tools
        """
        pass

    # ==================== Helper Methods ====================

    def _extract_system_prompt(self, messages: list[Message]) -> str | None:
        """Extract system prompt from messages.

        Args:
            messages: List of messages

        Returns:
            System prompt content or None if not present
        """
        for msg in messages:
            if msg.role == "system":
                return msg.content
        return None

    def _filter_messages_by_role(
        self,
        messages: list[Message],
        exclude_roles: set[str] | None = None,
        include_roles: set[str] | None = None,
    ) -> list[Message]:
        """Filter messages by role.

        Args:
            messages: List of messages
            exclude_roles: Roles to exclude (e.g., {'system'})
            include_roles: Roles to include (if set, only these are included)

        Returns:
            Filtered list of messages
        """
        if include_roles is not None:
            return [m for m in messages if m.role in include_roles]
        if exclude_roles is not None:
            return [m for m in messages if m.role not in exclude_roles]
        return messages

    def _validate_request(self, request: CompletionRequest) -> None:
        """Validate a completion request.

        Override in subclasses for provider-specific validation.

        Args:
            request: Request to validate

        Raises:
            ValidationError: If request is invalid
        """
        if not request.messages:
            from src.core.exceptions import ValidationError
            raise ValidationError("Messages list cannot be empty")

        if not request.model:
            from src.core.exceptions import ValidationError
            raise ValidationError("Model must be specified")

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID.

        Override in subclasses that support model aliases.

        Args:
            model: Model name or alias

        Returns:
            Full model identifier
        """
        return model

    # ==================== DB-Driven Capability Methods ====================

    def model_matches_patterns(
        self,
        model: str,
        supported_patterns: list[str] | None,
        excluded_patterns: list[str] | None = None,
    ) -> bool:
        """Check if model matches supported patterns and is not excluded.

        Used for checking capabilities based on vendor mappings from DB.

        Args:
            model: Model identifier to check
            supported_patterns: List of glob patterns that support this capability
            excluded_patterns: List of glob patterns to exclude

        Returns:
            True if model matches supported patterns and is not excluded
        """
        # Default to supporting all models if no patterns specified
        if not supported_patterns:
            supported_patterns = ["*"]

        # Check if matches any supported pattern
        matches_supported = any(
            fnmatch.fnmatch(model, pattern)
            for pattern in supported_patterns
        )

        # Check if excluded
        is_excluded = False
        if excluded_patterns:
            is_excluded = any(
                fnmatch.fnmatch(model, pattern)
                for pattern in excluded_patterns
            )

        return matches_supported and not is_excluded

    async def check_capability_from_db(
        self,
        db: "AsyncSession",
        model_id: str,
        capability_type: "CapabilityType",
    ) -> bool:
        """Check if a model supports a capability by querying the database.

        This is the DB-driven approach that queries model_capabilities table.

        Args:
            db: Database session
            model_id: The model's database UUID
            capability_type: The capability to check

        Returns:
            True if model supports the capability
        """
        from sqlalchemy import select
        from src.models.capability import ModelCapability

        result = await db.execute(
            select(ModelCapability).where(
                ModelCapability.model_id == model_id,
                ModelCapability.capability_type == capability_type,
                ModelCapability.is_enabled == True,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_vendor_capability_mapping(
        self,
        db: "AsyncSession",
        provider_id: str,
        capability_type: "CapabilityType",
    ) -> dict | None:
        """Get vendor-specific capability mapping from database.

        Args:
            db: Database session
            provider_id: The provider's database UUID
            capability_type: The capability to look up

        Returns:
            Mapping dict with vendor_name, api_config, supported_model_patterns, etc.
        """
        from sqlalchemy import select
        from src.models.capability import VendorCapabilityMapping

        result = await db.execute(
            select(VendorCapabilityMapping).where(
                VendorCapabilityMapping.provider_id == provider_id,
                VendorCapabilityMapping.capability_type == capability_type,
                VendorCapabilityMapping.is_available == True,
            )
        )
        mapping = result.scalar_one_or_none()
        if mapping:
            return {
                "vendor_name": mapping.vendor_name,
                "invocation_method": mapping.invocation_method,
                "api_config": mapping.api_config,
                "default_params": mapping.default_params,
                "supported_model_patterns": mapping.supported_model_patterns,
                "excluded_model_patterns": mapping.excluded_model_patterns,
            }
        return None

    async def check_capability_from_vendor_mapping(
        self,
        db: "AsyncSession",
        provider_id: str,
        model: str,
        capability_type: "CapabilityType",
    ) -> bool:
        """Check capability using vendor mapping patterns from DB.

        Uses the VendorCapabilityMapping table's supported_model_patterns
        and excluded_model_patterns for pattern-based checking.

        Args:
            db: Database session
            provider_id: The provider's database UUID
            model: Model identifier (e.g., "gpt-4o", "claude-3-5-sonnet")
            capability_type: The capability to check

        Returns:
            True if model supports the capability based on vendor patterns
        """
        mapping = await self.get_vendor_capability_mapping(
            db, provider_id, capability_type
        )
        if not mapping:
            return False

        return self.model_matches_patterns(
            model,
            mapping.get("supported_model_patterns"),
            mapping.get("excluded_model_patterns"),
        )
