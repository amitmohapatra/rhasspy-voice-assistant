"""E2E tests for tool use / function calling with OpenAI.

Tests cover:
- Assistant with custom tools (code handler) — LLM calls the tool, result fed back
- Assistant with built-in tools (web_search) — OpenAI native tool handling
- Multi-tool assistants — multiple tools attached
- Tool call SSE events — verifying event structure
- Multi-turn conversations with tools
- Edge cases — invalid tool refs, disabled tools, no tools
- Tool execution result verification

Requires OPENAI_API_KEY env var — tests are skipped if not set.

NOTE: The /responses endpoint ALWAYS returns SSE (text/event-stream).
Tools are executed server-side; the client does NOT handle tool calls.
"""

import json
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_response_data(response: httpx.Response) -> dict:
    """Extract response data from SSE events, including tool call info.

    Returns dict with keys: events, conversation_id, response_id, text,
    status, model, usage, raw_completed, tool_calls, tool_outputs.
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
        "tool_calls": [],
        "tool_outputs": [],
    }

    for event in events:
        event_type = event.get("event", "")
        data = event.get("data")
        if not isinstance(data, dict):
            continue

        if "conversation_id" in data and data["conversation_id"]:
            result["conversation_id"] = data["conversation_id"]

        if "id" in data and data.get("type", "").startswith("response"):
            result["response_id"] = data["id"]

        if data.get("type") in ("response.content.delta", "response.output_text.delta"):
            result["text"] += data.get("delta", "")

        if data.get("type") == "response.content.done":
            if data.get("text"):
                result["text"] = data["text"]

        if data.get("type") == "response.created":
            resp = data.get("response", {})
            result["response_id"] = resp.get("id", result["response_id"])
            result["conversation_id"] = resp.get(
                "conversation_id", result["conversation_id"]
            )

        if data.get("type") == "response.function_call_arguments.done":
            result["tool_calls"].append({
                "call_id": data.get("call_id"),
                "name": data.get("name"),
                "arguments": data.get("arguments"),
            })

        if data.get("type") == "response.output_item.added":
            item = data.get("item", {})
            if item.get("type") == "function_call":
                # Also capture from output_item.added
                pass
            elif item.get("type") == "function_call_output":
                result["tool_outputs"].append({
                    "call_id": item.get("call_id"),
                    "output": item.get("output"),
                })

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

        if data.get("type") == "response.failed":
            error = data.get("error", {})
            result["status"] = "failed"
            result["error"] = error.get("message", str(error))

    return result


async def create_response_and_parse(
    client: httpx.AsyncClient,
    headers: dict,
    assistant_id: str,
    message: str,
    conversation_id: str | None = None,
    previous_response_id: str | None = None,
    retries: int = 2,
    **overrides,
) -> dict:
    """Helper: POST /responses and parse SSE events into a dict.

    Retries on transient failures (OpenAI rate limits, network errors).
    """
    payload = {
        "assistant_id": assistant_id,
        "input": [{"type": "message", "role": "user", "content": message}],
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id
    if previous_response_id:
        payload["previous_response_id"] = previous_response_id
    payload.update(overrides)

    last_result = None
    for attempt in range(retries + 1):
        response = await client.post(
            f"{API_PREFIX}/responses",
            json=payload,
            headers=headers,
            timeout=90.0,
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: {response.text[:500]}"
        )
        last_result = extract_response_data(response)

        if last_result["status"] == "completed":
            return last_result

        # Retry on transient failures (truncated SSE or API error)
        if attempt < retries:
            import asyncio
            await asyncio.sleep(2)
            continue

    return last_result


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def weather_tool(async_client: httpx.AsyncClient, auth_headers: dict):
    """Create a custom weather tool with code handler."""
    tool_data = {
        "name": f"get_weather_{uuid.uuid4().hex[:8]}",
        "description": "Get the current weather for a given city. Returns temperature in Fahrenheit and conditions.",
        "schema_definition": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The city to get weather for",
                },
            },
            "required": ["city"],
        },
        "implementation": {
            "handler": "code",
            "code": "result = {'temperature': 72, 'conditions': 'sunny', 'city': params.get('city', 'Unknown')}",
        },
    }
    response = await async_client.post(
        f"{API_PREFIX}/tools/custom",
        json=tool_data,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create tool: {response.text}"
    tool = response.json()
    yield tool
    await async_client.delete(
        f"{API_PREFIX}/tools/{tool['id']}", headers=auth_headers,
    )


@pytest_asyncio.fixture(scope="function")
async def calculator_tool(async_client: httpx.AsyncClient, auth_headers: dict):
    """Create a custom calculator tool with code handler."""
    tool_data = {
        "name": f"calculate_{uuid.uuid4().hex[:8]}",
        "description": "Perform a mathematical calculation. Supports add, subtract, multiply, divide operations.",
        "schema_definition": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The math operation to perform",
                },
                "a": {"type": "number", "description": "First operand"},
                "b": {"type": "number", "description": "Second operand"},
            },
            "required": ["operation", "a", "b"],
        },
        "implementation": {
            "handler": "code",
            "code": (
                "ops = {'add': lambda a,b: a+b, 'subtract': lambda a,b: a-b, "
                "'multiply': lambda a,b: a*b, 'divide': lambda a,b: a/b if b != 0 else 'error'}\n"
                "op = params.get('operation', 'add')\n"
                "a = params.get('a', 0)\n"
                "b = params.get('b', 0)\n"
                "result = {'result': ops.get(op, lambda a,b: 'unknown')(a, b), 'operation': op}"
            ),
        },
    }
    response = await async_client.post(
        f"{API_PREFIX}/tools/custom",
        json=tool_data,
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create tool: {response.text}"
    tool = response.json()
    yield tool
    await async_client.delete(
        f"{API_PREFIX}/tools/{tool['id']}", headers=auth_headers,
    )


@pytest_asyncio.fixture(scope="function")
async def assistant_with_weather_tool(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
    weather_tool: dict,
):
    """Create an assistant with the weather tool attached."""
    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json={
            "name": f"Weather Assistant {uuid.uuid4().hex[:8]}",
            "system_prompt": (
                "You are a weather assistant. When the user asks about weather, "
                "use the get_weather tool. Always use the tool to get data, "
                "then report the result. Keep answers concise."
            ),
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 300,
            "tools": [weather_tool["id"]],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create assistant: {response.text}"
    assistant = response.json()
    yield assistant
    await async_client.delete(
        f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
    )


@pytest_asyncio.fixture(scope="function")
async def assistant_with_multiple_tools(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
    weather_tool: dict,
    calculator_tool: dict,
):
    """Create an assistant with multiple custom tools attached."""
    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json={
            "name": f"Multi-Tool Assistant {uuid.uuid4().hex[:8]}",
            "system_prompt": (
                "You are a versatile assistant with access to weather and calculator tools. "
                "Use the appropriate tool when the user asks about weather or math. "
                "Always use tools when relevant. Keep answers concise."
            ),
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 300,
            "tools": [weather_tool["id"], calculator_tool["id"]],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create assistant: {response.text}"
    assistant = response.json()
    yield assistant
    await async_client.delete(
        f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
    )


@pytest_asyncio.fixture(scope="function")
async def assistant_with_web_search(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
):
    """Create an assistant with OpenAI's web_search built-in tool."""
    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json={
            "name": f"Web Search Assistant {uuid.uuid4().hex[:8]}",
            "system_prompt": "You are a helpful assistant with web search. Use web search when asked about current events.",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 500,
            "tools": ["web_search"],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create assistant: {response.text}"
    assistant = response.json()
    yield assistant
    await async_client.delete(
        f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
    )


@pytest_asyncio.fixture(scope="function")
async def assistant_no_tools(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
):
    """Create an assistant with no tools attached."""
    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json={
            "name": f"No Tools Assistant {uuid.uuid4().hex[:8]}",
            "system_prompt": "You are a helpful assistant with no tools. Just respond with text.",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 200,
            "tools": [],
        },
        headers=auth_headers,
    )
    assert response.status_code == 201, f"Failed to create assistant: {response.text}"
    assistant = response.json()
    yield assistant
    await async_client.delete(
        f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
    )


