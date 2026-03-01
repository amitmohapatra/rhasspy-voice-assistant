"""Model Capability System - Database-driven tool and capability management.

This module implements a flexible, database-driven capability system that allows:
1. Different models to have different capabilities (file search, code interpreter, web search)
2. Admins to configure which tools are available for which models via UI
3. Automatic capability validation before tool execution
4. Vendor-specific capability mapping (OpenAI file_search vs Anthropic artifacts)

Design Principles:
- Everything configurable is in the database
- Constants that users shouldn't modify stay in code
- UI-driven configuration for admins
- Automatic capability inference and validation
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.models.ai_model import AIModel, AIProvider
    from src.models.tool import Tool


# ==================== Enums (Code Constants - Users Don't Modify) ====================

class CapabilityType(str, Enum):
    """Core capability types - these are code constants.

    These define the fundamental capability categories that exist across all vendors.
    Users cannot add new capability types - only admins can enable/disable existing ones.
    """
    # Built-in vendor capabilities (OpenAI Assistants API style)
    FILE_SEARCH = "file_search"           # Search through uploaded files
    CODE_INTERPRETER = "code_interpreter"  # Execute Python code in sandbox
    WEB_SEARCH = "web_search"             # Search the internet
    IMAGE_GENERATION = "image_generation"  # Generate images (DALL-E, etc.)
    VISION = "vision"                      # Analyze images/screenshots
    AUDIO_INPUT = "audio_input"            # Process audio input
    AUDIO_OUTPUT = "audio_output"          # Generate speech/audio
    VIDEO_INPUT = "video_input"            # Process video input
    VIDEO_OUTPUT = "video_output"          # Generate video

    # Function/Tool calling
    FUNCTION_CALLING = "function_calling"  # Call custom functions
    PARALLEL_FUNCTIONS = "parallel_functions"  # Call multiple functions at once
    STRUCTURED_OUTPUT = "structured_output"  # JSON mode / structured responses

    # Reasoning capabilities
    EXTENDED_THINKING = "extended_thinking"  # o1-style reasoning
    CHAIN_OF_THOUGHT = "chain_of_thought"   # Show reasoning steps

    # Context capabilities
    LONG_CONTEXT = "long_context"          # 100k+ context window
    STREAMING = "streaming"                 # Stream responses

    # Special capabilities
    ARTIFACTS = "artifacts"                 # Claude-style artifacts
    COMPUTER_USE = "computer_use"           # Control computer (Claude)
    MCP = "mcp"                             # Model Context Protocol support


class ToolCategory(str, Enum):
    """Tool categories for organization."""
    BUILTIN = "builtin"           # Vendor-provided (file_search, code_interpreter)
    FUNCTION = "function"         # Custom function calling
    INTEGRATION = "integration"   # Third-party integrations (Slack, GitHub)
    MCP = "mcp"                   # MCP protocol tools
    CUSTOM = "custom"             # User-defined tools


class CapabilityScope(str, Enum):
    """Where the capability is implemented."""
    VENDOR_NATIVE = "vendor_native"     # Vendor's built-in (OpenAI file_search)
    PLATFORM_PROVIDED = "platform_provided"  # Our platform provides it
    USER_CUSTOM = "user_custom"         # User-created


# ==================== Database Models ====================

class ModelCapability(Base):
    """Maps which capabilities each AI model supports."""

    __tablename__ = "model_capabilities"

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_models.id"), nullable=False
    )
    capability_type: Mapped[str] = mapped_column(
        SQLEnum(CapabilityType), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    vendor_implementation: Mapped[dict] = mapped_column(JSONB, default=dict)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    model: Mapped["AIModel"] = relationship("AIModel", back_populates="capabilities")

    __table_args__ = (
        UniqueConstraint("model_id", "capability_type", name="uq_model_capability"),
        Index("idx_model_capabilities_model", "model_id"),
        Index("idx_model_capabilities_type", "capability_type"),
    )


class CapabilityDefinition(Base):
    """Defines capability metadata and configuration schema."""

    __tablename__ = "capability_definitions"

    capability_type: Mapped[str] = mapped_column(
        SQLEnum(CapabilityType), unique=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="general")
    config_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    default_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    vendor_mappings: Mapped[dict] = mapped_column(JSONB, default=dict)
    requires_capabilities: Mapped[list] = mapped_column(ARRAY(String), default=[])
    incompatible_with: Mapped[list] = mapped_column(ARRAY(String), default=[])
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_beta: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class ToolCapabilityRequirement(Base):
    """Maps which capabilities a tool requires."""

    __tablename__ = "tool_capability_requirements"

    tool_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tools.id", ondelete="CASCADE"), nullable=False
    )
    capability_type: Mapped[str] = mapped_column(
        SQLEnum(CapabilityType), nullable=False
    )
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    tool: Mapped["Tool"] = relationship("Tool", back_populates="capability_requirements")

    __table_args__ = (
        UniqueConstraint("tool_id", "capability_type", name="uq_tool_capability"),
        Index("idx_tool_capability_tool", "tool_id"),
    )


class VendorCapabilityMapping(Base):
    """Maps vendor-specific capability implementations."""

    __tablename__ = "vendor_capability_mappings"

    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_providers.id"), nullable=False
    )
    capability_type: Mapped[str] = mapped_column(
        SQLEnum(CapabilityType), nullable=False
    )
    vendor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    invocation_method: Mapped[str] = mapped_column(String(50), nullable=False)
    default_params: Mapped[dict] = mapped_column(JSONB, default=dict)
    supported_model_patterns: Mapped[list] = mapped_column(ARRAY(String), default=[])
    excluded_model_patterns: Mapped[list] = mapped_column(ARRAY(String), default=[])
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    provider: Mapped["AIProvider"] = relationship("AIProvider", back_populates="capability_mappings")

    __table_args__ = (
        UniqueConstraint("provider_id", "capability_type", name="uq_vendor_capability"),
        Index("idx_vendor_capability_provider", "provider_id"),
    )


# ==================== Seed Data Constants (Code-Only) ====================

# These are the default capability definitions that get seeded into the database
# Users can modify display_name, description, etc. but not the core types

DEFAULT_CAPABILITY_DEFINITIONS = [
    {
        "capability_type": CapabilityType.FILE_SEARCH,
        "display_name": "File Search",
        "description": "Search through uploaded documents and files using semantic search",
        "icon": "file-search",
        "category": "retrieval",
        "config_schema": {
            "type": "object",
            "properties": {
                "max_files": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                "chunk_size": {"type": "integer", "default": 800},
                "chunk_overlap": {"type": "integer", "default": 400},
            }
        },
        "default_config": {"max_files": 20, "chunk_size": 800, "chunk_overlap": 400},
        "vendor_mappings": {
            "openai": {"tool_type": "file_search", "api": "assistants"},
            "anthropic": {"method": "context_injection"},
            "google": {"method": "grounding"},
        },
    },
    {
        "capability_type": CapabilityType.CODE_INTERPRETER,
        "display_name": "Code Interpreter",
        "description": "Execute Python code in a sandboxed environment for data analysis and computation",
        "icon": "code",
        "category": "execution",
        "config_schema": {
            "type": "object",
            "properties": {
                "timeout_seconds": {"type": "integer", "default": 300, "minimum": 10, "maximum": 600},
                "memory_mb": {"type": "integer", "default": 512, "minimum": 128, "maximum": 2048},
                "allowed_packages": {"type": "array", "items": {"type": "string"}},
            }
        },
        "default_config": {"timeout_seconds": 300, "memory_mb": 512},
        "vendor_mappings": {
            "openai": {"tool_type": "code_interpreter", "api": "assistants"},
        },
    },
    {
        "capability_type": CapabilityType.WEB_SEARCH,
        "display_name": "Web Search",
        "description": "Search the internet for real-time information",
        "icon": "globe",
        "category": "retrieval",
        "config_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                "search_depth": {"type": "string", "enum": ["basic", "advanced"]},
            }
        },
        "default_config": {"max_results": 5, "search_depth": "basic"},
        "vendor_mappings": {
            "openai": {"method": "function_call", "function": "web_search"},
            "perplexity": {"method": "native"},
        },
    },
    {
        "capability_type": CapabilityType.VISION,
        "display_name": "Vision",
        "description": "Analyze and understand images, screenshots, and visual content",
        "icon": "eye",
        "category": "multimodal",
        "config_schema": {
            "type": "object",
            "properties": {
                "max_images": {"type": "integer", "default": 5},
                "detail_level": {"type": "string", "enum": ["low", "high", "auto"]},
            }
        },
        "default_config": {"max_images": 5, "detail_level": "auto"},
        "vendor_mappings": {
            "openai": {"method": "message_content", "type": "image_url"},
            "anthropic": {"method": "message_content", "type": "image"},
            "google": {"method": "inline_data"},
        },
    },
    {
        "capability_type": CapabilityType.FUNCTION_CALLING,
        "display_name": "Function Calling",
        "description": "Call custom functions and tools defined by the user",
        "icon": "function",
        "category": "tools",
        "config_schema": {
            "type": "object",
            "properties": {
                "max_functions": {"type": "integer", "default": 128},
                "parallel_calls": {"type": "boolean", "default": True},
            }
        },
        "default_config": {"max_functions": 128, "parallel_calls": True},
        "vendor_mappings": {
            "openai": {"method": "tools", "type": "function"},
            "anthropic": {"method": "tools"},
            "google": {"method": "function_declarations"},
        },
    },
    {
        "capability_type": CapabilityType.EXTENDED_THINKING,
        "display_name": "Extended Thinking",
        "description": "Advanced reasoning with chain-of-thought processing",
        "icon": "brain",
        "category": "reasoning",
        "config_schema": {
            "type": "object",
            "properties": {
                "thinking_budget": {"type": "integer", "description": "Max tokens for thinking"},
                "show_thinking": {"type": "boolean", "default": False},
            }
        },
        "default_config": {"show_thinking": False},
        "vendor_mappings": {
            "openai": {"models": ["o1", "o1-mini", "o1-preview", "o3", "o3-mini"]},
            "anthropic": {"models": ["claude-*-4.5-*"], "param": "thinking"},
            "google": {"models": ["gemini-*-deep-think"]},
        },
        "is_premium": True,
    },
    {
        "capability_type": CapabilityType.ARTIFACTS,
        "display_name": "Artifacts",
        "description": "Create and display rich content artifacts (code, documents, etc.)",
        "icon": "box",
        "category": "output",
        "vendor_mappings": {
            "anthropic": {"method": "artifact_tag", "api": "messages"},
        },
    },
    {
        "capability_type": CapabilityType.COMPUTER_USE,
        "display_name": "Computer Use",
        "description": "Control computer through screenshots and actions",
        "icon": "monitor",
        "category": "automation",
        "config_schema": {
            "type": "object",
            "properties": {
                "allowed_actions": {"type": "array", "items": {"type": "string"}},
                "screen_resolution": {"type": "string"},
            }
        },
        "vendor_mappings": {
            "anthropic": {"method": "computer_use_tool", "beta": True},
        },
        "is_beta": True,
        "is_premium": True,
    },
    {
        "capability_type": CapabilityType.STREAMING,
        "display_name": "Streaming",
        "description": "Stream responses token by token",
        "icon": "activity",
        "category": "delivery",
        "default_config": {"enabled": True},
        "vendor_mappings": {
            "openai": {"param": "stream"},
            "anthropic": {"method": "stream"},
            "google": {"param": "stream"},
        },
    },
    {
        "capability_type": CapabilityType.STRUCTURED_OUTPUT,
        "display_name": "Structured Output",
        "description": "Generate JSON or structured data following a schema",
        "icon": "braces",
        "category": "output",
        "config_schema": {
            "type": "object",
            "properties": {
                "response_format": {"type": "object"},
                "strict": {"type": "boolean", "default": True},
            }
        },
        "vendor_mappings": {
            "openai": {"param": "response_format", "type": "json_schema"},
            "anthropic": {"method": "tool_use_for_json"},
            "google": {"param": "response_mime_type"},
        },
    },
    {
        "capability_type": CapabilityType.MCP,
        "display_name": "MCP Protocol",
        "description": "Model Context Protocol for external tool integration",
        "icon": "plug",
        "category": "integration",
        "config_schema": {
            "type": "object",
            "properties": {
                "server_url": {"type": "string"},
                "transport": {"type": "string", "enum": ["stdio", "http", "websocket"]},
            }
        },
        "vendor_mappings": {
            "anthropic": {"method": "native_mcp"},
        },
        "is_beta": True,
    },
    {
        "capability_type": CapabilityType.IMAGE_GENERATION,
        "display_name": "Image Generation",
        "description": "Generate images from text descriptions",
        "icon": "image",
        "category": "generation",
        "config_schema": {
            "type": "object",
            "properties": {
                "size": {"type": "string", "enum": ["256x256", "512x512", "1024x1024", "1792x1024"]},
                "quality": {"type": "string", "enum": ["standard", "hd"]},
                "style": {"type": "string", "enum": ["natural", "vivid"]},
            }
        },
        "default_config": {"size": "1024x1024", "quality": "standard"},
        "vendor_mappings": {
            "openai": {"model": "dall-e-3", "endpoint": "/v1/images/generations"},
        },
    },
    {
        "capability_type": CapabilityType.AUDIO_INPUT,
        "display_name": "Audio Input",
        "description": "Process and understand audio input",
        "icon": "mic",
        "category": "multimodal",
        "vendor_mappings": {
            "openai": {"model": "whisper-1", "endpoint": "/v1/audio/transcriptions"},
            "google": {"method": "inline_audio"},
        },
    },
    {
        "capability_type": CapabilityType.AUDIO_OUTPUT,
        "display_name": "Audio Output",
        "description": "Generate speech and audio from text",
        "icon": "volume-2",
        "category": "generation",
        "config_schema": {
            "type": "object",
            "properties": {
                "voice": {"type": "string"},
                "speed": {"type": "number", "minimum": 0.25, "maximum": 4.0},
            }
        },
        "vendor_mappings": {
            "openai": {"model": "tts-1", "endpoint": "/v1/audio/speech"},
            "elevenlabs": {"endpoint": "/v1/text-to-speech"},
        },
    },
]

# Default vendor capability mappings
DEFAULT_VENDOR_MAPPINGS = {
    "openai": {
        CapabilityType.FILE_SEARCH: {
            "vendor_name": "file_search",
            "invocation_method": "tool",
            "api_config": {"tool_type": "file_search"},
            "supported_model_patterns": ["gpt-4*", "gpt-3.5*"],
            "excluded_model_patterns": ["o1*", "o3*"],  # Reasoning models don't support
        },
        CapabilityType.CODE_INTERPRETER: {
            "vendor_name": "code_interpreter",
            "invocation_method": "tool",
            "api_config": {"tool_type": "code_interpreter"},
            "supported_model_patterns": ["gpt-4*", "gpt-3.5*"],
            "excluded_model_patterns": ["o1*", "o3*"],
        },
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["*"],
            "excluded_model_patterns": [],
        },
        CapabilityType.VISION: {
            "vendor_name": "vision",
            "invocation_method": "message_content",
            "api_config": {"content_type": "image_url"},
            "supported_model_patterns": ["gpt-4o*", "gpt-4-turbo*", "gpt-4-vision*"],
        },
        CapabilityType.WEB_SEARCH: {
            "vendor_name": "web_search",
            "invocation_method": "tool",
            "api_config": {"tool_type": "web_search_preview"},
            "supported_model_patterns": ["gpt-4*"],
            "notes": "Available in preview for select models",
        },
    },
    "anthropic": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["claude-*"],
        },
        CapabilityType.VISION: {
            "vendor_name": "vision",
            "invocation_method": "message_content",
            "api_config": {"content_type": "image"},
            "supported_model_patterns": ["claude-3*", "claude-*-4*"],
        },
        CapabilityType.COMPUTER_USE: {
            "vendor_name": "computer_use",
            "invocation_method": "tool",
            "api_config": {"tool_type": "computer_20241022"},
            "supported_model_patterns": ["claude-3-5-sonnet*", "claude-*-4*"],
            "notes": "Beta feature",
        },
        CapabilityType.EXTENDED_THINKING: {
            "vendor_name": "thinking",
            "invocation_method": "parameter",
            "api_config": {"param": "thinking"},
            "supported_model_patterns": ["claude-*-4.5-*"],
        },
    },
    "google": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "function_declarations",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["gemini-*"],
        },
        CapabilityType.VISION: {
            "vendor_name": "inline_data",
            "invocation_method": "message_content",
            "supported_model_patterns": ["gemini-*-pro*", "gemini-*-flash*"],
        },
        CapabilityType.WEB_SEARCH: {
            "vendor_name": "google_search_retrieval",
            "invocation_method": "tool",
            "api_config": {"tool_type": "google_search_retrieval"},
            "supported_model_patterns": ["gemini-*"],
        },
    },
    "mistral": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["mistral-*", "pixtral-*"],
            "excluded_model_patterns": ["ministral-*"],
        },
        CapabilityType.VISION: {
            "vendor_name": "vision",
            "invocation_method": "message_content",
            "supported_model_patterns": ["pixtral-*"],
        },
        CapabilityType.STRUCTURED_OUTPUT: {
            "vendor_name": "json_mode",
            "invocation_method": "parameter",
            "api_config": {"param": "response_format", "type": "json_object"},
            "supported_model_patterns": ["mistral-*"],
        },
    },
    "cohere": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["command-r*"],
        },
        CapabilityType.WEB_SEARCH: {
            "vendor_name": "web-search",
            "invocation_method": "connector",
            "api_config": {"connector_id": "web-search"},
            "supported_model_patterns": ["command-r*"],
        },
    },
    "deepseek": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["deepseek-chat*", "deepseek-v3*"],
            "excluded_model_patterns": ["deepseek-r1*", "deepseek-reasoner*"],
        },
        CapabilityType.EXTENDED_THINKING: {
            "vendor_name": "reasoning",
            "invocation_method": "parameter",
            "supported_model_patterns": ["deepseek-r1*", "deepseek-reasoner*"],
        },
    },
    "xai": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["grok-*"],
        },
        CapabilityType.VISION: {
            "vendor_name": "vision",
            "invocation_method": "message_content",
            "supported_model_patterns": ["grok-*-vision*", "grok-3*"],
        },
        CapabilityType.WEB_SEARCH: {
            "vendor_name": "web_search",
            "invocation_method": "tool",
            "supported_model_patterns": ["grok-*"],
        },
    },
    "perplexity": {
        CapabilityType.WEB_SEARCH: {
            "vendor_name": "online_search",
            "invocation_method": "native",
            "supported_model_patterns": ["sonar*"],
            "notes": "Always-on web search for all Perplexity models",
        },
        CapabilityType.EXTENDED_THINKING: {
            "vendor_name": "reasoning",
            "invocation_method": "native",
            "supported_model_patterns": ["sonar-reasoning*"],
        },
    },
    "groq": {
        CapabilityType.FUNCTION_CALLING: {
            "vendor_name": "tools",
            "invocation_method": "parameter",
            "api_config": {"param": "tools"},
            "supported_model_patterns": ["*"],
            "excluded_model_patterns": ["whisper*", "deepseek-r1*"],
        },
    },
}
