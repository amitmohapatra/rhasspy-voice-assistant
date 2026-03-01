"""Tool registry for managing available tools."""

from __future__ import annotations

from typing import Any, Callable, Type
from dataclasses import dataclass


@dataclass
class ToolMetadata:
    """Metadata for a registered tool."""

    name: str
    description: str
    handler: Type["BaseTool"] | Callable
    schema: dict[str, Any]
    requires_auth: bool = True


class ToolRegistry:
    """Central registry for all available tools."""

    _instance: "ToolRegistry | None" = None
    _tools: dict[str, ToolMetadata] = {}

    def __new__(cls) -> "ToolRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._tools = {}
        return cls._instance

    def register(
        self,
        name: str,
        description: str,
        schema: dict[str, Any],
        handler: Type["BaseTool"] | Callable,
        requires_auth: bool = True,
    ) -> None:
        """Register a tool.

        Args:
            name: Unique tool name
            description: Tool description
            schema: OpenAI function calling schema
            handler: Tool handler class or function
            requires_auth: Whether tool requires authentication
        """
        self._tools[name] = ToolMetadata(
            name=name,
            description=description,
            handler=handler,
            schema=schema,
            requires_auth=requires_auth,
        )

    def get(self, name: str) -> ToolMetadata | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list(self) -> list[ToolMetadata]:
        """List all registered tools."""
        return list(self._tools.values())

    def list_names(self) -> list[str]:
        """List all tool names."""
        return list(self._tools.keys())

    def get_schema(self, name: str) -> dict[str, Any] | None:
        """Get schema for a tool."""
        tool = self._tools.get(name)
        return tool.schema if tool else None

    def get_all_schemas(self, tool_names: list[str] | None = None) -> list[dict]:
        """Get schemas for specified tools or all tools."""
        if tool_names:
            return [
                {"type": "function", "function": tool.schema}
                for name, tool in self._tools.items()
                if name in tool_names
            ]
        return [
            {"type": "function", "function": tool.schema}
            for tool in self._tools.values()
        ]


# Global registry instance
_registry = ToolRegistry()


def register_tool(
    name: str,
    description: str,
    schema: dict[str, Any],
    requires_auth: bool = True,
) -> Callable:
    """Decorator to register a tool.

    Usage:
        @register_tool(
            name="get_weather",
            description="Get weather for a location",
            schema={
                "name": "get_weather",
                "description": "Get weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"}
                    },
                    "required": ["location"]
                }
            }
        )
        class GetWeatherTool(BaseTool):
            async def execute(self, location: str) -> str:
                ...
    """

    def decorator(cls: Type["BaseTool"]) -> Type["BaseTool"]:
        _registry.register(
            name=name,
            description=description,
            schema=schema,
            handler=cls,
            requires_auth=requires_auth,
        )
        return cls

    return decorator


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _registry


# Alias for backward compatibility
tool_registry = _registry


class BaseTool:
    """Base class for tools."""

    name: str = "base_tool"
    description: str = "Base tool"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool."""
        raise NotImplementedError

    async def validate(self, **kwargs: Any) -> bool:
        """Validate tool inputs."""
        return True

    def get_schema(self) -> dict[str, Any]:
        """Get tool schema."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "object", "properties": {}},
        }
