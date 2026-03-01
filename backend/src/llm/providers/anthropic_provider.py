"""Anthropic Claude LLM Provider.

This module implements the Anthropic Claude provider using reusable
utilities for consistent behavior and reduced code duplication.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.llm.providers.base import Message

from anthropic import AsyncAnthropic

from src.core.config import settings
from src.core.decorators import handle_provider_errors, measure_execution_time
from src.core.exceptions import LLMError
from src.llm.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    StreamDelta,
    ToolCall,
)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider.

    Capability Detection:
    - Primary: Query database via CapabilityService for model-specific capabilities
    - Fallback: Use pattern matching from CAPABILITY_PATTERNS
    - The DB is the source of truth - patterns are just fallbacks.
    """

    provider_name = "anthropic"

    # Pattern-based capability mappings (fallback when DB not available)
    # These mirror DEFAULT_VENDOR_MAPPINGS in capability.py
    CAPABILITY_PATTERNS = {
        "function_calling": {
            "supported": ["claude-*"],  # All Claude models support tools
            "excluded": [],
        },
        "vision": {
            "supported": ["claude-3*", "claude-*-4*"],  # Claude 3.x and 4.x
            "excluded": [],
        },
        "extended_thinking": {
            "supported": ["claude-*-4.5-*", "claude-*-4-5-*"],  # 4.5 models
            "excluded": [],
        },
        "computer_use": {
            "supported": ["claude-3-5-sonnet*", "claude-*-4*"],
            "excluded": [],
        },
        "artifacts": {
            "supported": ["claude-*"],  # All Claude models
            "excluded": [],
        },
    }

    # Model aliases for convenience
    MODEL_ALIASES = {
        "claude-opus-4.5": "claude-opus-4-5-20251101",
        "claude-opus-4.1": "claude-opus-4-1-20250805",
        "claude-opus-4": "claude-opus-4-20250522",
        "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
        "claude-sonnet-4": "claude-sonnet-4-20250522",
        "claude-haiku-4.5": "claude-haiku-4-5-20251015",
        "claude-3.5-sonnet": "claude-3-5-sonnet-20241022",
        "claude-3.5-haiku": "claude-3-5-haiku-20241022",
        "claude-3-opus": "claude-3-opus-20240229",
    }

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.anthropic_api_key

        if not self.api_key:
            raise LLMError("Anthropic API key not configured", provider="anthropic")

        self.client = AsyncAnthropic(api_key=self.api_key)

    @handle_provider_errors("anthropic", "completion")
    @measure_execution_time("anthropic_completion")
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        # Extract system prompt using base class helper
        system_prompt = self._extract_system_prompt(request.messages)
        messages = self._format_messages(request.messages)

        # Build request params
        params: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if system_prompt:
            params["system"] = system_prompt

        # Add tools (already in Anthropic-native format from ToolResolver)
        if request.tools and self.supports_tools(request.model):
            params["tools"] = request.tools

        response = await self.client.messages.create(**params)

        # Extract content and tool calls
        content = ""
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        type="function",
                        function={
                            "name": block.name,
                            "arguments": (
                                block.input
                                if isinstance(block.input, str)
                                else str(block.input)
                            ),
                        },
                    )
                )

        return CompletionResponse(
            content=content if content else None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=response.stop_reason or "stop",
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.input_tokens + response.usage.output_tokens,
            model=response.model,
        )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        # Extract system prompt using base class helper
        system_prompt = self._extract_system_prompt(request.messages)
        messages = self._format_messages(request.messages)

        # Build request params
        params: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "top_p": request.top_p,
        }

        if system_prompt:
            params["system"] = system_prompt

        # Add tools (already in Anthropic-native format from ToolResolver)
        if request.tools and self.supports_tools(request.model):
            params["tools"] = request.tools

        try:
            async with self.client.messages.stream(**params) as stream:
                current_tool_call: dict | None = None

                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "tool_use":
                            current_tool_call = {
                                "id": event.content_block.id,
                                "type": "function",
                                "function": {
                                    "name": event.content_block.name,
                                    "arguments": "",
                                },
                            }

                    elif event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            yield StreamDelta(type="text", content=event.delta.text)
                        elif (
                            event.delta.type == "input_json_delta"
                            and current_tool_call
                        ):
                            current_tool_call["function"]["arguments"] += (
                                event.delta.partial_json
                            )

                    elif event.type == "content_block_stop":
                        if current_tool_call:
                            yield StreamDelta(
                                type="tool_call",
                                tool_call=ToolCall(**current_tool_call),
                            )
                            current_tool_call = None

                    elif event.type == "message_delta":
                        if event.usage:
                            yield StreamDelta(
                                type="finish",
                                finish_reason=event.delta.stop_reason or "stop",
                                output_tokens=event.usage.output_tokens,
                            )

                # Get final message for input tokens
                final_message = await stream.get_final_message()
                yield StreamDelta(
                    type="finish",
                    finish_reason="stop",
                    input_tokens=final_message.usage.input_tokens,
                    output_tokens=final_message.usage.output_tokens,
                )

        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                message=f"Anthropic streaming failed: {str(e)}",
                provider="anthropic",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings - Anthropic doesn't have embedding models.
        Fall back to OpenAI or raise error."""
        raise LLMError(
            message="Anthropic does not support embeddings. Use OpenAI instead.",
            provider="anthropic",
        )

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Claude Opus 4.x (most intelligent - industry leader)
            "claude-opus-4-5-20251101",      # Latest flagship - Nov 2025
            "claude-opus-4-1-20250805",      # Improved code/search - Aug 2025
            "claude-opus-4-20250522",        # Base Opus 4 - May 2025
            # Claude Sonnet 4.x (best coding/agents)
            "claude-sonnet-4-5-20250929",    # Best coding model - Sep 2025
            "claude-sonnet-4-20250522",      # Base Sonnet 4 - May 2025
            # Claude Haiku 4.x (near-frontier at low cost)
            "claude-haiku-4-5-20251015",     # Fast, cheap - Oct 2025
            # Legacy Claude 3.x (deprecated)
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",        # Deprecated
            "claude-3-haiku-20240307",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling.

        Uses pattern matching from CAPABILITY_PATTERNS (fallback).
        For DB-driven checks, use check_capability_from_db() with a session.
        """
        patterns = self.CAPABILITY_PATTERNS.get("function_calling", {})
        return self.model_matches_patterns(
            model,
            patterns.get("supported", ["*"]),
            patterns.get("excluded", []),
        )

    def is_reasoning_model(self, model: str) -> bool:
        """Check if model supports extended thinking (hybrid reasoning).

        Uses pattern matching from CAPABILITY_PATTERNS.
        """
        patterns = self.CAPABILITY_PATTERNS.get("extended_thinking", {})
        return self.model_matches_patterns(
            model,
            patterns.get("supported", []),
            patterns.get("excluded", []),
        )

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for Anthropic API."""
        formatted = []

        for msg in messages:
            # Skip system messages (handled separately)
            if msg.role == "system":
                continue

            formatted_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }

            # Handle tool results
            if msg.role == "user" and msg.tool_call_id:
                formatted_msg["content"] = [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                ]

            formatted.append(formatted_msg)

        return formatted

