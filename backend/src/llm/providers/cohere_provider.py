"""Cohere LLM Provider - Command R models with native RAG and tool use."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from src.core.config import settings
from src.core.exceptions import LLMError
from src.llm.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    Message,
    StreamDelta,
    ToolCall,
)


class CohereProvider(LLMProvider):
    """Cohere provider with Command R models optimized for RAG and tool use."""

    provider_name = "cohere"

    # Available models (as of late 2025)
    MODELS = {
        # Command A family (latest - March 2025)
        "command-a-03-2025": {"context": 256000, "tools": True, "params": "111B"},
        "command-a-reasoning": {"context": 256000, "tools": True, "reasoning": True},
        "command-a-vision": {"context": 256000, "tools": True, "vision": True},
        "command-a-translate-08-2025": {"context": 256000, "tools": False, "translate": True},
        # Command R+ (August 2024)
        "command-r-plus-08-2024": {"context": 128000, "tools": True},
        "command-r-plus": {"context": 128000, "tools": True},
        # Command R (August 2024)
        "command-r-08-2024": {"context": 128000, "tools": True},
        "command-r": {"context": 128000, "tools": True},
        # Command R7B (small, efficient)
        "command-r7b": {"context": 128000, "tools": True, "params": "7B"},
        # Legacy (deprecated as of Sep 2025)
        "command": {"context": 4096, "tools": False, "deprecated": True},
        "command-light": {"context": 4096, "tools": False, "deprecated": True},
        "command-nightly": {"context": 128000, "tools": True},
    }

    # Model aliases
    MODEL_ALIASES = {
        "command-a": "command-a-03-2025",
        "command-latest": "command-a-03-2025",
    }

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "cohere_api_key", None)

        if not self.api_key:
            raise LLMError("Cohere API key not configured", provider="cohere")

        try:
            import cohere
            self.client = cohere.AsyncClient(api_key=self.api_key)
        except ImportError:
            raise LLMError(
                "cohere package not installed. Run: pip install cohere",
                provider="cohere",
            )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        try:
            # Extract system prompt (preamble in Cohere)
            preamble = self._extract_system_prompt(request.messages)

            # Format chat history
            chat_history, message = self._format_messages(request.messages)

            params = {
                "model": request.model,
                "message": message,
                "chat_history": chat_history,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "p": request.top_p,
            }

            if preamble:
                params["preamble"] = preamble

            # Add tools (already in Cohere-native format from ToolResolver)
            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools

            # Add connectors (Cohere-specific: web search etc.)
            if request.connectors:
                params["connectors"] = request.connectors

            response = await self.client.chat(**params)

            # Extract tool calls
            tool_calls = None
            if response.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=f"call_{i}",
                        type="function",
                        function={
                            "name": tc.name,
                            "arguments": json.dumps(tc.parameters),
                        },
                    )
                    for i, tc in enumerate(response.tool_calls)
                ]

            # Determine finish reason
            finish_reason = "stop"
            if response.finish_reason:
                finish_reason = response.finish_reason.lower()
            if tool_calls:
                finish_reason = "tool_calls"

            # Get usage from metadata
            input_tokens = 0
            output_tokens = 0
            if response.meta and response.meta.tokens:
                input_tokens = response.meta.tokens.input_tokens or 0
                output_tokens = response.meta.tokens.output_tokens or 0

            return CompletionResponse(
                content=response.text,
                tool_calls=tool_calls,
                finish_reason=finish_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                model=request.model,
            )

        except Exception as e:
            raise LLMError(
                message=f"Cohere completion failed: {str(e)}",
                provider="cohere",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        try:
            preamble = self._extract_system_prompt(request.messages)
            chat_history, message = self._format_messages(request.messages)

            params = {
                "model": request.model,
                "message": message,
                "chat_history": chat_history,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "p": request.top_p,
            }

            if preamble:
                params["preamble"] = preamble

            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools

            # Add connectors (Cohere-specific: web search etc.)
            if request.connectors:
                params["connectors"] = request.connectors

            stream = self.client.chat_stream(**params)

            input_tokens = 0
            output_tokens = 0
            tool_calls = []

            async for event in stream:
                if event.event_type == "text-generation":
                    yield StreamDelta(type="text", content=event.text)

                elif event.event_type == "tool-calls-chunk":
                    # Tool calls come in chunks in Cohere
                    pass

                elif event.event_type == "tool-calls-generation":
                    if event.tool_calls:
                        for i, tc in enumerate(event.tool_calls):
                            tool_call = ToolCall(
                                id=f"call_{len(tool_calls)}",
                                type="function",
                                function={
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.parameters),
                                },
                            )
                            tool_calls.append(tool_call)
                            yield StreamDelta(type="tool_call", tool_call=tool_call)

                elif event.event_type == "stream-end":
                    if event.response and event.response.meta:
                        if event.response.meta.tokens:
                            input_tokens = event.response.meta.tokens.input_tokens or 0
                            output_tokens = event.response.meta.tokens.output_tokens or 0

                    finish_reason = "stop"
                    if event.finish_reason:
                        finish_reason = event.finish_reason.lower()

                    yield StreamDelta(
                        type="finish",
                        finish_reason=finish_reason,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

        except Exception as e:
            raise LLMError(
                message=f"Cohere streaming failed: {str(e)}",
                provider="cohere",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Cohere embed models."""
        try:
            model_name = model or "embed-english-v3.0"

            response = await self.client.embed(
                texts=texts,
                model=model_name,
                input_type="search_document",
            )

            return response.embeddings

        except Exception as e:
            raise LLMError(
                message=f"Cohere embedding failed: {str(e)}",
                provider="cohere",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Command A family (latest - Mar 2025)
            "command-a-03-2025",        # Flagship, 111B params
            "command-a-reasoning",      # Chain-of-thought reasoning
            "command-a-vision",         # Vision + text
            "command-a-translate-08-2025",  # Translation
            # Command R+
            "command-r-plus-08-2024",   # Strong RAG/tool use
            "command-r-plus",
            # Command R
            "command-r-08-2024",        # Improved multilingual
            "command-r",
            # Command R7B
            "command-r7b",              # Small, efficient
            # Nightly
            "command-nightly",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        return "command-r" in model

    def _format_messages(self, messages: list[Message]) -> tuple[list[dict], str]:
        """Format messages for Cohere API.

        Returns:
            Tuple of (chat_history, current_message)
        """
        chat_history = []
        current_message = ""

        # Filter out system messages
        filtered = [m for m in messages if m.role != "system"]

        # Last user message is the current message
        for i, msg in enumerate(filtered):
            if i == len(filtered) - 1 and msg.role == "user":
                current_message = msg.content
            else:
                role = "USER" if msg.role == "user" else "CHATBOT"

                if msg.role == "tool":
                    # Tool results in Cohere format
                    chat_history.append({
                        "role": "TOOL",
                        "tool_results": [{
                            "call": {"name": msg.name or "function"},
                            "outputs": [{"result": msg.content}],
                        }],
                    })
                else:
                    chat_history.append({
                        "role": role,
                        "message": msg.content,
                    })

        return chat_history, current_message

