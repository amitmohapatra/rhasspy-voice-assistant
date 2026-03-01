"""Azure OpenAI LLM Provider - OpenAI models via Azure with enterprise compliance."""

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


class AzureOpenAIProvider(LLMProvider):
    """Azure OpenAI provider for enterprise deployments."""

    provider_name = "azure_openai"

    # Models that support function calling
    TOOL_CAPABLE_MODELS = {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4-turbo",
        "gpt-4",
        "gpt-35-turbo",
        "gpt-4-32k",
    }

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        api_version: str = "2024-08-01-preview",
        deployment_name: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "azure_openai_api_key", None)
        self.endpoint = endpoint or getattr(settings, "azure_openai_endpoint", None)
        self.api_version = api_version
        self.default_deployment = deployment_name

        if not self.api_key:
            raise LLMError("Azure OpenAI API key not configured", provider="azure_openai")
        if not self.endpoint:
            raise LLMError("Azure OpenAI endpoint not configured", provider="azure_openai")

        try:
            from openai import AsyncAzureOpenAI

            self.client = AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
            )
        except ImportError:
            raise LLMError(
                "openai package not installed. Run: pip install openai",
                provider="azure_openai",
            )

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        try:
            # Use deployment name (Azure uses deployments, not model names directly)
            deployment = request.model or self.default_deployment

            # Build messages
            messages = self._format_messages(request.messages)

            # Build request params
            params: dict[str, Any] = {
                "model": deployment,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
            }

            # Add tools (already in Chat Completions format from ToolResolver)
            if request.tools and self._model_supports_tools(deployment):
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
                message=f"Azure OpenAI completion failed: {str(e)}",
                provider="azure_openai",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        try:
            deployment = request.model or self.default_deployment
            messages = self._format_messages(request.messages)

            params: dict[str, Any] = {
                "model": deployment,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "top_p": request.top_p,
                "stream": True,
                "stream_options": {"include_usage": True},
            }

            if request.tools and self._model_supports_tools(deployment):
                params["tools"] = request.tools
                if request.tool_choice:
                    params["tool_choice"] = request.tool_choice

            stream = await self.client.chat.completions.create(**params)

            current_tool_calls: dict[int, dict] = {}

            async for chunk in stream:
                if not chunk.choices:
                    if chunk.usage:
                        yield StreamDelta(
                            type="finish",
                            finish_reason="stop",
                            input_tokens=chunk.usage.prompt_tokens,
                            output_tokens=chunk.usage.completion_tokens,
                        )
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if delta.content:
                    yield StreamDelta(type="text", content=delta.content)

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
                message=f"Azure OpenAI streaming failed: {str(e)}",
                provider="azure_openai",
                details={"model": request.model, "error": str(e)},
            )

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Azure OpenAI embedding deployment."""
        try:
            deployment = model or getattr(settings, "azure_embedding_deployment", "text-embedding-ada-002")

            response = await self.client.embeddings.create(
                input=texts,
                model=deployment,
            )

            return [item.embedding for item in response.data]

        except Exception as e:
            raise LLMError(
                message=f"Azure OpenAI embedding failed: {str(e)}",
                provider="azure_openai",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List available model deployments (deployment names vary by customer)."""
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-4-32k",
            "gpt-35-turbo",
            "gpt-35-turbo-16k",
        ]

    def supports_tools(self, model: str) -> bool:
        """Check if deployment supports function calling."""
        return self._model_supports_tools(model)

    def _model_supports_tools(self, deployment: str) -> bool:
        """Check deployment for tool support."""
        # Most GPT-4 and GPT-3.5-turbo deployments support tools
        deployment_lower = deployment.lower()
        return any(
            m in deployment_lower
            for m in ["gpt-4", "gpt-35-turbo", "gpt-3.5-turbo"]
        )

    def _format_messages(self, messages: list[Message]) -> list[dict[str, Any]]:
        """Format messages for Azure OpenAI API."""
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