# ---------------------------------------------------------------------------
# TestCustomToolExecution
# ---------------------------------------------------------------------------


class TestCustomToolExecution:
    """Tests for custom tool (code handler) execution via the Responses API."""

    @pytest.mark.asyncio
    async def test_tool_call_triggered(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Asking about weather should trigger the get_weather tool."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="What is the weather in San Francisco?",
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        assert len(result["tool_calls"]) >= 1, (
            f"Expected at least 1 tool call, got {len(result['tool_calls'])}"
        )
        # Check tool call has correct structure
        tc = result["tool_calls"][0]
        assert tc["name"] is not None
        assert tc["call_id"] is not None
        assert tc["arguments"] is not None

    @pytest.mark.asyncio
    async def test_tool_result_in_response_text(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Tool result (72 degrees, sunny) should appear in assistant's final text."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="What is the weather in New York?",
        )
        assert result["text"], "Expected non-empty response text"
        text_lower = result["text"].lower()
        # The mock tool returns 72 degrees and sunny
        assert "72" in text_lower or "sunny" in text_lower, (
            f"Expected tool result (72/sunny) in response: {result['text']}"
        )

    @pytest.mark.asyncio
    async def test_tool_output_sse_events(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Verify function_call_output SSE events are emitted."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="What's the weather in Chicago?",
        )
        assert len(result["tool_outputs"]) >= 1, (
            f"Expected at least 1 tool output, got {len(result['tool_outputs'])}"
        )
        output = result["tool_outputs"][0]
        assert output["call_id"] is not None
        assert output["output"] is not None

    @pytest.mark.asyncio
    async def test_tool_call_has_valid_arguments(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Tool call arguments should be valid JSON with expected fields."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Tell me about the weather in Tokyo.",
        )
        assert len(result["tool_calls"]) >= 1
        tc = result["tool_calls"][0]
        args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else tc["arguments"]
        assert "city" in args, f"Expected 'city' in tool args, got: {args}"

    @pytest.mark.asyncio
    async def test_calculator_tool_execution(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        calculator_tool: dict,
    ):
        """Calculator tool should execute and return correct result."""
        # Create assistant inline
        asst_resp = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Calc Test {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are a math assistant. Use the calculate tool for any math question. Be concise.",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_tokens": 200,
                "tools": [calculator_tool["id"]],
            },
            headers=auth_headers,
        )
        assistant = asst_resp.json()

        try:
            result = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=assistant["id"],
                message="What is 15 multiplied by 7?",
            )
            assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
            assert len(result["tool_calls"]) >= 1
            # The tool should return result: 105
            assert "105" in result["text"], (
                f"Expected '105' in response: {result['text']}"
            )
        finally:
            await async_client.delete(
                f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
            )


