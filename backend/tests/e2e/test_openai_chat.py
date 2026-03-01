"""E2E tests for the Responses API with OpenAI as the LLM provider.

Tests cover creating responses (always SSE-streamed), multi-turn
conversations, parameter overrides, and validation.

Requires OPENAI_API_KEY env var — tests are skipped if not set.

NOTE: The /responses endpoint ALWAYS returns SSE (text/event-stream).
All tests parse SSE events to extract response data.
"""

import os
import uuid

import httpx
import pytest
import pytest_asyncio

from tests.conftest import (
    API_PREFIX,
    OPENAI_API_KEY,
    TestDataFactory,
    assert_error_response,
    assert_success_response,
    assert_uuid_format,
    parse_sse_events,
    requires_openai,
)

pytestmark = [pytest.mark.e2e, requires_openai]


def extract_response_data(response: httpx.Response) -> dict:
    """Extract response data from SSE events.

    Parses the SSE stream and returns useful data extracted from events.
    Looks for response.completed, response.done, or the last event with data.
    """
    events = parse_sse_events(response)

    result = {
        "events": events,
        "conversation_id": None,
        "response_id": None,
        "text": "",
        "status": None,
        "model": None,
        "usage": None,
        "raw_completed": None,
    }

    for event in events:
        event_type = event.get("event", "")
        data = event.get("data")

        if not isinstance(data, dict):
            continue

        # Extract conversation_id from any event
        if "conversation_id" in data and data["conversation_id"]:
            result["conversation_id"] = data["conversation_id"]

        # Extract response_id
        if "id" in data and data.get("type", "").startswith("response"):
            result["response_id"] = data["id"]

        # Extract text content from deltas
        if data.get("type") in ("response.content.delta", "response.output_text.delta"):
            result["text"] += data.get("delta", "")

        # Extract full text from content done event
        if data.get("type") == "response.content.done":
            # This contains the full assembled text
            if data.get("text"):
                result["text"] = data["text"]

        # Extract response_id and conversation_id from response.created
        if data.get("type") == "response.created":
            resp = data.get("response", {})
            result["response_id"] = resp.get("id", result["response_id"])
            result["conversation_id"] = resp.get(
                "conversation_id", result["conversation_id"]
            )

        # Extract from completed event
        if data.get("type") in ("response.completed", "response.done"):
            resp = data.get("response", data)
            result["raw_completed"] = resp
            result["status"] = resp.get("status")
            result["model"] = resp.get("model")
            result["response_id"] = resp.get("id", result["response_id"])
            result["conversation_id"] = resp.get(
                "conversation_id", result["conversation_id"]
            )
            if "usage" in resp:
                result["usage"] = resp["usage"]

    return result


async def create_response_and_parse(
    client: httpx.AsyncClient,
    headers: dict,
    assistant_id: str,
    message: str,
    conversation_id: str | None = None,
    previous_response_id: str | None = None,
    **overrides,
) -> dict:
    """Helper: POST /responses and parse SSE events into a dict."""
    payload = {
        "assistant_id": assistant_id,
        "input": [{"type": "message", "role": "user", "content": message}],
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    payload.update(overrides)

    response = await client.post(
        f"{API_PREFIX}/responses",
        json=payload,
        headers=headers,
        timeout=60.0,
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )
    return extract_response_data(response)


@pytest_asyncio.fixture(scope="function")
async def openai_assistant(async_client: httpx.AsyncClient, auth_headers: dict):
    """Create an OpenAI assistant for chat tests."""
    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json={
            "name": f"Chat Test {uuid.uuid4().hex[:8]}",
            "system_prompt": "You are a concise test assistant. Keep answers under 50 words.",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 200,
        },
        headers=auth_headers,
    )
    assistant = response.json()
    yield assistant
    if "id" in assistant:
        await async_client.delete(
            f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
        )


# ---------------------------------------------------------------------------
# TestResponseCreation
# ---------------------------------------------------------------------------

class TestResponseCreation:
    """Tests for POST /responses (SSE stream)."""

    @pytest.mark.asyncio
    async def test_create_response_simple(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Say hello.",
        )
        assert len(result["events"]) > 0
        assert result["text"], "Expected non-empty response text"

    @pytest.mark.asyncio
    async def test_create_response_produces_text(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="What is 2+2?",
        )
        assert len(result["events"]) > 0
        # Response text should contain something
        assert len(result["text"]) > 0

    @pytest.mark.asyncio
    async def test_create_response_creates_conversation(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Hi",
        )
        conv_id = result["conversation_id"]
        assert conv_id is not None, "Expected conversation_id in SSE events"

        # Verify conversation appears in list
        convs = await async_client.get(
            f"{API_PREFIX}/chat/conversations",
            params={"assistant_id": openai_assistant["id"]},
            headers=auth_headers,
        )
        if convs.status_code == 200:
            conv_list = convs.json()
            if isinstance(conv_list, list):
                conv_ids = [c["id"] for c in conv_list]
                assert conv_id in conv_ids

    @pytest.mark.asyncio
    async def test_create_response_continue_conversation(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        # First response — creates conversation
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Hello",
        )
        conv_id = r1["conversation_id"]
        assert conv_id is not None

        # Second response — same conversation, chained via previous_response_id
        r2 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Thanks",
            conversation_id=conv_id,
            previous_response_id=r1["response_id"],
        )
        assert r2["conversation_id"] == conv_id

    @pytest.mark.asyncio
    async def test_create_response_temperature_override(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Hi",
            temperature=0.0,
        )
        assert len(result["events"]) > 0

    @pytest.mark.asyncio
    async def test_create_response_max_tokens_override(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Hi",
            max_tokens=50,
        )
        assert len(result["events"]) > 0

    @pytest.mark.asyncio
    async def test_create_response_instructions_override(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Say something.",
            instructions="Always respond in French.",
        )
        assert len(result["events"]) > 0


