"""Unit tests for OpenAI Responses API provider."""

from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.providers.openai_provider import OpenAIProvider, complete_with_web_search
from src.llm.providers.base import CompletionRequest, ToolCall, Message, ToolDefinition


class TestOpenAIProviderInit:
    """Test OpenAI provider initialization."""

    def test_init_with_api_key(self):
        """Test initialization with explicit API key."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = None
            mock_settings.openai_base_url = None

            provider = OpenAIProvider(api_key="test-key")

            assert provider.api_key == "test-key"
            assert provider.base_url == "https://api.openai.com/v1"

    def test_init_from_settings(self):
        """Test initialization from settings."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "settings-key"
            mock_settings.openai_base_url = None

            provider = OpenAIProvider()

            assert provider.api_key == "settings-key"

    def test_init_custom_base_url(self):
        """Test initialization with custom base URL."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = "https://custom.api.com/v1"

            provider = OpenAIProvider()

            assert provider.base_url == "https://custom.api.com/v1"

    def test_init_no_api_key_raises(self):
        """Test that missing API key raises error."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = None
            mock_settings.openai_base_url = None

            with pytest.raises(Exception) as exc_info:
                OpenAIProvider()

            assert "API key not configured" in str(exc_info.value)


class TestOpenAIProviderModels:
    """Test model support checks using pattern-based capability detection.

    Note: These tests use the CAPABILITY_PATTERNS fallback patterns.
    In production, capabilities are queried from the database via CapabilityService.
    """

    @pytest.fixture
    def provider(self):
        """Create a provider instance."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None
            return OpenAIProvider()

    def test_supports_tools_gpt4o(self, provider):
        """Test that GPT-4o supports tools via pattern matching."""
        assert provider.supports_tools("gpt-4o") is True
        assert provider.supports_tools("gpt-4o-mini") is True

    def test_supports_tools_reasoning_models(self, provider):
        """Test that reasoning models don't support standard tools (pattern: gpt-*)."""
        assert provider.supports_tools("o1") is False
        assert provider.supports_tools("o1-mini") is False
        assert provider.supports_tools("o3-mini") is False

    def test_supports_web_search(self, provider):
        """Test web search model support via pattern matching (gpt-4o*, gpt-4.1*)."""
        assert provider.supports_web_search("gpt-4o") is True
        assert provider.supports_web_search("gpt-4o-mini") is True
        assert provider.supports_web_search("gpt-4.1") is True
        assert provider.supports_web_search("gpt-4-turbo") is False
        assert provider.supports_web_search("o1") is False

    def test_is_reasoning_model(self, provider):
        """Test reasoning model detection via pattern matching (o1*, o3*)."""
        assert provider.is_reasoning_model("o1") is True
        assert provider.is_reasoning_model("o1-mini") is True
        assert provider.is_reasoning_model("o1-preview") is True
        assert provider.is_reasoning_model("o3-mini") is True
        assert provider.is_reasoning_model("gpt-4o") is False
        assert provider.is_reasoning_model("gpt-3.5-turbo") is False

    def test_list_models(self, provider):
        """Test listing available models."""
        models = provider.list_models()

        assert "gpt-4o" in models
        assert "gpt-4o-mini" in models
        assert "gpt-4.1" in models
        assert "o1" in models
        assert "o3-mini" in models
        assert len(models) > 5


