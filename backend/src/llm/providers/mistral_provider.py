"""Mistral AI LLM Provider - European AI with strong multilingual support."""

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


class MistralProvider(LLMProvider):
    """Mistral AI provider for high-performance European LLMs."""

    provider_name = "mistral"

    # Available models (as of late 2025)
    MODELS = {
        # Mistral Large 3 - flagship (Dec 2025)
        "mistral-large-3": {"context": 256000, "tools": True, "moe": True},
        "mistral-large-latest": {"context": 256000, "tools": True},
        "mistral-large-2411": {"context": 128000, "tools": True},
        # Mistral Medium 3.x
        "mistral-medium-3.1": {"context": 128000, "tools": True},
        "mistral-medium-3": {"context": 128000, "tools": True},
        # Mistral Small 3.x
        "mistral-small-3.2": {"context": 128000, "tools": True},
        "mistral-small-3.1": {"context": 128000, "tools": True},
        "mistral-small-latest": {"context": 32000, "tools": True},
        # Ministral (small, dense models - Dec 2025)
        "ministral-3-14b": {"context": 128000, "tools": True},
        "ministral-3-7b": {"context": 128000, "tools": True},
        "ministral-3-3b": {"context": 128000, "tools": True},
        "ministral-8b-latest": {"context": 128000, "tools": True},
        "ministral-3b-latest": {"context": 128000, "tools": True},
        # Codestral - coding models
        "codestral-2508": {"context": 32000, "tools": True},
        "codestral-2501": {"context": 32000, "tools": True},
        "codestral-latest": {"context": 32000, "tools": True},
        # Devstral - dev/agent models (Dec 2025)
        "devstral-2": {"context": 128000, "tools": True},
        "devstral-small-2": {"context": 128000, "tools": True},
        # Magistral - reasoning models (June-July 2025)
        "magistral-medium-1.1": {"context": 128000, "tools": True, "reasoning": True},
        "magistral-small-1.1": {"context": 128000, "tools": True, "reasoning": True},
        "magistral-medium": {"context": 128000, "tools": True, "reasoning": True},
        "magistral-small": {"context": 128000, "tools": True, "reasoning": True},
        # Pixtral - vision models
        "pixtral-large-latest": {"context": 128000, "tools": True, "vision": True},
        # Voxtral - audio models
        "voxtral-small-2507": {"context": 32000, "tools": False, "audio": True},
        "voxtral-mini-2507": {"context": 32000, "tools": False, "audio": True},
        # Embeddings
        "mistral-embed": {"context": 8000, "tools": False, "embedding": True},
        "mistral-codestral-embed": {"context": 32000, "tools": False, "embedding": True},
        # Moderation
        "mistral-moderation-latest": {"context": 8000, "tools": False},
        # OCR
        "mistral-ocr-2505": {"context": 8000, "tools": False, "ocr": True},
        # Open-weight models
        "open-mistral-nemo": {"context": 128000, "tools": True},
        "open-codestral-mamba": {"context": 256000, "tools": False},
        "open-mixtral-8x7b": {"context": 32000, "tools": True},
        "open-mixtral-8x22b": {"context": 64000, "tools": True},
    }

    # Model aliases
    MODEL_ALIASES = {
        "mistral-large": "mistral-large-3",
        "mistral-medium": "mistral-medium-3.1",
        "mistral-small": "mistral-small-3.2",
        "codestral": "codestral-2508",
        "devstral": "devstral-2",
        "magistral": "magistral-medium-1.1",
    }

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "mistral_api_key", None)
        self.endpoint = endpoint or "https://api.mistral.ai/v1"

        if not self.api_key:
            raise LLMError("Mistral API key not configured", provider="mistral")

        try:
            from mistralai import Mistral
            self.client = Mistral(api_key=self.api_key)
        except ImportError:
            raise LLMError(
                "mistralai package not installed. Run: pip install mistralai",
                provider="mistral",
            )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        try:
            messages = self._format_messages(request.messages)

            params = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
            }

            # Add tools (already in Chat Completions format from ToolResolver)
            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools
                if request.tool_choice:
                    params["tool_choice"] = request.tool_choice

            response = await self.client.chat.complete_async(**params)

            choice = response.choices[0]
            message = choice.message

            # Extract tool calls
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type="function",
                        function={
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    )
                    for tc in message.tool_calls
                ]

            return CompletionResponse(
                content=message.content,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason or "stop",
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
                model=response.model,
            )

        except Exception as e:
            raise LLMError(
                message=f"Mistral completion failed: {str(e)}",
                provider="mistral",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        try:
            messages = self._format_messages(request.messages)

            params = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
            }

            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools
                if request.tool_choice:
                    params["tool_choice"] = request.tool_choice

            stream = await self.client.chat.stream_async(**params)

            current_tool_calls: dict[int, dict] = {}
            input_tokens = 0
            output_tokens = 0

            async for event in stream:
                chunk = event.data
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Handle text content
                if delta.content:
                    yield StreamDelta(type="text", content=delta.content)

                # Handle tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index if hasattr(tc_delta, "index") else 0

                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc_delta.id or f"call_{idx}",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            }

                        if tc_delta.id:
                            current_tool_calls[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                current_tool_calls[idx]["function"]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                current_tool_calls[idx]["function"]["arguments"] += tc_delta.function.arguments

                # Track usage
                if chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

                # Handle finish
                if choice.finish_reason:
                    for tc_data in current_tool_calls.values():
                        yield StreamDelta(
                            type="tool_call",
                            tool_call=ToolCall(**tc_data),
                        )
                    yield StreamDelta(
                        type="finish",
                        finish_reason=choice.finish_reason,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

        except Exception as e:
            raise LLMError(
                message=f"Mistral streaming failed: {str(e)}",
                provider="mistral",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Mistral embed model."""
        try:
            model_name = model or "mistral-embed"

            response = await self.client.embeddings.create_async(
                model=model_name,
                inputs=texts,
            )

            return [item.embedding for item in response.data]

        except Exception as e:
            raise LLMError(
                message=f"Mistral embedding failed: {str(e)}",
                provider="mistral",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Flagship - Mistral Large 3 (Dec 2025)
            "mistral-large-3",           # 41B active / 675B total MoE
            "mistral-large-latest",
            # Medium
            "mistral-medium-3.1",
            "mistral-medium-3",
            # Small
            "mistral-small-3.2",
            "mistral-small-3.1",
            "mistral-small-latest",
            # Ministral (dense, small models - Dec 2025)
            "ministral-3-14b",
            "ministral-3-7b",
            "ministral-3-3b",
            # Codestral (coding)
            "codestral-2508",
            "codestral-2501",
            # Devstral (dev/agents - Dec 2025)
            "devstral-2",
            "devstral-small-2",
            # Magistral (reasoning - June 2025)
            "magistral-medium-1.1",
            "magistral-small-1.1",
            # Pixtral (vision)
            "pixtral-large-latest",
            # Voxtral (audio)
            "voxtral-small-2507",
            "voxtral-mini-2507",
            # Embeddings
            "mistral-embed",
            "mistral-codestral-embed",
            # Open-weight
            "open-mistral-nemo",
            "open-mixtral-8x7b",
            "open-mixtral-8x22b",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        # Default to True for newer models
        return "large" in model or "small" in model or "ministral" in model

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Format messages for Mistral API."""
        formatted = []

        for msg in messages:
            formatted_msg = {
                "role": msg.role,
                "content": msg.content,
            }

            if msg.tool_calls:
                formatted_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": tc["function"],
                    }
                    for tc in msg.tool_calls
                ]

            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id
                formatted_msg["name"] = msg.name

            formatted.append(formatted_msg)

        return formatted

