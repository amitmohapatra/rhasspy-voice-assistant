"""Replicate LLM Provider - Run any ML model via API."""

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


class ReplicateProvider(LLMProvider):
    """Replicate provider for running any ML model via simple API.

    Replicate hosts thousands of open-source models that can be run
    with a simple API call, without managing infrastructure.
    """

    provider_name = "replicate"

    # Popular LLM models on Replicate (as of late 2025)
    MODELS = {
        # Meta Llama 4 (2025) - multimodal MoE
        "meta/llama-4-maverick-17b-128e-instruct": {"context": 1000000, "tools": True, "vision": True, "moe": True},
        "meta/llama-4-scout-17b-16e-instruct": {"context": 10000000, "tools": True, "vision": True, "moe": True},
        # Meta Llama 3.3
        "meta/llama-3.3-70b-instruct": {"context": 128000, "tools": True},
        # Meta Llama 3.2 Vision
        "meta/llama-3.2-90b-vision-instruct": {"context": 128000, "tools": True, "vision": True},
        "meta/llama-3.2-11b-vision-instruct": {"context": 128000, "tools": True, "vision": True},
        # Meta Llama 3.1
        "meta/llama-3.1-405b-instruct": {"context": 128000, "tools": True},
        "meta/llama-3.1-70b-instruct": {"context": 128000, "tools": True},
        "meta/llama-3.1-8b-instruct": {"context": 128000, "tools": True},
        # Meta Llama 3 (legacy)
        "meta/meta-llama-3-70b-instruct": {"context": 8192, "tools": False},
        "meta/meta-llama-3-8b-instruct": {"context": 8192, "tools": False},
        # DeepSeek R1 (reasoning - 2025)
        "deepseek-ai/deepseek-r1": {"context": 128000, "tools": False, "reasoning": True},
        "deepseek-ai/deepseek-r1-distill-llama-70b": {"context": 128000, "tools": False, "reasoning": True},
        "deepseek-ai/deepseek-r1-distill-qwen-32b": {"context": 128000, "tools": False, "reasoning": True},
        # DeepSeek V3
        "deepseek-ai/deepseek-v3": {"context": 128000, "tools": True},
        # Qwen 3 (2025)
        "qwen/qwen3-235b-a22b-instruct": {"context": 128000, "tools": True, "moe": True},
        "qwen/qwen3-72b-instruct": {"context": 128000, "tools": True},
        # Qwen 2.5
        "qwen/qwen2.5-72b-instruct": {"context": 32768, "tools": True},
        "qwen/qwen2.5-coder-32b-instruct": {"context": 32768, "tools": True},
        # Qwen QwQ (reasoning)
        "qwen/qwq-32b-preview": {"context": 32768, "tools": True, "reasoning": True},
        # Mistral
        "mistralai/mistral-large-3": {"context": 256000, "tools": True, "moe": True},
        "mistralai/mixtral-8x22b-instruct-v0.1": {"context": 65536, "tools": True},
        "mistralai/mixtral-8x7b-instruct-v0.1": {"context": 32768, "tools": True},
        "mistralai/mistral-7b-instruct-v0.2": {"context": 32768, "tools": False},
        # Microsoft Phi-4 (2025)
        "microsoft/phi-4": {"context": 16384, "tools": True},
        # Google Gemma 2
        "google/gemma-2-27b-it": {"context": 8192, "tools": True},
        "google/gemma-2-9b-it": {"context": 8192, "tools": True},
        # Yi 1.5
        "01-ai/yi-1.5-34b-chat": {"context": 4096, "tools": False},
        # Snowflake Arctic
        "snowflake/snowflake-arctic-instruct": {"context": 4096, "tools": False},
    }

    # Model aliases
    MODEL_ALIASES = {
        # Llama 4
        "llama-4-maverick": "meta/llama-4-maverick-17b-128e-instruct",
        "llama-4-scout": "meta/llama-4-scout-17b-16e-instruct",
        # Llama 3.x
        "llama-3.3-70b": "meta/llama-3.3-70b-instruct",
        "llama-3.1-405b": "meta/llama-3.1-405b-instruct",
        "llama-3.1-70b": "meta/llama-3.1-70b-instruct",
        # DeepSeek
        "deepseek-r1": "deepseek-ai/deepseek-r1",
        "deepseek-v3": "deepseek-ai/deepseek-v3",
        # Qwen
        "qwen-3-235b": "qwen/qwen3-235b-a22b-instruct",
        "qwq-32b": "qwen/qwq-32b-preview",
        # Mistral
        "mistral-large-3": "mistralai/mistral-large-3",
    }

    def __init__(
        self,
        api_token: str | None = None,
    ) -> None:
        self.api_token = api_token or getattr(settings, "replicate_api_token", None)

        if not self.api_token:
            raise LLMError("Replicate API token not configured", provider="replicate")

        try:
            import replicate
            self.replicate = replicate
            self.client = replicate.Client(api_token=self.api_token)
        except ImportError:
            raise LLMError(
                "replicate package not installed. Run: pip install replicate",
                provider="replicate",
            )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        try:
            # Format prompt for the model
            prompt = self._format_prompt(request.messages)

            # Build input parameters
            input_params = {
                "prompt": prompt,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
            }

            # Handle system prompt if present
            system_prompt = self._extract_system_prompt(request.messages)
            if system_prompt:
                input_params["system_prompt"] = system_prompt

            # Resolve model alias
            model = self.resolve_model_alias(request.model)

            # Run the model
            import asyncio
            output = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.run(model, input=input_params)
            )

            # Collect output (may be a generator)
            content = ""
            if isinstance(output, (list, tuple)):
                content = "".join(str(chunk) for chunk in output)
            elif hasattr(output, "__iter__"):
                content = "".join(str(chunk) for chunk in output)
            else:
                content = str(output)

            return CompletionResponse(
                content=content,
                tool_calls=None,
                finish_reason="stop",
                input_tokens=0,  # Replicate doesn't provide token counts
                output_tokens=0,
                total_tokens=0,
                model=request.model,
            )

        except Exception as e:
            raise LLMError(
                message=f"Replicate completion failed: {str(e)}",
                provider="replicate",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        try:
            prompt = self._format_prompt(request.messages)

            input_params = {
                "prompt": prompt,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
                "top_p": request.top_p,
            }

            system_prompt = self._extract_system_prompt(request.messages)
            if system_prompt:
                input_params["system_prompt"] = system_prompt

            # Resolve model alias
            model = self.resolve_model_alias(request.model)

            # Stream from Replicate
            import asyncio

            def run_stream():
                return list(self.client.stream(model, input=input_params))

            # Replicate's stream returns an iterator
            chunks = await asyncio.get_event_loop().run_in_executor(None, run_stream)

            for chunk in chunks:
                if chunk.event == "output":
                    yield StreamDelta(type="text", content=str(chunk.data))
                elif chunk.event == "done":
                    yield StreamDelta(
                        type="finish",
                        finish_reason="stop",
                    )

        except Exception as e:
            raise LLMError(
                message=f"Replicate streaming failed: {str(e)}",
                provider="replicate",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Replicate embedding models."""
        try:
            model_name = model or "replicate/all-mpnet-base-v2"

            import asyncio
            embeddings = []

            for text in texts:
                output = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda t=text: self.client.run(
                        model_name,
                        input={"text": t}
                    )
                )

                # Output format varies by model
                if isinstance(output, list):
                    if isinstance(output[0], list):
                        embeddings.append(output[0])
                    else:
                        embeddings.append(output)
                else:
                    embeddings.append(list(output))

            return embeddings

        except Exception as e:
            raise LLMError(
                message=f"Replicate embedding failed: {str(e)}",
                provider="replicate",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List popular LLM models on Replicate."""
        return [
            # Llama 4 (2025 - multimodal MoE)
            "meta/llama-4-maverick-17b-128e-instruct",
            "meta/llama-4-scout-17b-16e-instruct",
            # Llama 3.3
            "meta/llama-3.3-70b-instruct",
            # Llama 3.2 Vision
            "meta/llama-3.2-90b-vision-instruct",
            "meta/llama-3.2-11b-vision-instruct",
            # Llama 3.1
            "meta/llama-3.1-405b-instruct",
            "meta/llama-3.1-70b-instruct",
            "meta/llama-3.1-8b-instruct",
            # DeepSeek R1 (reasoning)
            "deepseek-ai/deepseek-r1",
            "deepseek-ai/deepseek-r1-distill-llama-70b",
            # DeepSeek V3
            "deepseek-ai/deepseek-v3",
            # Qwen 3
            "qwen/qwen3-235b-a22b-instruct",
            "qwen/qwen3-72b-instruct",
            # Qwen 2.5
            "qwen/qwen2.5-72b-instruct",
            "qwen/qwen2.5-coder-32b-instruct",
            # Qwen QwQ (reasoning)
            "qwen/qwq-32b-preview",
            # Mistral
            "mistralai/mistral-large-3",
            "mistralai/mixtral-8x22b-instruct-v0.1",
            # Phi-4
            "microsoft/phi-4",
            # Gemma 2
            "google/gemma-2-27b-it",
            "google/gemma-2-9b-it",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        model = self.resolve_model_alias(model)
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        # Newer models generally support tools
        return "llama-4" in model or "llama-3.1" in model or "qwen3" in model

    def _format_prompt(self, messages: list[Message]) -> str:
        """Format messages into a prompt string.

        Replicate models typically expect a single prompt string,
        not a list of messages. We format it appropriately.
        """
        parts = []

        for msg in messages:
            if msg.role == "system":
                continue  # Handled separately
            elif msg.role == "user":
                parts.append(f"User: {msg.content}")
            elif msg.role == "assistant":
                parts.append(f"Assistant: {msg.content}")
            elif msg.role == "tool":
                parts.append(f"Tool Result: {msg.content}")

        # Add final assistant prefix to prompt continuation
        parts.append("Assistant:")

        return "\n\n".join(parts)

    async def get_model_info(self, model: str) -> dict:
        """Get information about a model."""
        try:
            import asyncio
            model_info = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.replicate.models.get(model)
            )
            return {
                "name": model_info.name,
                "description": model_info.description,
                "owner": model_info.owner,
                "url": model_info.url,
            }
        except Exception as e:
            raise LLMError(
                message=f"Failed to get model info: {str(e)}",
                provider="replicate",
            )

    async def search_models(self, query: str) -> list[dict]:
        """Search for models on Replicate."""
        try:
            import asyncio
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: list(self.replicate.models.search(query))
            )
            return [
                {
                    "name": m.name,
                    "owner": m.owner,
                    "description": m.description,
                }
                for m in results[:10]
            ]
        except Exception as e:
            raise LLMError(
                message=f"Failed to search models: {str(e)}",
                provider="replicate",
            )
