"""Pytest configuration and fixtures for E2E tests.

Provides fixtures and helpers for running E2E tests against
the running backend API.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import AsyncGenerator, Generator

import httpx
import pytest
import pytest_asyncio

# Test configuration
BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000")
API_PREFIX = "/api/v1"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Markers
requires_openai = pytest.mark.skipif(
    not OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set",
)

# ── Cached credentials (register once, reuse across all tests) ──────────────

_cached_credentials: dict | None = None
_token_created_at: float = 0.0
_TOKEN_REFRESH_SECONDS = 25 * 60  # Re-login 5 min before the 30-min expiry


async def _get_or_create_user(client: httpx.AsyncClient) -> dict:
    """Register and login a user; cache the result for the whole run.

    Automatically re-logins when the access token is near expiry so that
    long-running test suites (document processing on CPU) don't fail with 401.
    """
    global _cached_credentials, _token_created_at

    if _cached_credentials is not None:
        if time.monotonic() - _token_created_at < _TOKEN_REFRESH_SECONDS:
            return _cached_credentials
        # Token is stale — re-login with cached email/password
        _cached_credentials = await _login_user(
            client,
            _cached_credentials["email"],
            _cached_credentials["password"],
            _cached_credentials,
        )
        return _cached_credentials

    unique_id = str(uuid.uuid4())[:8]
    user_data = {
        "email": f"testuser_{unique_id}@example.com",
        "password": "TestPassword123!",
        "name": f"Test User {unique_id}",
    }

    # Register user
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json=user_data,
    )

    user = response.json() if response.status_code == 201 else None

    _cached_credentials = await _login_user(
        client, user_data["email"], user_data["password"],
        {"email": user_data["email"], "password": user_data["password"],
         "name": user_data["name"], "user": user},
    )
    return _cached_credentials


async def _login_user(
    client: httpx.AsyncClient, email: str, password: str, base: dict,
) -> dict:
    """Login and return updated credentials dict."""
    global _token_created_at

    login_response = await client.post(
        f"{API_PREFIX}/auth/login",
        json={"email": email, "password": password},
    )
    tokens = login_response.json()
    _token_created_at = time.monotonic()

    return {
        **base,
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token"),
    }


# ── Core fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def async_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create a fresh async HTTP client per test (avoids event-loop binding)."""
    async with httpx.AsyncClient(
        base_url=BASE_URL,
        timeout=120.0,
        follow_redirects=True,
    ) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def test_user(async_client: httpx.AsyncClient) -> dict:
    """Return cached test user credentials (registers once per run)."""
    return await _get_or_create_user(async_client)


@pytest_asyncio.fixture(scope="function")
async def auth_headers(test_user: dict) -> dict:
    """Return authorization headers for authenticated requests."""
    return {
        "Authorization": f"Bearer {test_user['access_token']}",
    }


@pytest_asyncio.fixture(scope="function")
async def test_assistant(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
) -> AsyncGenerator[dict, None]:
    """Create a test assistant and clean it up after the test."""
    assistant_data = {
        "name": f"Test Assistant {uuid.uuid4().hex[:8]}",
        "description": "A test assistant for E2E testing",
        "system_prompt": "You are a helpful test assistant.",
        "provider": "openai",
        "model": "gpt-4o",
        "temperature": 0.7,
        "max_tokens": 1000,
    }

    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json=assistant_data,
        headers=auth_headers,
    )

    assistant = response.json()

    yield assistant

    if "id" in assistant:
        await async_client.delete(
            f"{API_PREFIX}/assistants/{assistant['id']}",
            headers=auth_headers,
        )


@pytest_asyncio.fixture(scope="function")
async def test_knowledge_base(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
) -> AsyncGenerator[dict, None]:
    """Create a test knowledge base and clean it up after the test."""
    kb_data = {
        "name": f"Test KB {uuid.uuid4().hex[:8]}",
        "description": "A test knowledge base for E2E testing",
    }

    response = await async_client.post(
        f"{API_PREFIX}/knowledge-bases",
        json=kb_data,
        headers=auth_headers,
    )

    kb = response.json()

    yield kb

    if "id" in kb:
        try:
            await async_client.delete(
                f"{API_PREFIX}/knowledge-bases/{kb['id']}",
                headers=auth_headers,
            )
        except (httpx.ReadTimeout, httpx.ConnectTimeout):
            pass  # KB cleanup timed out — Qdrant cascade can be slow


