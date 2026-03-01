"""Tool schemas with comprehensive Swagger documentation."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin
from src.schemas.enums import ToolType, ToolExecutionStatus


class ToolCreate(BaseSchema):
    """Schema for creating a new custom tool.

    Tools extend the assistant's capabilities with custom functions,
    API integrations, or MCP (Model Context Protocol) connections.
    """

    type: ToolType = Field(
        default=ToolType.FUNCTION,
        description="Type of tool: function, api, mcp, or builtin.",
        json_schema_extra={"example": "function"}
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique name for the tool.",
        json_schema_extra={"example": "get_weather"}
    )
    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Human-readable display name.",
        json_schema_extra={"example": "Get Weather"}
    )
    description: str | None = Field(
        default=None,
        description="Description of what the tool does. Used by the LLM to decide when to use the tool.",
        json_schema_extra={"example": "Get the current weather for a given location."}
    )
    category: str = Field(
        default="custom",
        description="Tool category for grouping in UI.",
        json_schema_extra={"example": "custom"}
    )
    icon: str | None = Field(
        default=None,
        max_length=50,
        description="Icon name for UI display.",
        json_schema_extra={"example": "cloud"}
    )
    schema_definition: dict = Field(
        ...,
        description="JSON Schema defining the tool's input parameters (OpenAI function calling format).",
        json_schema_extra={
            "example": {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a location",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name or coordinates"
                            }
                        },
                        "required": ["location"]
                    }
                }
            }
        }
    )
    implementation: dict = Field(
        default_factory=dict,
        description="Tool implementation config: handler type, endpoint, code, etc.",
        json_schema_extra={
            "example": {
                "handler": "http",
                "method": "GET",
                "url": "https://api.weather.com/v1/current",
                "headers": {"X-API-Key": "{{WEATHER_API_KEY}}"}
            }
        }
    )
    required_secrets: list[str] = Field(
        default_factory=list,
        description="List of secret keys required by this tool.",
        json_schema_extra={"example": ["WEATHER_API_KEY"]}
    )
    mcp_config: dict | None = Field(
        default=None,
        description="MCP server configuration (for MCP tools only).",
        json_schema_extra={
            "example": {
                "server_url": "http://localhost:3000",
                "transport": "http"
            }
        }
    )


class ToolUpdate(BaseSchema):
    """Schema for updating a tool.

    All fields are optional. Only provided fields will be updated.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated name.",
        json_schema_extra={"example": "get_weather_v2"}
    )
    display_name: str | None = Field(
        default=None,
        max_length=255,
        description="Updated display name.",
        json_schema_extra={"example": "Get Weather v2"}
    )
    description: str | None = Field(
        default=None,
        description="Updated description.",
        json_schema_extra={"example": "Get weather forecast for multiple days."}
    )
    category: str | None = Field(
        default=None,
        description="Updated category.",
        json_schema_extra={"example": "custom"}
    )
    icon: str | None = Field(
        default=None,
        max_length=50,
        description="Updated icon name.",
        json_schema_extra={"example": "cloud"}
    )
    schema_definition: dict | None = Field(
        default=None,
        description="Updated input schema.",
        json_schema_extra={"example": {"type": "object", "properties": {}}}
    )
    implementation: dict | None = Field(
        default=None,
        description="Updated implementation config.",
        json_schema_extra={"example": {"handler": "http", "url": "https://api.weather.com/v2"}}
    )
    required_secrets: list[str] | None = Field(
        default=None,
        description="Updated required secrets.",
        json_schema_extra={"example": ["WEATHER_API_KEY"]}
    )
    mcp_config: dict | None = Field(
        default=None,
        description="Updated MCP configuration.",
        json_schema_extra={"example": None}
    )
    is_active: bool | None = Field(
        default=None,
        description="Enable or disable the tool.",
        json_schema_extra={"example": True}
    )


class ToolResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for tool data in API responses."""

    type: str = Field(
        ...,
        description="Type of the tool.",
        json_schema_extra={"example": "custom"}
    )
    name: str = Field(
        ...,
        description="Name of the tool.",
        json_schema_extra={"example": "get_weather"}
    )
    display_name: str | None = Field(
        default=None,
        description="Display name of the tool.",
        json_schema_extra={"example": "Get Weather"}
    )
    description: str | None = Field(
        default=None,
        description="Tool description.",
        json_schema_extra={"example": "Get the current weather for a given location."}
    )
    category: str = Field(
        default="general",
        description="Tool category.",
        json_schema_extra={"example": "custom"}
    )
    icon: str | None = Field(
        default=None,
        description="Icon name.",
        json_schema_extra={"example": "cloud"}
    )
    schema_definition: dict = Field(
        ...,
        description="Input parameter schema.",
        json_schema_extra={
            "example": {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
                }
            }
        }
    )
    implementation: dict = Field(
        default_factory=dict,
        description="Implementation configuration.",
    )
    required_secrets: list[str] = Field(
        default_factory=list,
        description="Required secret keys.",
    )
    mcp_config: dict | None = Field(
        default=None,
        description="MCP configuration (if applicable).",
        json_schema_extra={"example": None}
    )
    is_active: bool = Field(
        ...,
        description="Whether the tool is active.",
        json_schema_extra={"example": True}
    )
    is_system: bool = Field(
        default=False,
        description="Whether this is a system-provided tool.",
    )


class ToolExecutionRequest(BaseSchema):
    """Schema for manually executing a tool."""

    tool_id: UUID = Field(
        ...,
        description="ID of the tool to execute.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    input: dict = Field(
        ...,
        description="Input parameters for the tool (must match tool's schema).",
        json_schema_extra={"example": {"location": "New York", "units": "imperial"}}
    )
    timeout: int = Field(
        default=30,
        ge=1,
        le=300,
        description="Execution timeout in seconds.",
        json_schema_extra={"example": 30}
    )


class ToolExecutionResponse(BaseSchema, IDMixin):
    """Schema for tool execution result."""

    tool_id: UUID = Field(
        ...,
        description="ID of the executed tool.",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    response_item_id: UUID | None = Field(
        default=None,
        description="ID of the response item that triggered this execution (if applicable).",
        json_schema_extra={"example": None}
    )
    input: dict = Field(
        ...,
        description="Input parameters that were used.",
        json_schema_extra={"example": {"location": "New York"}}
    )
    output: dict | None = Field(
        default=None,
        description="Tool execution output.",
        json_schema_extra={
            "example": {
                "temperature": 72,
                "condition": "Sunny",
                "humidity": 45
            }
        }
    )
    status: ToolExecutionStatus = Field(
        ...,
        description="Execution status.",
        json_schema_extra={"example": "completed"}
    )
    error_message: str | None = Field(
        default=None,
        description="Error message if execution failed.",
        json_schema_extra={"example": None}
    )
    execution_time_ms: int | None = Field(
        default=None,
        description="Execution time in milliseconds.",
        json_schema_extra={"example": 150}
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when execution started.",
        json_schema_extra={"example": "2024-01-15T10:30:00Z"}
    )


class ToolListResponse(BaseSchema):
    """Schema for paginated list of tools."""

    items: list[ToolResponse] = Field(
        default_factory=list,
        description="List of tools."
    )
    total: int = Field(
        ...,
        description="Total number of tools.",
        json_schema_extra={"example": 5}
    )


class AdhocToolTestRequest(BaseSchema):
    """Schema for testing a tool definition before creation."""

    implementation: dict = Field(
        ...,
        description="Tool implementation config to test.",
        json_schema_extra={
            "example": {
                "handler": "http",
                "method": "GET",
                "url": "https://api.example.com/test"
            }
        }
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Test input parameters.",
        json_schema_extra={"example": {"query": "test"}}
    )
    mcp_config: dict | None = Field(
        default=None,
        description="MCP config to test (for MCP tools).",
    )
