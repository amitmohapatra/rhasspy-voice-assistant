"""OpenAI LLM Provider using the Responses API.

This module implements the OpenAI provider using the new Responses API
which provides built-in tools like web search, file search, and code interpreter.

Responses API endpoint: POST /v1/responses
Documentation: https://platform.openai.com/docs/api-reference/responses
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from openai import AsyncOpenAI

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


class OpenAIProvider(LLMProvider):
    """OpenAI provider using the Responses API.

    The Responses API is OpenAI's latest API that combines:
    - Chat completions
    - Built-in tools (web search, file search, code interpreter)
    - Stateless operation (you manage conversation history)
    - Streaming support

    Capability Detection:
    - Primary: Query database via CapabilityService for model-specific capabilities
    - Fallback: Use pattern matching from vendor_capability_mappings in DB
    - Last resort: Use DEFAULT_VENDOR_MAPPINGS patterns (defined in capability.py)
    """

    provider_name = "openai"

    # Pattern-based capability mappings (fallback when DB not available)
    # These mirror DEFAULT_VENDOR_MAPPINGS in capability.py but are used
    # for quick in-memory checks when DB session isn't available.
    # The DB is the source of truth - these are just fallbacks.
    CAPABILITY_PATTERNS = {
        "function_calling": {
            "supported": ["gpt-*"],
            "excluded": [],  # Reasoning models (o1*, o3*) don't support standard tools
        },
        "web_search": {
            "supported": ["gpt-4o*", "gpt-4.1*"],
            "excluded": [],
        },
        "vision": {
            "supported": ["gpt-4o*", "gpt-4-turbo*", "gpt-4-vision*"],
            "excluded": [],
        },
        "extended_thinking": {
            "supported": ["o1*", "o3*"],
            "excluded": [],
        },
        "code_interpreter": {
            "supported": ["gpt-4*", "gpt-3.5*"],
            "excluded": [],
        },
        "file_search": {
            "supported": ["gpt-4*", "gpt-3.5*"],
            "excluded": [],
        },
    }

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.base_url = base_url or settings.openai_base_url or "https://api.openai.com/v1"

        if not self.api_key:
            raise LLMError("OpenAI API key not configured", provider="openai")

        # AsyncOpenAI client for embeddings (Responses API doesn't do embeddings)
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url if self.base_url != "https://api.openai.com/v1" else None,
        )

    @handle_provider_errors("openai", "completion")
    @measure_execution_time("openai_completion")
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion using Responses API."""
        return await self._call_responses_api(request, stream=False)

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion using Responses API."""
        async for delta in self._stream_responses_api(request):
            yield delta

    async def _call_responses_api(
        self,
        request: CompletionRequest,
        stream: bool = False,
    ) -> CompletionResponse:
        """Call the OpenAI Responses API (non-streaming)."""

        # Build the request payload
        payload = self._build_responses_payload(request, stream=False)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120.0,
            )

            if response.status_code != 200:
                error_data = response.json() if response.content else {}
                raise LLMError(
                    message=f"OpenAI Responses API error: {error_data.get('error', {}).get('message', response.text)}",
                    provider="openai",
                    details={"status_code": response.status_code, "error": error_data},
                )

            data = response.json()

            # Extract response content
            output = data.get("output", [])
            content = ""
            tool_calls = []

            for item in output:
                if item.get("type") == "message":
                    for content_item in item.get("content", []):
                        if content_item.get("type") == "output_text":
                            content += content_item.get("text", "")
                        elif content_item.get("type") == "refusal":
                            content += f"[Refusal: {content_item.get('refusal', '')}]"

                elif item.get("type") == "function_call":
                    tool_calls.append(ToolCall(
                        id=item.get("call_id", ""),
                        name=item.get("name", ""),
                        arguments=item.get("arguments", "{}"),
                    ))

                elif item.get("type") == "web_search_call":
                    # Web search was performed - results are in the context
                    pass

            # Extract usage
            usage = data.get("usage", {})

            return CompletionResponse(
                content=content,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=data.get("status", "completed"),
                input_tokens=usage.get("input_tokens", 0),
                output_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                model=data.get("model", request.model),
            )

    async def _stream_responses_api(
        self,
        request: CompletionRequest,
    ) -> AsyncGenerator[StreamDelta, None]:
        """Stream from the OpenAI Responses API."""

        payload = self._build_responses_payload(request, stream=True)

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=120.0,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise LLMError(
                        message=f"OpenAI Responses API streaming error: {error_text.decode()}",
                        provider="openai",
                    )

                current_tool_call = None

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data_str = line[6:]  # Remove "data: " prefix

                    if data_str == "[DONE]":
                        if current_tool_call:
                            yield StreamDelta(type="tool_call", tool_call=current_tool_call)
                        yield StreamDelta(type="finish", finish_reason="stop")
                        break

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type", "")

                    # Handle different event types
                    if event_type == "response.output_text.delta":
                        # Text content delta
                        delta_text = event.get("delta", "")
                        if delta_text:
                            yield StreamDelta(type="text", content=delta_text)

                    elif event_type == "response.output_text.done":
                        # Text content complete
                        pass

                    elif event_type == "response.output_item.added":
                        # New output item — capture function_call name early
                        item = event.get("item", {})
                        if item.get("type") == "function_call":
                            current_tool_call = ToolCall(
                                id=item.get("call_id", ""),
                                name=item.get("name", ""),
                                arguments="",
                            )

                    elif event_type == "response.function_call_arguments.delta":
                        # Function call arguments streaming
                        if current_tool_call is None:
                            current_tool_call = ToolCall(
                                id=event.get("call_id", ""),
                                name=event.get("name", ""),
                                arguments="",
                            )
                        current_tool_call.arguments += event.get("delta", "")

                    elif event_type == "response.function_call_arguments.done":
                        # Function call complete — done event has name + full arguments
                        if current_tool_call is None:
                            current_tool_call = ToolCall(
                                id=event.get("call_id", ""),
                                name=event.get("name", ""),
                                arguments=event.get("arguments", ""),
                            )
                        else:
                            done_name = event.get("name", "")
                            if done_name:
                                current_tool_call.name = done_name
                            done_args = event.get("arguments")
                            if done_args is not None:
                                current_tool_call.arguments = done_args
                        yield StreamDelta(type="tool_call", tool_call=current_tool_call)
                        current_tool_call = None

                    elif event_type == "response.web_search_call.searching":
                        # Web search in progress
                        yield StreamDelta(
                            type="status",
                            content="Searching the web..."
                        )

                    elif event_type == "response.web_search_call.completed":
                        # Web search completed
                        yield StreamDelta(
                            type="status",
                            content="Web search completed"
                        )

                    elif event_type == "response.completed":
                        # Response complete - extract usage
                        response_data = event.get("response", {})
                        usage = response_data.get("usage", {})
                        yield StreamDelta(
                            type="finish",
                            finish_reason="stop",
                            input_tokens=usage.get("input_tokens", 0),
                            output_tokens=usage.get("output_tokens", 0),
                        )

                    elif event_type == "error":
                        error = event.get("error", {})
                        raise LLMError(
                            message=f"OpenAI streaming error: {error.get('message', 'Unknown error')}",
                            provider="openai",
                        )

    def _build_responses_payload(
        self,
        request: CompletionRequest,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Build the Responses API request payload."""

        # Convert messages to Responses API format
        # Messages can be Message objects (Pydantic) or dicts
        input_messages = []

        for msg in request.messages:
            # Handle both Message objects and dicts
            if hasattr(msg, 'role'):
                role = msg.role
                content = msg.content or ""
                tool_call_id = getattr(msg, 'tool_call_id', None)
            else:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                tool_call_id = msg.get("tool_call_id")

            if role == "system":
                # System messages become instructions or first user message
                input_messages.append({
                    "role": "user",
                    "content": f"[System Instructions]\n{content}"
                })
            elif role == "user":
                input_messages.append({
                    "role": "user",
                    "content": content
                })
            elif role == "assistant":
                input_messages.append({
                    "role": "assistant",
                    "content": content
                })
            elif role == "tool":
                # Tool results
                input_messages.append({
                    "role": "user",
                    "content": f"[Tool Result: {tool_call_id or ''}]\n{content}"
                })

        payload: dict[str, Any] = {
            "model": request.model,
            "input": input_messages,
        }

        # Add generation parameters
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        if request.max_tokens is not None:
            payload["max_output_tokens"] = request.max_tokens

        if request.top_p is not None:
            payload["top_p"] = request.top_p

        # Add tools (already in Responses API format from ToolResolver)
        if request.tools:
            payload["tools"] = request.tools

        # Add tool choice if specified
        if request.tool_choice:
            payload["tool_choice"] = request.tool_choice

        # Enable streaming
        if stream:
            payload["stream"] = True

        # Add instructions (system prompt) if present
        system_content = ""
        for msg in request.messages:
            # Handle both Message objects and dicts
            msg_role = msg.role if hasattr(msg, 'role') else msg.get("role")
            msg_content = msg.content if hasattr(msg, 'content') else msg.get("content", "")

            if msg_role == "system":
                system_content += msg_content + "\n"

        if system_content.strip():
            payload["instructions"] = system_content.strip()
            # Remove system messages from input since we're using instructions
            payload["input"] = [
                msg for msg in input_messages
                if not msg.get("content", "").startswith("[System Instructions]")
            ]

        return payload

    @handle_provider_errors("openai", "embedding")
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings (still uses embeddings API)."""
        embedding_model = model or settings.default_embedding_model or "text-embedding-3-small"

        response = await self.client.embeddings.create(
            input=texts,
            model=embedding_model,
        )

        return [item.embedding for item in response.data]

    def list_models(self) -> list[str]:
        """List available models for Responses API."""
        return [
            # GPT-4o family (recommended for Responses API)
            "gpt-4o",            # Most capable, supports web search
            "gpt-4o-mini",       # Faster, cheaper, supports web search
            # GPT-4.1 family
            "gpt-4.1",           # Latest GPT-4 variant
            "gpt-4.1-mini",      # Smaller, faster
            "gpt-4.1-nano",      # Most efficient
            # GPT-4 Turbo
            "gpt-4-turbo",       # Fast GPT-4
            "gpt-4-turbo-preview",
            # GPT-4 & 3.5
            "gpt-4",             # Original GPT-4
            "gpt-3.5-turbo",     # Legacy, still supported
            # o-series reasoning models
            "o1",                # Full reasoning
            "o1-mini",           # Fast reasoning
            "o1-preview",        # Preview version
            "o3-mini",           # Latest reasoning
        ]

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

    def supports_web_search(self, model: str) -> bool:
        """Check if model supports built-in web search.

        Uses pattern matching from CAPABILITY_PATTERNS (fallback).
        For DB-driven checks, use check_capability_from_db() with a session.
        """
        patterns = self.CAPABILITY_PATTERNS.get("web_search", {})
        return self.model_matches_patterns(
            model,
            patterns.get("supported", []),
            patterns.get("excluded", []),
        )

    def is_reasoning_model(self, model: str) -> bool:
        """Check if model is a reasoning model with extended thinking.

        Uses pattern matching from CAPABILITY_PATTERNS.
        """
        patterns = self.CAPABILITY_PATTERNS.get("extended_thinking", {})
        return self.model_matches_patterns(
            model,
            patterns.get("supported", []),
            patterns.get("excluded", []),
        )


# Helper function to create a completion with web search enabled
async def complete_with_web_search(
    messages: list[dict],
    model: str = "gpt-4o",
    api_key: str | None = None,
) -> CompletionResponse:
    """Convenience function to complete with web search enabled.

    Example:
        response = await complete_with_web_search(
            messages=[{"role": "user", "content": "What's the latest news about AI?"}],
            model="gpt-4o",
        )
    """
    provider = OpenAIProvider(api_key=api_key)

    request = CompletionRequest(
        model=model,
        messages=messages,
        tools=[{"type": "web_search"}],
    )

    return await provider.complete(request)