@pytest_asyncio.fixture(scope="function")
async def test_tool(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
) -> AsyncGenerator[dict, None]:
    """Create a test custom tool and clean it up after the test."""
    tool_data = {
        "name": f"test_tool_{uuid.uuid4().hex[:8]}",
        "description": "A test tool for E2E testing",
        "schema_definition": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "Test input",
                }
            },
            "required": ["input"],
        },
        "implementation": {
            "handler": "code",
            "code": "result = {'echo': params.get('input', '')}",
        },
    }

    response = await async_client.post(
        f"{API_PREFIX}/tools/custom",
        json=tool_data,
        headers=auth_headers,
    )

    tool = response.json()

    yield tool

    if "id" in tool:
        await async_client.delete(
            f"{API_PREFIX}/tools/{tool['id']}",
            headers=auth_headers,
        )


@pytest_asyncio.fixture(scope="function")
async def test_voice_preset(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
) -> AsyncGenerator[dict, None]:
    """Create a test TTS voice preset and clean it up after the test."""
    preset_data = {
        "name": f"Test Preset {uuid.uuid4().hex[:8]}",
        "type": "tts",
        "config": {"source": "browser"},
    }

    response = await async_client.post(
        f"{API_PREFIX}/voice-presets",
        json=preset_data,
        headers=auth_headers,
    )

    preset = response.json()

    yield preset

    if "id" in preset:
        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{preset['id']}",
            headers=auth_headers,
        )


@pytest_asyncio.fixture(scope="function")
async def test_project(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
) -> AsyncGenerator[dict, None]:
    """Create a test project and clean it up after the test."""
    project_data = {
        "name": f"Test Project {uuid.uuid4().hex[:8]}",
        "description": "A test project for E2E testing",
    }

    response = await async_client.post(
        f"{API_PREFIX}/projects",
        json=project_data,
        headers=auth_headers,
    )

    project = response.json()

    yield project

    if "id" in project:
        await async_client.delete(
            f"{API_PREFIX}/projects/{project['id']}",
            headers=auth_headers,
        )


@pytest_asyncio.fixture(scope="function")
async def test_avatar(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
) -> AsyncGenerator[dict, None]:
    """Create a test avatar and clean it up after the test."""
    avatar_data = {
        "name": f"Test Avatar {uuid.uuid4().hex[:8]}",
        "description": "A test avatar for E2E testing",
    }

    response = await async_client.post(
        f"{API_PREFIX}/avatars",
        json=avatar_data,
        headers=auth_headers,
    )

    avatar = response.json()

    yield avatar

    if "id" in avatar:
        await async_client.delete(
            f"{API_PREFIX}/avatars/{avatar['id']}",
            headers=auth_headers,
        )


class TestDataFactory:
    """Factory for generating test data."""

    @staticmethod
    def user_data(
        email: str | None = None,
        password: str = "TestPassword123!",
        name: str | None = None,
    ) -> dict:
        unique_id = uuid.uuid4().hex[:8]
        return {
            "email": email or f"user_{unique_id}@example.com",
            "password": password,
            "name": name or f"Test User {unique_id}",
        }

    @staticmethod
    def assistant_data(
        name: str | None = None,
        provider: str = "openai",
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        tools: list[str] | None = None,
        knowledge_base_ids: list[str] | None = None,
    ) -> dict:
        unique_id = uuid.uuid4().hex[:8]
        return {
            "name": name or f"Assistant {unique_id}",
            "description": f"Test assistant {unique_id}",
            "system_prompt": "You are a helpful assistant.",
            "provider": provider,
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "tools": tools or [],
            "knowledge_base_ids": knowledge_base_ids or [],
        }

    @staticmethod
    def knowledge_base_data(
        name: str | None = None,
        description: str | None = None,
    ) -> dict:
        unique_id = uuid.uuid4().hex[:8]
        return {
            "name": name or f"KB {unique_id}",
            "description": description or f"Test knowledge base {unique_id}",
        }

    @staticmethod
    def tool_data(
        name: str | None = None,
        schema: dict | None = None,
    ) -> dict:
        unique_id = uuid.uuid4().hex[:8]
        return {
            "name": name or f"tool_{unique_id}",
            "description": f"Test tool {unique_id}",
            "schema_definition": schema or {
                "type": "object",
                "properties": {
                    "input": {"type": "string"},
                },
                "required": ["input"],
            },
            "implementation": {
                "handler": "code",
                "code": "result = {'echo': params.get('input', '')}",
            },
        }

    @staticmethod
    def response_data(
        assistant_id: str,
        message: str = "Hello, how are you?",
        stream: bool = False,
        conversation_id: str | None = None,
        previous_response_id: str | None = None,
        **overrides,
    ) -> dict:
        data = {
            "assistant_id": assistant_id,
            "input": [
                {
                    "type": "message",
                    "role": "user",
                    "content": message,
                }
            ],
            "stream": stream,
        }
        if conversation_id:
            data["conversation_id"] = conversation_id
        if previous_response_id:
            data["previous_response_id"] = previous_response_id
        data.update(overrides)
        return data