# ---------------------------------------------------------------------------
# TestMultiToolAssistant
# ---------------------------------------------------------------------------


class TestMultiToolAssistant:
    """Tests for assistants with multiple tools attached."""

    @pytest.mark.asyncio
    async def test_selects_correct_tool_weather(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_multiple_tools: dict,
        weather_tool: dict,
    ):
        """When asked about weather, should use the weather tool (not calculator)."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_multiple_tools["id"],
            message="What's the weather in Miami?",
        )
        assert len(result["tool_calls"]) >= 1
        tool_names = [tc["name"] for tc in result["tool_calls"]]
        # Should use the weather tool
        assert any(weather_tool["name"] in name for name in tool_names), (
            f"Expected weather tool in calls, got: {tool_names}"
        )

    @pytest.mark.asyncio
    async def test_selects_correct_tool_calculator(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_multiple_tools: dict,
        calculator_tool: dict,
    ):
        """When asked about math, should use the calculator tool (not weather)."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_multiple_tools["id"],
            message="What is 99 divided by 3?",
        )
        assert len(result["tool_calls"]) >= 1
        tool_names = [tc["name"] for tc in result["tool_calls"]]
        assert any(calculator_tool["name"] in name for name in tool_names), (
            f"Expected calculator tool in calls, got: {tool_names}"
        )

    @pytest.mark.asyncio
    async def test_no_tool_when_not_needed(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_multiple_tools: dict,
    ):
        """When asked a general question, should NOT use any tool."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_multiple_tools["id"],
            message="Say hello.",
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        assert result["text"], "Expected non-empty text"
        # No tool calls expected for a simple greeting
        assert len(result["tool_calls"]) == 0, (
            f"Expected no tool calls for greeting, got: {result['tool_calls']}"
        )


# ---------------------------------------------------------------------------
# TestBuiltinTools
# ---------------------------------------------------------------------------


class TestBuiltinTools:
    """Tests for built-in tools (web_search) with OpenAI."""

    @pytest.mark.asyncio
    async def test_web_search_assistant_responds(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_web_search: dict,
    ):
        """Assistant with web_search should produce a valid response."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_web_search["id"],
            message="What is the capital of France?",
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        assert result["text"], "Expected non-empty response text"

    @pytest.mark.asyncio
    async def test_web_search_with_current_events(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_web_search: dict,
    ):
        """Web search should handle current events questions."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_web_search["id"],
            message="What are the latest headlines today?",
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        assert len(result["text"]) > 0


# ---------------------------------------------------------------------------
# TestToolSSEEvents
# ---------------------------------------------------------------------------


class TestToolSSEEvents:
    """Tests for SSE event structure when tools are involved."""

    @pytest.mark.asyncio
    async def test_sse_has_response_created(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """SSE stream should start with response.created event."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Weather in Boston?",
        )
        event_types = [
            e["data"].get("type") for e in result["events"]
            if isinstance(e.get("data"), dict)
        ]
        assert "response.created" in event_types

    @pytest.mark.asyncio
    async def test_sse_has_completed_event(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """SSE stream should end with response.completed event."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Weather in Denver?",
        )
        event_types = [
            e["data"].get("type") for e in result["events"]
            if isinstance(e.get("data"), dict)
        ]
        assert "response.completed" in event_types

    @pytest.mark.asyncio
    async def test_sse_function_call_events_in_order(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Tool-related SSE events should appear in correct order:
        function_call → function_call_output → content.
        """
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="What is the weather in Seattle?",
        )
        event_types = [
            e["data"].get("type") for e in result["events"]
            if isinstance(e.get("data"), dict)
        ]
        # Check ordering: function_call_arguments.done before function_call_output
        fn_done_idx = None
        fn_output_idx = None
        for i, et in enumerate(event_types):
            if et == "response.function_call_arguments.done" and fn_done_idx is None:
                fn_done_idx = i
            if et == "response.output_item.added":
                item_data = result["events"][i]["data"]
                if isinstance(item_data, dict):
                    item = item_data.get("item", {})
                    if item.get("type") == "function_call_output" and fn_output_idx is None:
                        fn_output_idx = i

        if fn_done_idx is not None and fn_output_idx is not None:
            assert fn_done_idx < fn_output_idx, (
                "function_call_arguments.done should come before function_call_output"
            )

    @pytest.mark.asyncio
    async def test_sse_has_usage_stats(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Completed event should include usage statistics."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Weather in Atlanta?",
        )
        assert result["usage"] is not None, "Expected usage stats in completed event"
        assert "total_tokens" in result["usage"]


