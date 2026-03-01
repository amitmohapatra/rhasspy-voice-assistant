"""AWS Bedrock LLM Provider - Access Claude, Llama, Mistral, Titan via AWS."""

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


class AWSBedrockProvider(LLMProvider):
    """AWS Bedrock provider for accessing multiple foundation models."""

    provider_name = "bedrock"

    # Model mappings with their configurations (as of late 2025)
    MODELS = {
        # Anthropic Claude 4.x models (2025)
        "anthropic.claude-sonnet-4-20250115-v1:0": {"vendor": "anthropic", "tools": True, "context": 1000000},
        "anthropic.claude-3-7-sonnet-20250219-v1:0": {"vendor": "anthropic", "tools": True},
        "anthropic.claude-3-5-sonnet-20241022-v2:0": {"vendor": "anthropic", "tools": True},
        "anthropic.claude-3-5-haiku-20241022-v1:0": {"vendor": "anthropic", "tools": True},
        "anthropic.claude-3-opus-20240229-v1:0": {"vendor": "anthropic", "tools": True},
        "anthropic.claude-3-sonnet-20240229-v1:0": {"vendor": "anthropic", "tools": True},
        "anthropic.claude-3-haiku-20240307-v1:0": {"vendor": "anthropic", "tools": True},
        # Meta Llama 4 models (2025)
        "meta.llama4-scout-17b-instruct-v1:0": {"vendor": "meta", "tools": True, "vision": True, "context": 10000000},
        "meta.llama4-maverick-17b-instruct-v1:0": {"vendor": "meta", "tools": True, "vision": True, "context": 1000000},
        # Meta Llama 3.x models
        "meta.llama3-3-70b-instruct-v1:0": {"vendor": "meta", "tools": True},
        "meta.llama3-2-90b-instruct-v1:0": {"vendor": "meta", "tools": True, "vision": True},
        "meta.llama3-2-11b-instruct-v1:0": {"vendor": "meta", "tools": True, "vision": True},
        "meta.llama3-1-405b-instruct-v1:0": {"vendor": "meta", "tools": True},
        "meta.llama3-1-70b-instruct-v1:0": {"vendor": "meta", "tools": True},
        "meta.llama3-1-8b-instruct-v1:0": {"vendor": "meta", "tools": True},
        # Mistral models
        "mistral.mistral-large-2411-v1:0": {"vendor": "mistral", "tools": True},
        "mistral.mistral-large-2407-v1:0": {"vendor": "mistral", "tools": True},
        "mistral.mixtral-8x7b-instruct-v0:1": {"vendor": "mistral", "tools": True},
        "mistral.mistral-7b-instruct-v0:2": {"vendor": "mistral", "tools": False},
        # Amazon Titan
        "amazon.titan-text-premier-v1:0": {"vendor": "amazon", "tools": False},
        "amazon.titan-text-express-v1": {"vendor": "amazon", "tools": False},
        "amazon.titan-text-lite-v1": {"vendor": "amazon", "tools": False},
        # Cohere Command A (2025)
        "cohere.command-a-03-2025-v1:0": {"vendor": "cohere", "tools": True, "context": 256000},
        "cohere.command-r-plus-08-2024-v1:0": {"vendor": "cohere", "tools": True},
        "cohere.command-r-plus-v1:0": {"vendor": "cohere", "tools": True},
        "cohere.command-r-08-2024-v1:0": {"vendor": "cohere", "tools": True},
        "cohere.command-r-v1:0": {"vendor": "cohere", "tools": True},
        # AI21 Jamba
        "ai21.jamba-1-5-large-v1:0": {"vendor": "ai21", "tools": False},
        "ai21.jamba-1-5-mini-v1:0": {"vendor": "ai21", "tools": False},
        # DeepSeek (2025)
        "deepseek.deepseek-r1-v1:0": {"vendor": "deepseek", "tools": False, "reasoning": True},
        # OpenAI on Bedrock (2025)
        "openai.gpt-4o-v1:0": {"vendor": "openai", "tools": True},
        # Qwen (2025)
        "qwen.qwen2-5-72b-instruct-v1:0": {"vendor": "qwen", "tools": True},
    }

    # Friendly aliases
    MODEL_ALIASES = {
        # Claude 4.x
        "claude-sonnet-4": "anthropic.claude-sonnet-4-20250115-v1:0",
        "claude-3.7-sonnet": "anthropic.claude-3-7-sonnet-20250219-v1:0",
        "claude-3.5-sonnet": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "claude-3.5-haiku": "anthropic.claude-3-5-haiku-20241022-v1:0",
        "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
        # Llama 4
        "llama-4-scout": "meta.llama4-scout-17b-instruct-v1:0",
        "llama-4-maverick": "meta.llama4-maverick-17b-instruct-v1:0",
        # Llama 3.x
        "llama-3.3-70b": "meta.llama3-3-70b-instruct-v1:0",
        "llama-3.2-90b": "meta.llama3-2-90b-instruct-v1:0",
        "llama-3.1-405b": "meta.llama3-1-405b-instruct-v1:0",
        # Mistral
        "mistral-large": "mistral.mistral-large-2411-v1:0",
        "mixtral-8x7b": "mistral.mixtral-8x7b-instruct-v0:1",
        # Cohere
        "command-a": "cohere.command-a-03-2025-v1:0",
        "command-r-plus": "cohere.command-r-plus-08-2024-v1:0",
        # Amazon
        "titan-premier": "amazon.titan-text-premier-v1:0",
        # DeepSeek
        "deepseek-r1": "deepseek.deepseek-r1-v1:0",
        # Qwen
        "qwen-2.5-72b": "qwen.qwen2-5-72b-instruct-v1:0",
    }

    def __init__(
        self,
        region: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        profile_name: str | None = None,
    ) -> None:
        self.region = region or getattr(settings, "aws_region", "us-east-1")
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.profile_name = profile_name

        try:
            import boto3
            from botocore.config import Config

            config = Config(
                region_name=self.region,
                retries={"max_attempts": 3, "mode": "adaptive"},
            )

            session_kwargs = {}
            if profile_name:
                session_kwargs["profile_name"] = profile_name
            elif aws_access_key_id and aws_secret_access_key:
                session_kwargs["aws_access_key_id"] = aws_access_key_id
                session_kwargs["aws_secret_access_key"] = aws_secret_access_key

            session = boto3.Session(**session_kwargs)
            self.client = session.client("bedrock-runtime", config=config)

        except ImportError:
            raise LLMError(
                "boto3 package not installed. Run: pip install boto3",
                provider="bedrock",
            )
        except Exception as e:
            raise LLMError(
                f"Failed to initialize Bedrock client: {str(e)}",
                provider="bedrock",
            )

    def _resolve_model(self, model: str) -> str:
        """Resolve model alias to full model ID."""
        return self.MODEL_ALIASES.get(model, model)

    def _get_vendor(self, model: str) -> str:
        """Get vendor from model ID."""
        model = self._resolve_model(model)
        if model in self.MODELS:
            return self.MODELS[model]["vendor"]
        # Infer from model ID prefix
        if model.startswith("anthropic"):
            return "anthropic"
        elif model.startswith("meta"):
            return "meta"
        elif model.startswith("mistral"):
            return "mistral"
        elif model.startswith("amazon"):
            return "amazon"
        elif model.startswith("cohere"):
            return "cohere"
        elif model.startswith("ai21"):
            return "ai21"
        return "unknown"

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion via Bedrock Converse API."""
        try:
            model_id = self._resolve_model(request.model)
            vendor = self._get_vendor(model_id)

            # Build converse request
            converse_params = self._build_converse_request(request, model_id, vendor)

            # Call Bedrock
            import asyncio
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.converse(**converse_params)
            )

            # Parse response
            content = ""
            tool_calls = []

            output = response.get("output", {})
            message = output.get("message", {})

            for block in message.get("content", []):
                if "text" in block:
                    content += block["text"]
                if "toolUse" in block:
                    tool_use = block["toolUse"]
                    tool_calls.append(
                        ToolCall(
                            id=tool_use["toolUseId"],
                            type="function",
                            function={
                                "name": tool_use["name"],
                                "arguments": json.dumps(tool_use.get("input", {})),
                            },
                        )
                    )

            # Get usage
            usage = response.get("usage", {})

            return CompletionResponse(
                content=content or None,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=response.get("stopReason", "stop"),
                input_tokens=usage.get("inputTokens", 0),
                output_tokens=usage.get("outputTokens", 0),
                total_tokens=usage.get("totalTokens", 0),
                model=model_id,
            )

        except Exception as e:
            raise LLMError(
                message=f"Bedrock completion failed: {str(e)}",
                provider="bedrock",
                details={"model": request.model, "error": str(e)},
            )

    async def stream(
        self, request: CompletionRequest
    ) -> AsyncGenerator[StreamDelta, None]:
        """Streaming completion via Bedrock Converse Stream API."""
        try:
            model_id = self._resolve_model(request.model)
            vendor = self._get_vendor(model_id)

            # Build converse request
            converse_params = self._build_converse_request(request, model_id, vendor)

            # Call streaming API
            import asyncio
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.converse_stream(**converse_params)
            )

            stream = response.get("stream", [])
            current_tool_use = None
            input_tokens = 0
            output_tokens = 0

            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        yield StreamDelta(type="text", content=delta["text"])
                    if "toolUse" in delta:
                        tool_use = delta["toolUse"]
                        if "toolUseId" in tool_use:
                            current_tool_use = {
                                "id": tool_use["toolUseId"],
                                "name": tool_use.get("name", ""),
                                "input": "",
                            }
                        if "input" in tool_use and current_tool_use:
                            current_tool_use["input"] += tool_use["input"]

                if "contentBlockStop" in event and current_tool_use:
                    yield StreamDelta(
                        type="tool_call",
                        tool_call=ToolCall(
                            id=current_tool_use["id"],
                            type="function",
                            function={
                                "name": current_tool_use["name"],
                                "arguments": current_tool_use["input"],
                            },
                        ),
                    )
                    current_tool_use = None

                if "metadata" in event:
                    usage = event["metadata"].get("usage", {})
                    input_tokens = usage.get("inputTokens", 0)
                    output_tokens = usage.get("outputTokens", 0)

                if "messageStop" in event:
                    yield StreamDelta(
                        type="finish",
                        finish_reason=event["messageStop"].get("stopReason", "stop"),
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )

        except Exception as e:
            raise LLMError(
                message=f"Bedrock streaming failed: {str(e)}",
                provider="bedrock",
                details={"model": request.model, "error": str(e)},
            )

    def _build_converse_request(
        self, request: CompletionRequest, model_id: str, vendor: str
    ) -> dict:
        """Build Bedrock Converse API request."""
        # Format messages
        messages = []
        system_prompt = None

        for msg in request.messages:
            if msg.role == "system":
                system_prompt = msg.content
                continue

            content = []

            if msg.content:
                content.append({"text": msg.content})

            # Handle tool results
            if msg.role == "tool" and msg.tool_call_id:
                content = [{
                    "toolResult": {
                        "toolUseId": msg.tool_call_id,
                        "content": [{"text": msg.content}],
                    }
                }]

            if content:
                role = "user" if msg.role in ("user", "tool") else "assistant"
                messages.append({"role": role, "content": content})

        params = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {
                "temperature": request.temperature,
                "maxTokens": request.max_tokens,
                "topP": request.top_p,
            },
        }

        if system_prompt:
            params["system"] = [{"text": system_prompt}]

        # Add tools (already in Bedrock-native format from ToolResolver)
        if request.tools and self.supports_tools(model_id):
            params["toolConfig"] = {"tools": request.tools}

        return params

    async def embed(
        self,
        texts: list[str],
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using Titan or Cohere embedding models."""
        try:
            model_id = model or "amazon.titan-embed-text-v2:0"

            embeddings = []
            for text in texts:
                if model_id.startswith("amazon.titan"):
                    body = json.dumps({"inputText": text})
                elif model_id.startswith("cohere"):
                    body = json.dumps({
                        "texts": [text],
                        "input_type": "search_document",
                    })
                else:
                    body = json.dumps({"inputText": text})

                import asyncio
                response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.client.invoke_model(
                        modelId=model_id,
                        body=body,
                    )
                )

                result = json.loads(response["body"].read())

                if model_id.startswith("cohere"):
                    embeddings.append(result["embeddings"][0])
                else:
                    embeddings.append(result["embedding"])

            return embeddings

        except Exception as e:
            raise LLMError(
                message=f"Bedrock embedding failed: {str(e)}",
                provider="bedrock",
                details={"model": model, "error": str(e)},
            )

    def list_models(self) -> list[str]:
        """List available models."""
        return list(self.MODELS.keys()) + list(self.MODEL_ALIASES.keys())

    def supports_tools(self, model: str) -> bool:
        """Check if model supports function calling."""
        model = self._resolve_model(model)
        if model in self.MODELS:
            return self.MODELS[model].get("tools", False)
        return False