@pytest.fixture
def test_data() -> TestDataFactory:
    """Provide access to test data factory."""
    return TestDataFactory()


# Helper functions for common test assertions

def assert_success_response(response: httpx.Response, expected_status: int = 200):
    """Assert that the response is successful."""
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}: "
        f"{response.text}"
    )


def assert_error_response(
    response: httpx.Response,
    expected_status: int,
    expected_detail: str | None = None,
):
    """Assert that the response is an error with the expected format."""
    assert response.status_code == expected_status, (
        f"Expected status {expected_status}, got {response.status_code}: "
        f"{response.text}"
    )

    if expected_detail:
        data = response.json()
        detail = data.get("detail") or data.get("message") or data.get("error")
        assert expected_detail.lower() in str(detail).lower(), (
            f"Expected detail containing '{expected_detail}', got: {detail}"
        )


def assert_pagination_response(data: dict):
    """Assert that the response has proper pagination fields."""
    assert "items" in data, "Missing 'items' field in pagination response"
    assert "total" in data, "Missing 'total' field in pagination response"
    assert isinstance(data["items"], list), "'items' should be a list"
    assert isinstance(data["total"], int), "'total' should be an integer"


def assert_uuid_format(value: str):
    """Assert that the value is a valid UUID."""
    try:
        uuid.UUID(value)
    except ValueError:
        pytest.fail(f"Invalid UUID format: {value}")


def assert_datetime_format(value: str):
    """Assert that the value is a valid ISO datetime string."""
    from datetime import datetime
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        pytest.fail(f"Invalid datetime format: {value}")


def parse_sse_events(response: httpx.Response) -> list[dict]:
    """Parse SSE events from a streaming response.

    Returns a list of parsed event dicts: {event: str, data: dict|str}.
    """
    events = []
    current_event = None
    current_data_parts = []

    for line in response.text.split("\n"):
        line = line.strip()
        if not line:
            # Empty line = end of event
            if current_data_parts:
                raw_data = "\n".join(current_data_parts)
                try:
                    parsed = json.loads(raw_data)
                except (json.JSONDecodeError, ValueError):
                    parsed = raw_data
                events.append({
                    "event": current_event or "message",
                    "data": parsed,
                })
                current_event = None
                current_data_parts = []
            continue

        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data_parts.append(line[len("data:"):].strip())

    # Handle last event if no trailing newline
    if current_data_parts:
        raw_data = "\n".join(current_data_parts)
        try:
            parsed = json.loads(raw_data)
        except (json.JSONDecodeError, ValueError):
            parsed = raw_data
        events.append({
            "event": current_event or "message",
            "data": parsed,
        })

    return events


def assert_list_response(data, expected_fields: list[str] | None = None):
    """Check list responses — either {items, total} or direct list."""
    if isinstance(data, dict) and "items" in data:
        items = data["items"]
    elif isinstance(data, list):
        items = data
    else:
        pytest.fail(f"Expected list or dict with 'items', got: {type(data)}")

    assert isinstance(items, list)

    if expected_fields and items:
        for field in expected_fields:
            assert field in items[0], f"Missing field '{field}' in list item"

    return items
