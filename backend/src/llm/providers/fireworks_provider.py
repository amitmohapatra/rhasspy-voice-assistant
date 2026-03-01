"""Fireworks AI LLM Provider - Fast inference for open-source models."""

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


class FireworksProvider(LLMProvider):
    """Fireworks AI provider for fast, cost-effective inference."""

    provider_name = "fireworks"

    # Available models (as of late 2025)
    MODELS = {
        # Llama 4 (2025) - multimodal MoE
        "accounts/fireworks/models/llama-v4-maverick-17b-128e-instruct": {"context": 1000000, "tools": True, "vision": True, "moe": True},
        "accounts/fireworks/models/llama-v4-scout-17b-16e-instruct": {"context": 10000000, "tools": True, "vision": True, "moe": True},
        # Llama 3.3
        "accounts/fireworks/models/llama-v3p3-70b-instruct": {"context": 128000, "tools": True},
        # Llama 3.2
        "accounts/fireworks/models/llama-v3p2-3b-instruct": {"context": 128000, "tools": True},
        "accounts/fireworks/models/llama-v3p2-1b-instruct": {"context": 128000, "tools": True},
        "accounts/fireworks/models/llama-v3p2-11b-vision-instruct": {"context": 128000, "tools": True, "vision": True},
        "accounts/fireworks/models/llama-v3p2-90b-vision-instruct": {"context": 128000, "tools": True, "vision": True},
        # Llama 3.1
        "accounts/fireworks/models/llama-v3p1-405b-instruct": {"context": 128000, "tools": True},
        "accounts/fireworks/models/llama-v3p1-70b-instruct": {"context": 128000, "tools": True},
        "accounts/fireworks/models/llama-v3p1-8b-instruct": {"context": 128000, "tools": True},
        # Qwen 3 (2025)
        "accounts/fireworks/models/qwen3-235b-a22b-instruct": {"context": 128000, "tools": True, "moe": True},
        "accounts/fireworks/models/qwen3-72b-instruct": {"context": 128000, "tools": True},
        "accounts/fireworks/models/qwen3-30b-a3b-instruct": {"context": 128000, "tools": True, "moe": True},
        # Qwen 2.5
        "accounts/fireworks/models/qwen2p5-72b-instruct": {"context": 32768, "tools": True},
        "accounts/fireworks/models/qwen2p5-coder-32b-instruct": {"context": 32768, "tools": True},
        # DeepSeek R1 (reasoning - 2025)
        "accounts/fireworks/models/deepseek-r1": {"context": 128000, "tools": False, "reasoning": True},
        "accounts/fireworks/models/deepseek-r1-distill-llama-70b": {"context": 128000, "tools": False, "reasoning": True},
        "accounts/fireworks/models/deepseek-r1-distill-qwen-32b": {"context": 128000, "tools": False, "reasoning": True},
        # DeepSeek V3
        "accounts/fireworks/models/deepseek-v3": {"context": 128000, "tools": True},
        # Mistral Large 3 (2025)
        "accounts/fireworks/models/mistral-large-3-instruct": {"context": 256000, "tools": True, "moe": True},
        # Mixtral
        "accounts/fireworks/models/mixtral-8x22b-instruct": {"context": 65536, "tools": True},
        "accounts/fireworks/models/mixtral-8x7b-instruct": {"context": 32768, "tools": True},
        # Microsoft Phi-4 (2025)
        "accounts/fireworks/models/phi-4": {"context": 16384, "tools": True},
        "accounts/fireworks/models/phi-3-vision-128k-instruct": {"context": 128000, "tools": True, "vision": True},
        # Google Gemma 2
        "accounts/fireworks/models/gemma2-27b-it": {"context": 8192, "tools": True},
        "accounts/fireworks/models/gemma2-9b-it": {"context": 8192, "tools": True},
        # DBRX
        "accounts/fireworks/models/dbrx-instruct": {"context": 32768, "tools": True},
        # Embedding
        "nomic-ai/nomic-embed-text-v1.5": {"context": 8192, "tools": False, "embedding": True},
        "BAAI/bge-large-en-v1.5": {"context": 8192, "tools": False, "embedding": True},
    }

    # Friendly aliases
    MODEL_ALIASES = {
        # Llama 4
        "llama-4-maverick": "accounts/fireworks/models/llama-v4-maverick-17b-128e-instruct",
        "llama-4-scout": "accounts/fireworks/models/llama-v4-scout-17b-16e-instruct",
        # Llama 3.x
        "llama-3.3-70b": "accounts/fireworks/models/llama-v3p3-70b-instruct",
        "llama-3.1-405b": "accounts/fireworks/models/llama-v3p1-405b-instruct",
        "llama-3.1-70b": "accounts/fireworks/models/llama-v3p1-70b-instruct",
        "llama-3.1-8b": "accounts/fireworks/models/llama-v3p1-8b-instruct",
        # Qwen 3
        "qwen-3-235b": "accounts/fireworks/models/qwen3-235b-a22b-instruct",
        "qwen-3-72b": "accounts/fireworks/models/qwen3-72b-instruct",
        # Qwen 2.5
        "qwen-72b": "accounts/fireworks/models/qwen2p5-72b-instruct",
        # DeepSeek
        "deepseek-r1": "accounts/fireworks/models/deepseek-r1",
        "deepseek-v3": "accounts/fireworks/models/deepseek-v3",
        # Mistral
        "mistral-large-3": "accounts/fireworks/models/mistral-large-3-instruct",
        "mixtral-8x22b": "accounts/fireworks/models/mixtral-8x22b-instruct",
    }

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "fireworks_api_key", None)
        self.base_url = "https://api.fireworks.ai/inference/v1"

        if not self.api_key:
            raise LLMError("Fireworks API key not configured", provider="fireworks")

        try:
            from openai import AsyncOpenAI
            # Fireworks uses OpenAI-compatible API
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
            )
        except ImportError:
            raise LLMError(
                "openai package not installed. Run: pip install openai",
                provider="fireworks",
            )

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        try:
            model = self._resolve_model(request.model)
            messages = self._format_messages(request.messages)

            params = {
                "model": model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
            }

            # Add tools (already in Chat Completions format from ToolResolver)
            if request.tools and self.supports_tools(model):
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
                message=f"Fireworks completion failed: {str(e)}",
                provider="fireworks",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        try:
            model = self._resolve_model(request.model)
            messages = self._format_messages(request.messages)

            params = {
                "model": model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
                "stream": True,
            }

            if request.tools and self.supports_tools(model):
                params["tools"] = request.tools
                if request.tool_choice:
                    params["tool_choice"] = request.tool_choice

            stream = await self.client.chat.completions.create(**params)

            current_tool_calls: dict[int, dict] = {}

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
                    )

        except Exception as e:
            raise LLMError(
                message=f"Fireworks streaming failed: {str(e)}",
                provider="fireworks",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Fireworks embedding models."""
        try:
            model_name = model or "nomic-ai/nomic-embed-text-v1.5"

            response = await self.client.embeddings.create(
                model=model_name,
                input=texts,
            )

            return [item.embedding for item in response.data]

        except Exception as e:
            raise LLMError(
                message=f"Fireworks embedding failed: {str(e)}",
                provider="fireworks",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Llama 4 (2025 - multimodal MoE)
            "accounts/fireworks/models/llama-v4-maverick-17b-128e-instruct",
            "accounts/fireworks/models/llama-v4-scout-17b-16e-instruct",
            # Llama 3.3
            "accounts/fireworks/models/llama-v3p3-70b-instruct",
            # Llama 3.2 Vision
            "accounts/fireworks/models/llama-v3p2-90b-vision-instruct",
            "accounts/fireworks/models/llama-v3p2-11b-vision-instruct",
            # Llama 3.1
            "accounts/fireworks/models/llama-v3p1-405b-instruct",
            "accounts/fireworks/models/llama-v3p1-70b-instruct",
            "accounts/fireworks/models/llama-v3p1-8b-instruct",
            # Qwen 3
            "accounts/fireworks/models/qwen3-235b-a22b-instruct",
            "accounts/fireworks/models/qwen3-72b-instruct",
            # Qwen 2.5
            "accounts/fireworks/models/qwen2p5-72b-instruct",
            "accounts/fireworks/models/qwen2p5-coder-32b-instruct",
            # DeepSeek R1 (reasoning)
            "accounts/fireworks/models/deepseek-r1",
            "accounts/fireworks/models/deepseek-r1-distill-llama-70b",
            # DeepSeek V3
            "accounts/fireworks/models/deepseek-v3",
            # Mistral Large 3
            "accounts/fireworks/models/mistral-large-3-instruct",
            # Mixtral
            "accounts/fireworks/models/mixtral-8x22b-instruct",
            "accounts/fireworks/models/mixtral-8x7b-instruct",
            # Phi-4
            "accounts/fireworks/models/phi-4",
            # Gemma 2
            "accounts/fireworks/models/gemma2-27b-it",
            "accounts/fireworks/models/gemma2-9b-it",
        ]

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        model = self._resolve_model(model)
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        return True  # Most Fireworks models support tools

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for Fireworks API (OpenAI-compatible)."""
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