class TestBuildResponsesPayload:
    """Test Responses API payload building."""

    @pytest.fixture
    def provider(self):
        """Create a provider instance."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None
            return OpenAIProvider()

    def test_basic_payload(self, provider):
        """Test basic payload structure."""
        request = CompletionRequest(
            model="gpt-4o",
            messages=[Message(role="user", content="Hello")],
            temperature=0.7,
            max_tokens=1000,
        )

        payload = provider._build_responses_payload(request)

        assert payload["model"] == "gpt-4o"
        assert payload["temperature"] == 0.7
        assert payload["max_output_tokens"] == 1000
        assert "input" in payload

    def test_system_message_handling(self, provider):
        """Test that system messages are converted to instructions."""
        request = CompletionRequest(
            model="gpt-4o",
            messages=[
                Message(role="system", content="You are a helpful assistant."),
                Message(role="user", content="Hello"),
            ],
        )

        payload = provider._build_responses_payload(request)

        assert "instructions" in payload
        assert "helpful assistant" in payload["instructions"]
        # System messages should not appear in input with [System Instructions] prefix
        for msg in payload["input"]:
            assert not msg["content"].startswith("[System Instructions]")

    def test_web_search_tool(self, provider):
        """Test web search tool is added when requested."""
        request = CompletionRequest(
            model="gpt-4o",
            messages=[Message(role="user", content="Search the web")],
            tools=[ToolDefinition(type="web_search")],
        )

        payload = provider._build_responses_payload(request)

        assert "tools" in payload
        assert {"type": "web_search"} in payload["tools"]

    def test_function_tools(self, provider):
        """Test function tools are added correctly."""
        request = CompletionRequest(
            model="gpt-4o",
            messages=[Message(role="user", content="Use a tool")],
            tools=[
                ToolDefinition(
                    type="function",
                    function={
                        "name": "get_weather",
                        "description": "Get the weather",
                        "parameters": {
                            "type": "object",
                            "properties": {"location": {"type": "string"}},
                        },
                    },
                )
            ],
        )

        payload = provider._build_responses_payload(request)

        assert "tools" in payload
        function_tools = [t for t in payload["tools"] if t["type"] == "function"]
        assert len(function_tools) == 1
        assert function_tools[0]["name"] == "get_weather"

    def test_streaming_flag(self, provider):
        """Test streaming flag is set correctly."""
        request = CompletionRequest(
            model="gpt-4o",
            messages=[Message(role="user", content="Hello")],
        )

        payload_no_stream = provider._build_responses_payload(request, stream=False)
        payload_stream = provider._build_responses_payload(request, stream=True)

        assert "stream" not in payload_no_stream
        assert payload_stream.get("stream") is True


class TestOpenAIProviderComplete:
    """Test non-streaming completion."""

    @pytest.fixture
    def provider(self):
        """Create a provider instance."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None
            return OpenAIProvider()

    @pytest.mark.asyncio
    async def test_complete_success(self, provider):
        """Test successful completion."""
        mock_response = {
            "id": "resp_123",
            "model": "gpt-4o",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Hello! How can I help?"}],
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            request = CompletionRequest(
                model="gpt-4o",
                messages=[Message(role="user", content="Hello")],
            )

            response = await provider.complete(request)

            assert response.content == "Hello! How can I help?"
            assert response.input_tokens == 10
            assert response.output_tokens == 20
            assert response.model == "gpt-4o"

    @pytest.mark.asyncio
    async def test_complete_with_function_call(self, provider):
        """Test completion with function call response."""
        mock_response = {
            "id": "resp_123",
            "model": "gpt-4o",
            "status": "completed",
            "output": [
                {
                    "type": "function_call",
                    "call_id": "call_abc123",
                    "name": "get_weather",
                    "arguments": '{"location": "San Francisco"}',
                }
            ],
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
        }

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json.return_value = mock_response
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            request = CompletionRequest(
                model="gpt-4o",
                messages=[Message(role="user", content="What's the weather?")],
                tools=[
                    ToolDefinition(
                        type="function",
                        function={
                            "name": "get_weather",
                            "description": "Get weather",
                            "parameters": {"type": "object"},
                        },
                    )
                ],
            )

            response = await provider.complete(request)

            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].name == "get_weather"
            assert response.tool_calls[0].id == "call_abc123"

    @pytest.mark.asyncio
    async def test_complete_api_error(self, provider):
        """Test API error handling."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = MagicMock()
            mock_response_obj.status_code = 400
            mock_response_obj.content = b'{"error": {"message": "Invalid request"}}'
            mock_response_obj.text = '{"error": {"message": "Invalid request"}}'
            mock_response_obj.json.return_value = {
                "error": {"message": "Invalid request"}
            }
            mock_client.post = AsyncMock(return_value=mock_response_obj)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            request = CompletionRequest(
                model="gpt-4o",
                messages=[Message(role="user", content="Hello")],
            )

            with pytest.raises(Exception) as exc_info:
                await provider.complete(request)

            assert "Invalid request" in str(exc_info.value)


class TestOpenAIProviderStream:
    """Test streaming completion."""

    @pytest.fixture
    def provider(self):
        """Create a provider instance."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None
            return OpenAIProvider()

    @pytest.mark.asyncio
    async def test_stream_text_deltas(self, provider):
        """Test streaming text deltas."""
        # Simulate SSE stream lines
        stream_lines = [
            'data: {"type": "response.output_text.delta", "delta": "Hello"}',
            'data: {"type": "response.output_text.delta", "delta": " world"}',
            'data: {"type": "response.completed", "response": {"usage": {"input_tokens": 5, "output_tokens": 2}}}',
            "data: [DONE]",
        ]

        async def mock_aiter_lines():
            for line in stream_lines:
                yield line

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_stream = AsyncMock()
            mock_stream.status_code = 200
            mock_stream.aiter_lines = mock_aiter_lines
            mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
            mock_stream.__aexit__ = AsyncMock(return_value=None)

            mock_client.stream = MagicMock(return_value=mock_stream)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            request = CompletionRequest(
                model="gpt-4o",
                messages=[Message(role="user", content="Hello")],
            )

            deltas = []
            async for delta in provider.stream(request):
                deltas.append(delta)

            # Should have text deltas, a completed event, and a finish event
            text_deltas = [d for d in deltas if d.type == "text"]
            assert len(text_deltas) >= 1


class TestCompleteWithWebSearch:
    """Test the web search helper function."""

    @pytest.mark.asyncio
    async def test_complete_with_web_search_creates_request(self):
        """Test that web search helper creates correct request."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None

            with patch.object(
                OpenAIProvider, "complete", new_callable=AsyncMock
            ) as mock_complete:
                mock_complete.return_value = MagicMock(
                    content="Search results...",
                    input_tokens=10,
                    output_tokens=20,
                )

                response = await complete_with_web_search(
                    messages=[{"role": "user", "content": "Latest news"}],
                    model="gpt-4o",
                )

                assert mock_complete.called
                call_args = mock_complete.call_args[0][0]
                assert call_args.model == "gpt-4o"
                assert any(t.type == "web_search" for t in call_args.tools)


class TestOpenAIProviderEmbed:
    """Test embedding generation."""

    @pytest.fixture
    def provider(self):
        """Create a provider instance."""
        with patch("src.llm.providers.openai_provider.settings") as mock_settings:
            mock_settings.openai_api_key = "test-key"
            mock_settings.openai_base_url = None
            mock_settings.default_embedding_model = "text-embedding-3-small"
            return OpenAIProvider()

    @pytest.mark.asyncio
    async def test_embed_uses_openai_client(self, provider):
        """Test that embed uses the OpenAI client (not Responses API)."""
        mock_embedding = MagicMock()
        mock_embedding.embedding = [0.1, 0.2, 0.3]

        mock_response = MagicMock()
        mock_response.data = [mock_embedding]

        provider.client.embeddings.create = AsyncMock(return_value=mock_response)

        embeddings = await provider.embed(["Hello world"])

        assert embeddings == [[0.1, 0.2, 0.3]]
        provider.client.embeddings.create.assert_called_once()
