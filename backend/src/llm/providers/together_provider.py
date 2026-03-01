"""Together AI LLM Provider - Access open-source models at scale."""

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


class TogetherProvider(LLMProvider):
    """Together AI provider for open-source models with optimized inference."""

    provider_name = "together"

    # Popular models available on Together (as of late 2025)
    MODELS = {
        # Meta Llama 4 (2025)
        "meta-llama/Llama-4-Maverick-17B-128E-Instruct-Turbo": {"context": 1000000, "tools": True, "vision": True, "moe": True},
        "meta-llama/Llama-4-Scout-17B-16E-Instruct-Turbo": {"context": 10000000, "tools": True, "vision": True, "moe": True},
        # Meta Llama 3.3
        "meta-llama/Llama-3.3-70B-Instruct-Turbo": {"context": 128000, "tools": True},
        # Meta Llama 3.2
        "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo": {"context": 128000, "tools": True, "vision": True},
        "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo": {"context": 128000, "tools": True, "vision": True},
        "meta-llama/Llama-3.2-3B-Instruct-Turbo": {"context": 128000, "tools": True},
        # Meta Llama 3.1
        "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": {"context": 128000, "tools": True},
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo": {"context": 128000, "tools": True},
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo": {"context": 128000, "tools": True},
        # Qwen 3 (2025)
        "Qwen/Qwen3-235B-A22B-Instruct-Turbo": {"context": 128000, "tools": True, "moe": True},
        "Qwen/Qwen3-72B-Instruct-Turbo": {"context": 128000, "tools": True},
        "Qwen/Qwen3-30B-A3B-Instruct-Turbo": {"context": 128000, "tools": True, "moe": True},
        # Qwen 2.5
        "Qwen/Qwen2.5-72B-Instruct-Turbo": {"context": 32768, "tools": True},
        "Qwen/Qwen2.5-Coder-32B-Instruct-Turbo": {"context": 32768, "tools": True},
        "Qwen/QwQ-32B-Preview": {"context": 32768, "tools": True, "reasoning": True},
        # DeepSeek R1 (reasoning)
        "deepseek-ai/DeepSeek-R1": {"context": 128000, "tools": False, "reasoning": True},
        "deepseek-ai/DeepSeek-R1-Distill-Llama-70B": {"context": 128000, "tools": False, "reasoning": True},
        "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B": {"context": 128000, "tools": False, "reasoning": True},
        # DeepSeek V3
        "deepseek-ai/DeepSeek-V3": {"context": 128000, "tools": True},
        # Mistral Large 3 (2025)
        "mistralai/Mistral-Large-3-Instruct-2412": {"context": 256000, "tools": True, "moe": True},
        "mistralai/Mixtral-8x22B-Instruct-v0.1": {"context": 65536, "tools": True},
        "mistralai/Mixtral-8x7B-Instruct-v0.1": {"context": 32768, "tools": True},
        # Google Gemma
        "google/gemma-2-27b-it": {"context": 8192, "tools": True},
        "google/gemma-2-9b-it": {"context": 8192, "tools": True},
        # Microsoft Phi-4
        "microsoft/phi-4": {"context": 16384, "tools": True},
        # Databricks DBRX
        "databricks/dbrx-instruct": {"context": 32768, "tools": True},
    }

    # Model aliases
    MODEL_ALIASES = {
        "llama-4-maverick": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-Turbo",
        "llama-4-scout": "meta-llama/Llama-4-Scout-17B-16E-Instruct-Turbo",
        "llama-3.3-70b": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "llama-3.1-405b": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        "deepseek-r1": "deepseek-ai/DeepSeek-R1",
        "deepseek-v3": "deepseek-ai/DeepSeek-V3",
        "qwen-3-235b": "Qwen/Qwen3-235B-A22B-Instruct-Turbo",
        "mistral-large-3": "mistralai/Mistral-Large-3-Instruct-2412",
    }

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "together_api_key", None)

        if not self.api_key:
            raise LLMError("Together API key not configured", provider="together")

        try:
            from together import AsyncTogether
            self.client = AsyncTogether(api_key=self.api_key)
        except ImportError:
            raise LLMError(
                "together package not installed. Run: pip install together",
                provider="together",
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
                message=f"Together completion failed: {str(e)}",
                provider="together",
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

            async for chunk in stream:
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                # Handle text content
                if delta.content:
                    yield StreamDelta(type="text", content=delta.content)

                # Handle tool calls
                if hasattr(delta, "tool_calls") and delta.tool_calls:
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
                message=f"Together streaming failed: {str(e)}",
                provider="together",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Together embedding models."""
        try:
            model_name = model or "togethercomputer/m2-bert-80M-8k-retrieval"

            response = await self.client.embeddings.create(
                model=model_name,
                input=texts,
            )

            return [item.embedding for item in response.data]

        except Exception as e:
            raise LLMError(
                message=f"Together embedding failed: {str(e)}",
                provider="together",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Llama 4 (2025)
            "meta-llama/Llama-4-Maverick-17B-128E-Instruct-Turbo",
            "meta-llama/Llama-4-Scout-17B-16E-Instruct-Turbo",
            # Llama 3.3
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            # Llama 3.2 Vision
            "meta-llama/Llama-3.2-90B-Vision-Instruct-Turbo",
            "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo",
            # Llama 3.1
            "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
            # Qwen 3
            "Qwen/Qwen3-235B-A22B-Instruct-Turbo",
            "Qwen/Qwen3-72B-Instruct-Turbo",
            # Qwen 2.5
            "Qwen/Qwen2.5-72B-Instruct-Turbo",
            "Qwen/Qwen2.5-Coder-32B-Instruct-Turbo",
            # DeepSeek R1 (reasoning)
            "deepseek-ai/DeepSeek-R1",
            "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
            # DeepSeek V3
            "deepseek-ai/DeepSeek-V3",
            # Mistral Large 3
            "mistralai/Mistral-Large-3-Instruct-2412",
            "mistralai/Mixtral-8x22B-Instruct-v0.1",
            # Gemma
            "google/gemma-2-27b-it",
            # Phi-4
            "microsoft/phi-4",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        # Most instruction-tuned models support tools
        return "instruct" in model.lower() or "chat" in model.lower()

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for Together API (OpenAI-compatible)."""
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
