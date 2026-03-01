"""E2E tests for core platform CRUD: auth, assistants, knowledge bases, tools, files, conversations.

No OPENAI_API_KEY required — these tests only exercise CRUD endpoints.
"""

import uuid

import httpx
import pytest

from tests.conftest import (
    API_PREFIX,
    TestDataFactory,
    assert_error_response,
    assert_success_response,
    assert_uuid_format,
    assert_datetime_format,
    assert_pagination_response,
)

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# TestAuth
# ---------------------------------------------------------------------------

class TestAuth:
    """Tests for /auth endpoints."""

    @pytest.mark.asyncio
    async def test_register_user(self, async_client: httpx.AsyncClient, test_data: TestDataFactory):
        user = test_data.user_data()
        response = await async_client.post(f"{API_PREFIX}/auth/register", json=user)
        assert_success_response(response, 201)
        data = response.json()
        assert data["email"] == user["email"]
        assert "id" in data
        assert "password" not in data
        assert "hashed_password" not in data

    @pytest.mark.asyncio
    async def test_register_duplicate_email(
        self, async_client: httpx.AsyncClient, test_user: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/auth/register",
            json={
                "email": test_user["email"],
                "password": "AnotherP@ss123!",
                "name": "Duplicate",
            },
        )
        assert response.status_code in (400, 409)

    @pytest.mark.asyncio
    async def test_register_invalid_email(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/auth/register",
            json={"email": "not-an-email", "password": "TestPassword123!", "name": "Bad"},
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_register_short_password(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/auth/register",
            json={"email": f"short_{uuid.uuid4().hex[:6]}@test.com", "password": "short", "name": "Short"},
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/auth/register", json={"email": "a@b.com"},
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_login_success(
        self, async_client: httpx.AsyncClient, test_user: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": test_user["email"], "password": test_user["password"]},
        )
        assert_success_response(response)
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, async_client: httpx.AsyncClient, test_user: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": test_user["email"], "password": "WrongP@ss123!"},
        )
        assert_error_response(response, 401)

    @pytest.mark.asyncio
    async def test_login_nonexistent_email(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": f"ghost_{uuid.uuid4().hex}@test.com", "password": "P@ss123!"},
        )
        assert_error_response(response, 401)

    @pytest.mark.asyncio
    async def test_refresh_token(
        self, async_client: httpx.AsyncClient, test_user: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/auth/refresh",
            params={"refresh_token": test_user["refresh_token"]},
        )
        assert_success_response(response)
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/auth/refresh", params={"refresh_token": "bad_token"},
        )
        assert_error_response(response, 401)

    @pytest.mark.asyncio
    async def test_get_me(
        self, async_client: httpx.AsyncClient, test_user: dict, auth_headers: dict,
    ):
        response = await async_client.get(f"{API_PREFIX}/auth/me", headers=auth_headers)
        assert_success_response(response)
        data = response.json()
        assert data["email"] == test_user["email"]
        assert "password" not in data

    @pytest.mark.asyncio
    async def test_get_me_no_token(self, async_client: httpx.AsyncClient):
        response = await async_client.get(f"{API_PREFIX}/auth/me")
        assert_error_response(response, 401)

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, async_client: httpx.AsyncClient):
        response = await async_client.get(
            f"{API_PREFIX}/auth/me", headers={"Authorization": "Bearer invalid"},
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestAssistants
# ---------------------------------------------------------------------------

class TestAssistants:
    """Tests for /assistants CRUD."""

    @pytest.mark.asyncio
    async def test_create_assistant_minimal(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Minimal {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are helpful.",
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert "id" in data
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"

        await async_client.delete(
            f"{API_PREFIX}/assistants/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_assistant_full(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Full {uuid.uuid4().hex[:8]}",
                "description": "Full test assistant",
                "system_prompt": "You are a thorough test assistant.",
                "provider": "openai",
                "model": "gpt-4o",
                "temperature": 0.5,
                "max_tokens": 2000,
                "top_p": 0.9,
                "tools": [],
                "knowledge_base_ids": [],
                "settings": {"response_format": "text"},
                "avatar_enabled": False,
                "voice_enabled": False,
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert data["temperature"] == 0.5
        assert data["max_tokens"] == 2000
        assert data["avatar_enabled"] is False

        await async_client.delete(
            f"{API_PREFIX}/assistants/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_assistant_openai_gpt4o(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"GPT4o {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are a test assistant.",
                "provider": "openai",
                "model": "gpt-4o",
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert data["provider"] == "openai"
        assert data["model"] == "gpt-4o"

        await async_client.delete(
            f"{API_PREFIX}/assistants/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_list_assistants(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/assistants", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_list_assistants_pagination(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/assistants",
            params={"skip": 0, "limit": 5},
            headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert len(data["items"]) <= 5

    @pytest.mark.asyncio
    async def test_list_assistants_search(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        search_term = test_assistant["name"][:10]
        response = await async_client.get(
            f"{API_PREFIX}/assistants",
            params={"search": search_term},
            headers=auth_headers,
        )
        assert_success_response(response)

    @pytest.mark.asyncio
    async def test_get_assistant(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/assistants/{test_assistant['id']}", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert data["id"] == test_assistant["id"]
        assert data["name"] == test_assistant["name"]

    @pytest.mark.asyncio
    async def test_update_assistant_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/assistants/{test_assistant['id']}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_assistant_temperature(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/assistants/{test_assistant['id']}",
            json={"temperature": 0.1},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["temperature"] == 0.1

    @pytest.mark.asyncio
    async def test_update_assistant_model(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/assistants/{test_assistant['id']}",
            json={"model": "gpt-4o-mini"},
            headers=auth_headers,
        )
        # May reject invalid model for the provider — accept 200 or 400
        assert response.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_delete_assistant(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Delete Me {uuid.uuid4().hex[:8]}",
                "system_prompt": "Temp.",
            },
            headers=auth_headers,
        )
        aid = create.json()["id"]

        response = await async_client.delete(
            f"{API_PREFIX}/assistants/{aid}", headers=auth_headers,
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_get_deleted_assistant(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Ghost {uuid.uuid4().hex[:8]}",
                "system_prompt": "Temp.",
            },
            headers=auth_headers,
        )
        aid = create.json()["id"]
        await async_client.delete(
            f"{API_PREFIX}/assistants/{aid}", headers=auth_headers,
        )

        response = await async_client.get(
            f"{API_PREFIX}/assistants/{aid}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_create_missing_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={"system_prompt": "No name."},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_create_missing_system_prompt(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={"name": "No prompt"},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_invalid_temperature(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": "Bad Temp",
                "system_prompt": "test",
                "temperature": 5.0,
            },
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_no_auth_assistants(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={"name": "NoAuth", "system_prompt": "test"},
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestKnowledgeBases
# ---------------------------------------------------------------------------

class TestKnowledgeBases:
    """Tests for /knowledge-bases CRUD."""

    @pytest.mark.asyncio
    async def test_create_kb_minimal(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"Min KB {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert "id" in data
        assert data["kb_type"] == "platform_managed"

        await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_kb_with_description(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={
                "name": f"Desc KB {uuid.uuid4().hex[:8]}",
                "description": "Test knowledge base with description",
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert data["description"] == "Test knowledge base with description"

        await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_kb_platform_managed(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={
                "name": f"PM KB {uuid.uuid4().hex[:8]}",
                "kb_type": "platform_managed",
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        assert response.json()["kb_type"] == "platform_managed"

        await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{response.json()['id']}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_list_kbs(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_kbs_pagination(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases",
            params={"skip": 0, "limit": 5},
            headers=auth_headers,
        )
        assert_success_response(response)

    @pytest.mark.asyncio
    async def test_list_kbs_search(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        search_term = test_knowledge_base["name"][:8]
        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases",
            params={"search": search_term},
            headers=auth_headers,
        )
        assert_success_response(response)

    @pytest.mark.asyncio
    async def test_get_kb(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases/{test_knowledge_base['id']}",
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["id"] == test_knowledge_base["id"]

    @pytest.mark.asyncio
    async def test_update_kb_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/knowledge-bases/{test_knowledge_base['id']}",
            json={"name": "Updated KB Name"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["name"] == "Updated KB Name"

    @pytest.mark.asyncio
    async def test_update_kb_description(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/knowledge-bases/{test_knowledge_base['id']}",
            json={"description": "Updated description"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete_kb(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"Del KB {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        kid = create.json()["id"]

        response = await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{kid}", headers=auth_headers,
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_get_deleted_kb(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"Ghost KB {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        kid = create.json()["id"]
        await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{kid}", headers=auth_headers,
        )

        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases/{kid}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_create_kb_missing_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"description": "No name"},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_create_kb_empty_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": ""},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_no_auth_kb(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/knowledge-bases", json={"name": "NoAuth"},
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestTools
# ---------------------------------------------------------------------------

class TestTools:
    """Tests for /tools CRUD (custom tools via POST /tools/custom)."""

    @pytest.mark.asyncio
    async def test_create_custom_tool(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "name": f"tool_{uuid.uuid4().hex[:8]}",
                "description": "A test custom tool",
                "schema_definition": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
                "implementation": {
                    "handler": "code",
                    "code": "result = {'answer': params['query']}",
                },
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert "id" in data
        assert data["is_active"] is True

        await async_client.delete(
            f"{API_PREFIX}/tools/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_tool_http_handler(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "name": f"http_tool_{uuid.uuid4().hex[:8]}",
                "schema_definition": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                },
                "implementation": {
                    "handler": "http",
                    "method": "GET",
                    "url": "https://httpbin.org/get",
                },
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert data["implementation"]["handler"] == "http"

        await async_client.delete(
            f"{API_PREFIX}/tools/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_tool_code_handler(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "name": f"code_tool_{uuid.uuid4().hex[:8]}",
                "schema_definition": {
                    "type": "object",
                    "properties": {"x": {"type": "integer"}},
                },
                "implementation": {
                    "handler": "code",
                    "code": "result = params.get('x', 0) * 2",
                },
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)

        await async_client.delete(
            f"{API_PREFIX}/tools/{response.json()['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_list_tools(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_tool: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools", headers=auth_headers,
        )
        assert_success_response(response)
        tools = response.json()
        assert isinstance(tools, list)

    @pytest.mark.asyncio
    async def test_list_tools_pagination(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_tool: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools",
            params={"skip": 0, "limit": 5},
            headers=auth_headers,
        )
        assert_success_response(response)

    @pytest.mark.asyncio
    async def test_get_tool(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_tool: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools/{test_tool['id']}", headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["id"] == test_tool["id"]

    @pytest.mark.asyncio
    async def test_update_tool(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_tool: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/tools/{test_tool['id']}",
            json={"description": "Updated description"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_toggle_tool_active(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_tool: dict,
    ):
        response = await async_client.put(
            f"{API_PREFIX}/tools/{test_tool['id']}",
            json={"is_active": False},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["is_active"] is False

    @pytest.mark.asyncio
    async def test_delete_tool(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "name": f"del_tool_{uuid.uuid4().hex[:8]}",
                "schema_definition": {"type": "object", "properties": {}},
                "implementation": {"handler": "code", "code": "result = None"},
            },
            headers=auth_headers,
        )
        tid = create.json()["id"]

        response = await async_client.delete(
            f"{API_PREFIX}/tools/{tid}", headers=auth_headers,
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_get_catalog_builtin(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools/catalog/builtin", headers=auth_headers,
        )
        assert_success_response(response)
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_catalog_integrations(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools/catalog/integrations", headers=auth_headers,
        )
        assert_success_response(response)
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_catalog_all(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools/catalog/all", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "builtin" in data
        assert "integrations" in data

    @pytest.mark.asyncio
    async def test_get_available_tools(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/tools/available", headers=auth_headers,
        )
        assert_success_response(response)

    @pytest.mark.asyncio
    async def test_create_missing_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "schema_definition": {"type": "object"},
                "implementation": {"handler": "code", "code": "result = None"},
            },
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_create_missing_schema(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "name": f"no_schema_{uuid.uuid4().hex[:8]}",
                "implementation": {"handler": "code", "code": "result = None"},
            },
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_no_auth_tools(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/tools/custom",
            json={
                "name": "noauth",
                "schema_definition": {"type": "object"},
                "implementation": {"handler": "code", "code": "result = None"},
            },
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestFiles
# ---------------------------------------------------------------------------

class TestFiles:
    """Tests for /files endpoints."""

    @pytest.mark.asyncio
    async def test_upload_text_file(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/files/upload-text",
            data={
                "knowledge_base_id": test_knowledge_base["id"],
                "title": "Test Document",
                "content": "This is test content for the knowledge base.",
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert "id" in data
        assert data["filename"] == "Test Document.txt"

    @pytest.mark.asyncio
    async def test_upload_text_empty_content(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_knowledge_base: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/files/upload-text",
            data={
                "knowledge_base_id": test_knowledge_base["id"],
                "title": "Empty",
                "content": "   ",
            },
            headers=auth_headers,
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_list_files(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/files", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_files_search(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/files",
            params={"search": "nonexistent_file_xyz"},
            headers=auth_headers,
        )
        assert_success_response(response)

    @pytest.mark.asyncio
    async def test_no_auth_files(self, async_client: httpx.AsyncClient):
        response = await async_client.get(f"{API_PREFIX}/files")
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestConversations
# ---------------------------------------------------------------------------

class TestConversations:
    """Tests for /chat/conversations endpoints."""

    @pytest.mark.asyncio
    async def test_list_conversations_empty(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/chat/conversations", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_list_conversations_filter_assistant(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_assistant: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/chat/conversations",
            params={"assistant_id": test_assistant["id"]},
            headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_delete_nonexistent_conversation(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        bad_id = str(uuid.uuid4())
        response = await async_client.delete(
            f"{API_PREFIX}/chat/conversations/{bad_id}", headers=auth_headers,
        )
        assert_error_response(response, 404)