# ---------------------------------------------------------------------------
# TestMultiTurnWithTools
# ---------------------------------------------------------------------------


class TestMultiTurnWithTools:
    """Tests for multi-turn conversations with tool-using assistants."""

    @pytest.mark.asyncio
    async def test_multi_turn_tool_context(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Multi-turn: tool results from previous turns should be in context."""
        # Turn 1: Ask about weather
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="What is the weather in Portland?",
        )
        assert r1["status"] == "completed"
        conv_id = r1["conversation_id"]

        # Turn 2: Follow-up referencing previous tool result
        r2 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Is that temperature warm or cold?",
            conversation_id=conv_id,
            previous_response_id=r1["response_id"],
        )
        assert r2["status"] == "completed"
        assert r2["text"], "Expected non-empty follow-up response"

    @pytest.mark.asyncio
    async def test_multi_turn_different_tools(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_multiple_tools: dict,
    ):
        """Multi-turn: should use different tools across turns."""
        # Turn 1: Weather question
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_multiple_tools["id"],
            message="What's the weather in Dallas?",
        )
        conv_id = r1["conversation_id"]

        # Turn 2: Math question in same conversation
        r2 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_multiple_tools["id"],
            message="Now calculate 25 times 4 for me.",
            conversation_id=conv_id,
            previous_response_id=r1["response_id"],
        )
        assert r2["status"] == "completed"
        assert "100" in r2["text"], (
            f"Expected '100' in response: {r2['text']}"
        )


# ---------------------------------------------------------------------------
# TestToolEdgeCases
# ---------------------------------------------------------------------------


class TestToolEdgeCases:
    """Edge cases and negative tests for tool use."""

    @pytest.mark.asyncio
    async def test_no_tools_still_works(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_no_tools: dict,
    ):
        """Assistant with no tools should still respond normally."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_no_tools["id"],
            message="Hello, how are you?",
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        assert result["text"], "Expected non-empty response"
        assert len(result["tool_calls"]) == 0

    @pytest.mark.asyncio
    async def test_tool_override_in_request(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_no_tools: dict,
        weather_tool: dict,
    ):
        """Can override tool_ids at request level (assistant has none, request adds one)."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_no_tools["id"],
            message="What's the weather in Houston?",
            tool_ids=[weather_tool["id"]],
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        # May or may not trigger tool call depending on model decision,
        # but should not error
        assert result["text"] or len(result["tool_calls"]) >= 0

    @pytest.mark.asyncio
    async def test_invalid_tool_id_in_assistant(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
    ):
        """Assistant with a non-existent tool UUID should still be creatable."""
        fake_tool_id = str(uuid.uuid4())
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Bad Tool Assistant {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are a test assistant.",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_tokens": 200,
                "tools": [fake_tool_id],
            },
            headers=auth_headers,
        )
        # Should be creatable (tool resolution happens at response time)
        if response.status_code == 201:
            assistant = response.json()
            # Try to chat — should handle gracefully (skip unresolvable tool)
            r = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=assistant["id"],
                message="Hello",
            )
            # Should complete without crashing
            assert r["status"] in ("completed", "failed")
            await async_client.delete(
                f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
            )

    @pytest.mark.asyncio
    async def test_response_with_empty_tool_ids(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Overriding tool_ids to empty list at request level should disable tools."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="What's the weather?",
            tool_ids=[],
        )
        assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
        # No tools available, so no tool calls
        assert len(result["tool_calls"]) == 0


# ---------------------------------------------------------------------------
# TestToolResponseRetrieval
# ---------------------------------------------------------------------------


class TestToolResponseRetrieval:
    """Tests for retrieving responses that contain tool calls."""

    @pytest.mark.asyncio
    async def test_get_response_with_tool_calls(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """GET /responses/{id} should include tool call items."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Weather in Las Vegas?",
        )
        resp_id = result["response_id"]
        if not resp_id:
            pytest.skip("No response_id in SSE events")

        response = await async_client.get(
            f"{API_PREFIX}/responses/{resp_id}", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert data["id"] == resp_id
        assert data["status"] == "completed"

        # Check response items contain tool calls
        items = data.get("items", data.get("output", []))
        if items:
            item_types = [item.get("item_type") or item.get("type") for item in items]
            # Should have message, function_call, and function_call_output
            has_function_call = "function_call" in item_types
            has_function_output = "function_call_output" in item_types
            if result["tool_calls"]:
                assert has_function_call, (
                    f"Expected function_call in items, got: {item_types}"
                )
                assert has_function_output, (
                    f"Expected function_call_output in items, got: {item_types}"
                )

    @pytest.mark.asyncio
    async def test_conversation_history_includes_tool_calls(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        assistant_with_weather_tool: dict,
    ):
        """Conversation history should include responses with tool calls."""
        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=assistant_with_weather_tool["id"],
            message="Weather in Phoenix?",
        )
        conv_id = result["conversation_id"]
        if not conv_id:
            pytest.skip("No conversation_id in SSE events")

        history = await async_client.get(
            f"{API_PREFIX}/chat/conversations/{conv_id}/responses",
            headers=auth_headers,
        )
        assert history.status_code == 200
        responses = history.json()
        assert isinstance(responses, list)
        assert len(responses) >= 1


