"""Tool Adapters - Convert tools to provider-native formats.

Each adapter implements the Strategy pattern to convert builtin and custom
tool definitions into the specific format required by each LLM provider's API.

The ToolAdapterRegistry maps provider names to adapter instances using the
Registry pattern, enabling O(1) lookup and easy extensibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ToolAdapter(ABC):
    """Abstract base for converting tools to provider-native format."""

    @abstractmethod
    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        """Convert a builtin tool to provider-native format.

        Args:
            name: Builtin tool name (e.g. "web_search", "code_interpreter")
            api_config: Provider-specific API config from builtin_tools table
            default_config: Default configuration from builtin_tools table

        Returns:
            Provider-native tool dict, or None to skip this tool.
        """

    @abstractmethod
    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        """Convert a custom tool schema to provider-native format.

        Args:
            name: Tool function name
            description: Tool description
            parameters: JSON Schema parameters dict

        Returns:
            Provider-native tool dict.
        """


# ==================== Concrete Adapters ====================


class OpenAIResponsesAdapter(ToolAdapter):
    """OpenAI Responses API format.

    Builtins: {"type": "web_search_preview"} or {"type": "file_search"} etc.
    Custom: {"type": "function", "name": ..., "parameters": ...} (flat format)
    """

    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        # api_config stores tool_type; Responses API needs "type" key
        if api_config:
            config = dict(api_config)
            if "tool_type" in config:
                config["type"] = config.pop("tool_type")
            return config
        # Fallback: pass the name as the type
        return {"type": name}

    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        # Responses API uses flat format (not nested under "function")
        tool: dict[str, Any] = {
            "type": "function",
            "name": name,
            "parameters": parameters,
        }
        if description:
            tool["description"] = description
        return tool


class ChatCompletionsAdapter(ToolAdapter):
    """OpenAI Chat Completions format (shared by Azure, Groq, Together, Fireworks, etc.).

    Builtins: Skipped (these providers don't support native builtin tools).
    Custom: {"type": "function", "function": {"name": ..., "parameters": ...}}
    """

    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        # Chat Completions API providers don't support builtin tools
        return None

    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        func: dict[str, Any] = {
            "name": name,
            "parameters": parameters,
        }
        if description:
            func["description"] = description
        return {"type": "function", "function": func}


class AnthropicAdapter(ToolAdapter):
    """Anthropic Claude format.

    Builtins: Varies per tool (e.g. computer_use has specific schema).
    Custom: {"name": ..., "description": ..., "input_schema": ...}
    """

    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        if api_config:
            return dict(api_config)
        return {"type": name}

    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        return {
            "name": name,
            "description": description or "",
            "input_schema": parameters or {"type": "object", "properties": {}},
        }


class GoogleAdapter(ToolAdapter):
    """Google Gemini format.

    Builtins: {"google_search": {}} or {"code_execution": {}}.
    Custom: {"function_declarations": [{"name": ..., "parameters": ...}]}
    """

    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        if api_config:
            return dict(api_config)
        # Fallback mapping for common builtins
        mapping = {
            "google_search": {"google_search": {}},
            "code_execution": {"code_execution": {}},
        }
        return mapping.get(name)

    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        decl: dict[str, Any] = {
            "name": name,
            "parameters": parameters or {"type": "object", "properties": {}},
        }
        if description:
            decl["description"] = description
        return {"function_declarations": [decl]}


class BedrockAdapter(ToolAdapter):
    """AWS Bedrock Converse API format.

    Builtins: Skipped (Bedrock doesn't have native builtin tools).
    Custom: {"toolSpec": {"name": ..., "inputSchema": {"json": ...}}}
    """

    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        return None

    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        spec: dict[str, Any] = {
            "name": name,
            "inputSchema": {
                "json": parameters or {"type": "object", "properties": {}},
            },
        }
        if description:
            spec["description"] = description
        return {"toolSpec": spec}


class CohereAdapter(ToolAdapter):
    """Cohere Command format.

    Builtins: Converted to connectors (separate API param) or skipped.
    Custom: {"name": ..., "description": ..., "parameter_definitions": {...}}
    """

    def convert_builtin(
        self, name: str, api_config: dict, default_config: dict | None
    ) -> dict | None:
        # Cohere builtins are handled as connectors, not tools.
        # Return a special marker that ToolResolver will route to connectors.
        if api_config:
            return {"__cohere_connector__": True, **api_config}
        # Default web-search connector
        if name in ("web_search", "rag_search"):
            return {"__cohere_connector__": True, "id": name.replace("_", "-")}
        return None

    def convert_custom(
        self, name: str, description: str, parameters: dict
    ) -> dict:
        parameter_definitions: dict[str, Any] = {}
        if "properties" in parameters:
            required_fields = set(parameters.get("required", []))
            for prop_name, prop in parameters["properties"].items():
                parameter_definitions[prop_name] = {
                    "description": prop.get("description", ""),
                    "type": prop.get("type", "string"),
                    "required": prop_name in required_fields,
                }
        return {
            "name": name,
            "description": description or "",
            "parameter_definitions": parameter_definitions,
        }


# ==================== Registry ====================


class ToolAdapterRegistry:
    """Singleton registry mapping provider names to ToolAdapter instances."""

    _instance: ToolAdapterRegistry | None = None

    PROVIDER_ADAPTER_MAP: dict[str, type[ToolAdapter]] = {
        "openai": OpenAIResponsesAdapter,
        "anthropic": AnthropicAdapter,
        "google": GoogleAdapter,
        "bedrock": BedrockAdapter,
        "cohere": CohereAdapter,
        # Chat Completions providers
        "azure": ChatCompletionsAdapter,
        "azure_openai": ChatCompletionsAdapter,
        "groq": ChatCompletionsAdapter,
        "together": ChatCompletionsAdapter,
        "fireworks": ChatCompletionsAdapter,
        "mistral": ChatCompletionsAdapter,
        "ollama": ChatCompletionsAdapter,
        "deepseek": ChatCompletionsAdapter,
        "xai": ChatCompletionsAdapter,
        "perplexity": ChatCompletionsAdapter,
    }

    def __new__(cls) -> ToolAdapterRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._adapters = {}
        return cls._instance

    def get(self, provider: str) -> ToolAdapter:
        """Get adapter for a provider, creating it lazily."""
        if provider not in self._adapters:
            adapter_cls = self.PROVIDER_ADAPTER_MAP.get(provider)
            if adapter_cls is None:
                # Default to Chat Completions format for unknown providers
                adapter_cls = ChatCompletionsAdapter
            self._adapters[provider] = adapter_cls()
        return self._adapters[provider]

    def register(self, provider: str, adapter: ToolAdapter) -> None:
        """Register a custom adapter for a provider."""
        self._adapters[provider] = adapter
