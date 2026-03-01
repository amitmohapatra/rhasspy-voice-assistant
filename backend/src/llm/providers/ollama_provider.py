"""Ollama LLM Provider - Run open-source models locally with zero config."""

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


class OllamaProvider(LLMProvider):
    """Ollama provider for running LLMs locally on your own hardware.

    Features:
    - Zero config local inference
    - Support for all major open-source models
    - Tool/function calling support
    - Vision model support
    - Embedding generation
    - Air-gapped/offline deployments
    """

    provider_name = "ollama"

    # Popular models (user can run any model available on Ollama)
    MODELS = {
        # Llama 3.3
        "llama3.3": {"context": 128000, "tools": True},
        "llama3.3:70b": {"context": 128000, "tools": True},
        # Llama 3.2
        "llama3.2": {"context": 128000, "tools": True},
        "llama3.2:1b": {"context": 128000, "tools": True},
        "llama3.2:3b": {"context": 128000, "tools": True},
        "llama3.2-vision": {"context": 128000, "tools": True, "vision": True},
        # Llama 3.1
        "llama3.1": {"context": 128000, "tools": True},
        "llama3.1:8b": {"context": 128000, "tools": True},
        "llama3.1:70b": {"context": 128000, "tools": True},
        "llama3.1:405b": {"context": 128000, "tools": True},
        # Qwen 2.5
        "qwen2.5": {"context": 32768, "tools": True},
        "qwen2.5:7b": {"context": 32768, "tools": True},
        "qwen2.5:14b": {"context": 32768, "tools": True},
        "qwen2.5:32b": {"context": 32768, "tools": True},
        "qwen2.5:72b": {"context": 32768, "tools": True},
        "qwen2.5-coder": {"context": 32768, "tools": True},
        # DeepSeek
        "deepseek-r1": {"context": 64000, "tools": False},
        "deepseek-r1:7b": {"context": 64000, "tools": False},
        "deepseek-r1:14b": {"context": 64000, "tools": False},
        "deepseek-r1:32b": {"context": 64000, "tools": False},
        "deepseek-r1:70b": {"context": 64000, "tools": False},
        # Mistral
        "mistral": {"context": 32768, "tools": True},
        "mistral-nemo": {"context": 128000, "tools": True},
        "mistral-large": {"context": 128000, "tools": True},
        "mixtral": {"context": 32768, "tools": True},
        # Phi
        "phi4": {"context": 16384, "tools": True},
        "phi3": {"context": 4096, "tools": True},
        # Gemma
        "gemma2": {"context": 8192, "tools": True},
        "gemma2:2b": {"context": 8192, "tools": True},
        "gemma2:9b": {"context": 8192, "tools": True},
        "gemma2:27b": {"context": 8192, "tools": True},
        # CodeLlama
        "codellama": {"context": 16384, "tools": False},
        # Vision models
        "llava": {"context": 4096, "tools": False, "vision": True},
        "llava-llama3": {"context": 8192, "tools": False, "vision": True},
        "moondream": {"context": 4096, "tools": False, "vision": True},
        # Embedding models
        "nomic-embed-text": {"context": 8192, "tools": False, "embedding": True},
        "mxbai-embed-large": {"context": 512, "tools": False, "embedding": True},
        "all-minilm": {"context": 512, "tools": False, "embedding": True},
    }

    def __init__(
        self,
        host: str | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.host = host or getattr(settings, "ollama_host", "http://localhost:11434")
        self.timeout = timeout

        try:
            import ollama
            self.ollama = ollama
            self.client = ollama.AsyncClient(host=self.host, timeout=timeout)
        except ImportError:
            raise LLMError(
                "ollama package not installed. Run: pip install ollama",
                provider="ollama",
            )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        try:
            messages = self._format_messages(request.messages)

            options = {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                "top_p": request.top_p,
            }

            params = {
                "model": request.model,
                "messages": messages,
                "options": options,
                "stream": False,
            }

            # Add tools (already in Chat Completions format from ToolResolver)
            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools

            response = await self.client.chat(**params)

            # Extract content
            content = response.get("message", {}).get("content", "")

            # Extract tool calls
            tool_calls = None
            message_tool_calls = response.get("message", {}).get("tool_calls", [])
            if message_tool_calls:
                tool_calls = [
                    ToolCall(
                        id=f"call_{i}",
                        type="function",
                        function={
                            "name": tc.get("function", {}).get("name", ""),
                            "arguments": json.dumps(tc.get("function", {}).get("arguments", {})),
                        },
                    )
                    for i, tc in enumerate(message_tool_calls)
                ]

            # Get usage
            input_tokens = response.get("prompt_eval_count", 0)
            output_tokens = response.get("eval_count", 0)

            return CompletionResponse(
                content=content,
                tool_calls=tool_calls,
                finish_reason="stop" if not tool_calls else "tool_calls",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                model=request.model,
            )

        except Exception as e:
            raise LLMError(
                message=f"Ollama completion failed: {str(e)}",
                provider="ollama",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        try:
            messages = self._format_messages(request.messages)

            options = {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
                "top_p": request.top_p,
            }

            params = {
                "model": request.model,
                "messages": messages,
                "options": options,
                "stream": True,
            }

            if request.tools and self.supports_tools(request.model):
                params["tools"] = request.tools

            input_tokens = 0
            output_tokens = 0

            async for chunk in await self.client.chat(**params):
                # Handle text content
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield StreamDelta(type="text", content=content)

                # Handle tool calls
                tool_calls = chunk.get("message", {}).get("tool_calls", [])
                for i, tc in enumerate(tool_calls):
                    yield StreamDelta(
                        type="tool_call",
                        tool_call=ToolCall(
                            id=f"call_{i}",
                            type="function",
                            function={
                                "name": tc.get("function", {}).get("name", ""),
                                "arguments": json.dumps(tc.get("function", {}).get("arguments", {})),
                            },
                        ),
                    )

                # Track usage
                if chunk.get("prompt_eval_count"):
                    input_tokens = chunk["prompt_eval_count"]
                if chunk.get("eval_count"):
                    output_tokens = chunk["eval_count"]

                # Handle finish
                if chunk.get("done"):
                    yield StreamDelta(
                        type="finish",
                        finish_reason="stop",
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

        except Exception as e:
            raise LLMError(
                message=f"Ollama streaming failed: {str(e)}",
                provider="ollama",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Ollama embedding models."""
        try:
            model_name = model or "nomic-embed-text"

            # Ollama embeddings API handles single text at a time
            embeddings = []
            for text in texts:
                response = await self.client.embeddings(
                    model=model_name,
                    prompt=text,
                )
                embeddings.append(response["embedding"])

            return embeddings

        except Exception as e:
            raise LLMError(
                message=f"Ollama embedding failed: {str(e)}",
                provider="ollama",
                details={"model": model, "error": str(e)},
            )

    async def pull_model(self, model: str) -> None:
        """Pull/download a model from Ollama registry."""
        try:
            await self.client.pull(model)
        except Exception as e:
            raise LLMError(
                message=f"Failed to pull model {model}: {str(e)}",
                provider="ollama",
            )

    async def list_local_models(self) -> list[str]:
        """List models available locally."""
        try:
            response = await self.client.list()
            return [m["name"] for m in response.get("models", [])]
        except Exception as e:
            raise LLMError(
                message=f"Failed to list models: {str(e)}",
                provider="ollama",
            )

    def list_models(self) -> list[str]:
        """List popular models (not necessarily installed)."""
        return list(self.MODELS.keys())

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        # Normalize model name (remove tags like :7b)
        base_model = model.split(":")[0]
        if base_model in self.MODELS:
            return self.MODELS[base_model].get("tools", False)
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        # Default to True for newer models
        return True

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Format messages for Ollama API."""
        formatted = []

        for msg in messages:
            formatted_msg = {
                "role": msg.role,
                "content": msg.content,
            }

            # Handle tool calls in assistant messages
            if msg.tool_calls:
                formatted_msg["tool_calls"] = [
                    {
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"].get("arguments", {}),
                        }
                    }
                    for tc in msg.tool_calls
                ]

            formatted.append(formatted_msg)

        return formatted

