"""Google Gemini LLM Provider.

This module implements the Google Gemini provider using reusable
utilities for consistent behavior and reduced code duplication.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from src.core.config import settings
from src.core.decorators import handle_provider_errors, measure_execution_time
from src.core.exceptions import LLMError
from src.llm.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    Message,
    StreamDelta,
    ToolCall,
)


class GoogleGeminiProvider(LLMProvider):
    """Google Gemini provider using the Generative AI SDK."""

    provider_name = "google"

    # Available models (as of late 2025)
    MODELS = {
        # Gemini 3.x family (latest - Nov 2025)
        "gemini-3-pro": {"context": 2000000, "tools": True, "thinking": True},
        "gemini-3-deep-think": {"context": 2000000, "tools": True, "thinking": True},
        "gemini-3-flash": {"context": 1000000, "tools": True},
        # Gemini 2.5 family
        "gemini-2.5-pro": {"context": 2000000, "tools": True, "thinking": True},
        "gemini-2.5-flash": {"context": 1000000, "tools": True},
        "gemini-2.5-flash-lite": {"context": 1000000, "tools": True},
        # Gemini 2.0 family (retiring Mar 2026)
        "gemini-2.0-pro": {"context": 1000000, "tools": True},
        "gemini-2.0-flash": {"context": 1000000, "tools": True},
        "gemini-2.0-flash-thinking": {"context": 1000000, "tools": True, "thinking": True},
        # Legacy (deprecated/retired)
        "gemini-1.5-pro": {"context": 2000000, "tools": True},
        "gemini-1.5-flash": {"context": 1000000, "tools": True},
    }

    # Model aliases for convenience
    MODEL_ALIASES = {
        "gemini-pro": "gemini-3-pro",
        "gemini-flash": "gemini-3-flash",
        "gemini": "gemini-3-pro",
    }

    # Image generation models
    IMAGE_MODELS = {
        "gemini-3-pro-image": "Nano Banana Pro",
        "gemini-2.5-flash-image": "Nano Banana",
    }

    def __init__(
        self,
        api_key: str | None = None,
    ) -> None:
        self.api_key = api_key or getattr(settings, "google_api_key", None)

        if not self.api_key:
            raise LLMError("Google API key not configured", provider="google")

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.genai = genai
        except ImportError:
            raise LLMError(
                "google-generativeai package not installed. Run: pip install google-generativeai",
                provider="google",
            )

    @handle_provider_errors("google", "completion")
    @measure_execution_time("google_completion")
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""
        model = self.genai.GenerativeModel(
            model_name=request.model,
            generation_config={
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
                "top_p": request.top_p,
            },
            system_instruction=self._extract_system_prompt(request.messages),
        )

        # Tools already in Google-native format from ToolResolver
        tools = None
        if request.tools and self.supports_tools(request.model):
            tools = request.tools

        # Format messages for Gemini
        contents = self._format_messages(request.messages)

        # Generate response
        response = await model.generate_content_async(
            contents,
            tools=tools,
        )

        # Extract content and tool calls
        content = ""
        tool_calls = []

        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if hasattr(part, "text") and part.text:
                    content += part.text
                if hasattr(part, "function_call") and part.function_call:
                    tool_calls.append(
                        ToolCall(
                            id=f"call_{len(tool_calls)}",
                            type="function",
                            function={
                                "name": part.function_call.name,
                                "arguments": json.dumps(dict(part.function_call.args)),
                            },
                        )
                    )

        # Get usage
        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count
            output_tokens = response.usage_metadata.candidates_token_count

        return CompletionResponse(
            content=content or None,
            tool_calls=tool_calls if tool_calls else None,
            finish_reason=self._map_finish_reason(response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            model=request.model,
        )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion."""
        model = self.genai.GenerativeModel(
            model_name=request.model,
            generation_config={
                "temperature": request.temperature,
                "max_output_tokens": request.max_tokens,
                "top_p": request.top_p,
            },
            system_instruction=self._extract_system_prompt(request.messages),
        )

        # Tools already in Google-native format from ToolResolver
        tools = None
        if request.tools and self.supports_tools(request.model):
            tools = request.tools

        # Format messages
        contents = self._format_messages(request.messages)

        try:
            # Stream response
            response = await model.generate_content_async(
                contents,
                tools=tools,
                stream=True,
            )

            tool_calls_accumulated = []

            async for chunk in response:
                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    for part in candidate.content.parts:
                        if hasattr(part, "text") and part.text:
                            yield StreamDelta(type="text", content=part.text)
                        if hasattr(part, "function_call") and part.function_call:
                            tc = ToolCall(
                                id=f"call_{len(tool_calls_accumulated)}",
                                type="function",
                                function={
                                    "name": part.function_call.name,
                                    "arguments": json.dumps(dict(part.function_call.args)),
                                },
                            )
                            tool_calls_accumulated.append(tc)
                            yield StreamDelta(type="tool_call", tool_call=tc)

            # Get final usage
            input_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count

            yield StreamDelta(
                type="finish",
                finish_reason="stop",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except LLMError:
            raise
        except Exception as e:
            raise LLMError(
                message=f"Google Gemini streaming failed: {str(e)}",
                provider="google",
                details={"model": request.model, "error": str(e)},
            )

    @handle_provider_errors("google", "embedding")
    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Gemini embedding model."""
        model_name = model or "text-embedding-004"

        result = self.genai.embed_content(
            model=f"models/{model_name}",
            content=texts,
        )

        return result["embedding"] if isinstance(texts, str) else [
            r for r in result["embedding"]
        ]

    def list_models(self) -> list[str]:
        """List available models."""
        return [
            # Gemini 3.x (latest - Nov 2025)
            "gemini-3-pro",           # Most powerful, #1 on LMArena
            "gemini-3-deep-think",    # Extended reasoning
            "gemini-3-flash",         # Fast, default model
            # Gemini 2.5 (stable)
            "gemini-2.5-pro",         # Deep Think mode
            "gemini-2.5-flash",       # Fast and capable
            "gemini-2.5-flash-lite",  # Speed optimized
            # Gemini 2.0 (retiring Mar 2026)
            "gemini-2.0-pro",
            "gemini-2.0-flash",
            "gemini-2.0-flash-thinking",
            # Legacy (retired)
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]

    def resolve_model_alias(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        return True  # Assume newer models support tools

    def _format_messages(self, messages: list[Message]) -> list[dict]:
        """Format messages for Gemini API."""
        contents = []

        for msg in messages:
            if msg.role == "system":
                continue  # System message handled separately

            role = "user" if msg.role == "user" else "model"

            # Handle tool responses
            if msg.role == "tool" and msg.tool_call_id:
                contents.append({
                    "role": "function",
                    "parts": [{
                        "function_response": {
                            "name": msg.name or "function",
                            "response": {"result": msg.content},
                        }
                    }],
                })
            else:
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}],
                })

        return contents

    def _map_finish_reason(self, response) -> str:
        """Map Gemini finish reason to standard format."""
        if not response.candidates:
            return "stop"

        reason = response.candidates[0].finish_reason
        mapping = {
            1: "stop",      # STOP
            2: "length",    # MAX_TOKENS
            3: "safety",    # SAFETY
            4: "recitation",
            5: "other",
        }
        return mapping.get(reason, "stop")