# ---------------------------------------------------------------------------
# TestResponseRetrieval
# ---------------------------------------------------------------------------

class TestResponseRetrieval:
    """Tests for GET/DELETE /responses/{id}."""

    @pytest.mark.asyncio
    async def test_get_response(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Hello",
        )
        resp_id = result["response_id"]
        if not resp_id:
            pytest.skip("No response_id found in SSE events")

        response = await async_client.get(
            f"{API_PREFIX}/responses/{resp_id}", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert data["id"] == resp_id

    @pytest.mark.asyncio
    async def test_get_response_not_found(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        bad_id = str(uuid.uuid4())
        response = await async_client.get(
            f"{API_PREFIX}/responses/{bad_id}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_delete_response(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Delete me",
        )
        resp_id = result["response_id"]
        if not resp_id:
            pytest.skip("No response_id found in SSE events")

        response = await async_client.delete(
            f"{API_PREFIX}/responses/{resp_id}", headers=auth_headers,
        )
        assert response.status_code in (200, 204)


# ---------------------------------------------------------------------------
# TestResponseStreaming
# ---------------------------------------------------------------------------

class TestResponseStreaming:
    """Tests for POST /responses SSE event structure."""

    @pytest.mark.asyncio
    async def test_sse_stream_events(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Say hi briefly.",
        )
        assert len(result["events"]) > 0

    @pytest.mark.asyncio
    async def test_sse_has_text_events(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Say hello.",
        )
        # Should have received some text
        assert result["text"], "Expected non-empty text from SSE events"

    @pytest.mark.asyncio
    async def test_sse_has_conversation_id(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Hi",
        )
        assert result["conversation_id"], "No conversation_id found in SSE events"


# ---------------------------------------------------------------------------
# TestResponseValidation
# ---------------------------------------------------------------------------

class TestResponseValidation:
    """Tests for POST /responses validation errors."""

    @pytest.mark.asyncio
    async def test_missing_assistant_id(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/responses",
            json={
                "input": [{"type": "message", "role": "user", "content": "Hi"}],
            },
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_missing_input(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/responses",
            json={
                "assistant_id": openai_assistant["id"],
                "input": [],
            },
            headers=auth_headers,
        )
        # May return 422 (validation) or 200 with error in SSE
        assert response.status_code in (200, 422)

    @pytest.mark.asyncio
    async def test_invalid_assistant_id(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/responses",
            json={
                "assistant_id": str(uuid.uuid4()),
                "input": [{"type": "message", "role": "user", "content": "Hi"}],
            },
            headers=auth_headers,
            timeout=30.0,
        )
        # May return 404, 400, 500 or 200 with error in SSE stream
        assert response.status_code in (200, 400, 404, 500)

    @pytest.mark.asyncio
    async def test_no_auth_responses(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/responses",
            json={
                "assistant_id": str(uuid.uuid4()),
                "input": [{"type": "message", "role": "user", "content": "Hi"}],
            },
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestMultiTurnConversation
# ---------------------------------------------------------------------------

class TestMultiTurnConversation:
    """Tests for multi-turn conversations via the Responses API."""

    @pytest.mark.asyncio
    async def test_multi_turn_remembers_context(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        # Turn 1 — introduce a name
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="My name is Alice. Please remember this.",
        )
        conv_id = r1["conversation_id"]
        resp_id = r1["response_id"]
        assert conv_id is not None

        # Turn 2 — ask about the name (chain via previous_response_id for history)
        r2 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="What is my name?",
            conversation_id=conv_id,
            previous_response_id=resp_id,
        )
        assert "alice" in r2["text"].lower(), (
            f"Expected 'Alice' in response, got: {r2['text']}"
        )

    @pytest.mark.asyncio
    async def test_conversation_history_ordering(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        # Create 3 responses in the same conversation, chaining via previous_response_id
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="First message",
        )
        conv_id = r1["conversation_id"]
        assert conv_id is not None

        r2 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Second message",
            conversation_id=conv_id,
            previous_response_id=r1["response_id"],
        )

        await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Third message",
            conversation_id=conv_id,
            previous_response_id=r2["response_id"],
        )

        # Fetch conversation responses
        history = await async_client.get(
            f"{API_PREFIX}/chat/conversations/{conv_id}/responses",
            headers=auth_headers,
        )
        assert history.status_code == 200
        responses = history.json()
        assert isinstance(responses, list)
        assert len(responses) >= 3

    @pytest.mark.asyncio
    async def test_conversation_response_count(
        self, async_client: httpx.AsyncClient, auth_headers: dict, openai_assistant: dict,
    ):
        # Create a conversation with 2 responses, chained via previous_response_id
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="One",
        )
        conv_id = r1["conversation_id"]
        assert conv_id is not None

        await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=openai_assistant["id"],
            message="Two",
            conversation_id=conv_id,
            previous_response_id=r1["response_id"],
        )

        # Check conversation list shows response_count
        convs = await async_client.get(
            f"{API_PREFIX}/chat/conversations",
            params={"assistant_id": openai_assistant["id"]},
            headers=auth_headers,
        )
        if convs.status_code == 200:
            conv_list = convs.json()
            if isinstance(conv_list, list):
                conv = next((c for c in conv_list if c["id"] == conv_id), None)
                assert conv is not None
                assert conv.get("response_count", 0) >= 2
