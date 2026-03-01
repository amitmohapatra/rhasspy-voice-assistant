"""Groq LLM Provider - Ultra-fast inference with custom LPU hardware."""

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


class GroqProvider(LLMProvider):
    """Groq provider for ultra-fast LLM inference on LPU hardware."""

    provider_name = "groq"

    # Available models (optimized for speed on LPU hardware - 2025)
    MODELS = {
        # Llama 4 (2025) - multimodal MoE
        "llama-4-maverick-17b-128e": {"context": 1000000, "tools": True, "vision": True, "moe": True},
        "llama-4-scout-17b-16e": {"context": 10000000, "tools": True, "vision": True, "moe": True},
        # Llama 3.3
        "llama-3.3-70b-versatile": {"context": 128000, "tools": True},
        # Llama 3.2
        "llama-3.2-90b-vision-preview": {"context": 8192, "tools": True, "vision": True},
        "llama-3.2-11b-vision-preview": {"context": 8192, "tools": True, "vision": True},
        "llama-3.2-3b-preview": {"context": 8192, "tools": True},
        "llama-3.2-1b-preview": {"context": 8192, "tools": True},
        # Llama 3.1
        "llama-3.1-70b-versatile": {"context": 128000, "tools": True},
        "llama-3.1-8b-instant": {"context": 128000, "tools": True},
        # DeepSeek R1 (reasoning) - 128k context on Groq
        "deepseek-r1-distill-llama-70b": {"context": 128000, "tools": False, "reasoning": True},
        # Qwen QwQ (reasoning)
        "qwen-qwq-32b": {"context": 32000, "tools": True, "reasoning": True},
        # Mixtral
        "mixtral-8x7b-32768": {"context": 32768, "tools": True},
        # Gemma
        "gemma2-9b-it": {"context": 8192, "tools": True},
        # Kimi (Moonshot)
        "moonshotai-kimi-k2-instruct": {"context": 128000, "tools": True},
        # Whisper (for audio)
        "whisper-large-v3": {"context": 0, "tools": False, "audio": True},
        "whisper-large-v3-turbo": {"context": 0, "tools": False, "audio": True},
    }

    # Model aliases
    MODEL_ALIASES = {
        "llama-4": "llama-4-maverick-17b-128e",
        "deepseek-r1": "deepseek-r1-distill-llama-70b",
        "qwq": "qwen-qwq-32b",
    }

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "groq_api_key", None)

        if not self.api_key:
            raise LLMError("Groq API key not configured", provider="groq")

        try:
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=self.api_key)
        except ImportError:
            raise LLMError(
                "groq package not installed. Run: pip install groq",
                provider="groq",
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

            response = await self.client.chat.completions.create(**params)

            choice = response.choices[0]
            message = choice.message

            # Extract tool calls
            tool_calls = None
            if message.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id,
                        type=tc.type,
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
                message=f"Groq completion failed: {str(e)}",
                provider="groq",
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
                "stream": True,
            }

            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools
                if request.tool_choice:
                    params["tool_choice"] = request.tool_choice

            stream = await self.client.chat.completions.create(**params)

            current_tool_calls: dict[int, dict] = {}
            input_tokens = 0
            output_tokens = 0

            async for chunk in stream:
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
                        idx = tc_delta.index

                        if idx not in current_tool_calls:
                            current_tool_calls[idx] = {
                                "id": tc_delta.id or "",
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

                # Track usage from x_groq header
                if hasattr(chunk, "x_groq") and chunk.x_groq:
                    usage = chunk.x_groq.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("completion_tokens", 0)

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
                message=f"Groq streaming failed: {str(e)}",
                provider="groq",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Groq doesn't support embeddings natively - raise error."""
        raise LLMError(
            message="Groq does not support embeddings. Use OpenAI, Cohere, or Voyage embeddings instead.",
            provider="groq",
        )

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Llama 4 (multimodal MoE)
            "llama-4-maverick-17b-128e",  # 17B active, 400B total
            "llama-4-scout-17b-16e",      # 17B active, 109B total, 10M context
            # Llama 3.3
            "llama-3.3-70b-versatile",
            # Llama 3.2 Vision
            "llama-3.2-90b-vision-preview",
            "llama-3.2-11b-vision-preview",
            # Llama 3.2 Text
            "llama-3.2-3b-preview",
            "llama-3.2-1b-preview",
            # Llama 3.1
            "llama-3.1-70b-versatile",
            "llama-3.1-8b-instant",
            # DeepSeek R1 (reasoning)
            "deepseek-r1-distill-llama-70b",  # 94.5% MATH-500
            # Qwen QwQ (reasoning)
            "qwen-qwq-32b",
            # Mixtral
            "mixtral-8x7b-32768",
            # Gemma
            "gemma2-9b-it",
            # Kimi
            "moonshotai-kimi-k2-instruct",
            # Audio
            "whisper-large-v3",
            "whisper-large-v3-turbo",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        return True  # Most Groq models support tools

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for Groq API (OpenAI-compatible)."""
        formatted = []

        for msg in messages:
            formatted_msg: dict[str, Any] = {
                "role": msg.role,
                "content": msg.content,
            }

            if msg.name:
                formatted_msg["name"] = msg.name

            if msg.tool_calls:
                formatted_msg["tool_calls"] = msg.tool_calls

            if msg.tool_call_id:
                formatted_msg["tool_call_id"] = msg.tool_call_id

            formatted.append(formatted_msg)

        return formatted