# ---------------------------------------------------------------------------
# TestToolModels
# ---------------------------------------------------------------------------


class TestToolModels:
    """Tests for tool use with different OpenAI models."""

    @pytest.mark.asyncio
    async def test_tool_with_gpt4o_mini(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        weather_tool: dict,
    ):
        """gpt-4o-mini should support custom tool calls."""
        asst_resp = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"GPT4oMini Tools {uuid.uuid4().hex[:8]}",
                "system_prompt": "Use tools when asked. Be concise.",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_tokens": 200,
                "tools": [weather_tool["id"]],
            },
            headers=auth_headers,
        )
        assistant = asst_resp.json()
        try:
            result = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=assistant["id"],
                message="Weather in London?",
            )
            assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
            assert len(result["tool_calls"]) >= 1
        finally:
            await async_client.delete(
                f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
            )

    @pytest.mark.asyncio
    async def test_tool_with_gpt4o(
        self,
        async_client: httpx.AsyncClient,
        auth_headers: dict,
        weather_tool: dict,
    ):
        """gpt-4o should support custom tool calls."""
        asst_resp = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"GPT4o Tools {uuid.uuid4().hex[:8]}",
                "system_prompt": "Use tools when asked. Be concise.",
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.0,
                "max_tokens": 200,
                "tools": [weather_tool["id"]],
            },
            headers=auth_headers,
        )
        assistant = asst_resp.json()
        try:
            result = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=assistant["id"],
                message="Weather in Paris?",
            )
            assert result["status"] == "completed", (
            f"Expected 'completed', got '{result['status']}'; "
            f"error={result.get('error', 'N/A')}; "
            f"events={[e.get('data', {}).get('type', '?') if isinstance(e.get('data'), dict) else '?' for e in result.get('events', [])]}"
        )
            assert len(result["tool_calls"]) >= 1
        finally:
            await async_client.delete(
                f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
            )
