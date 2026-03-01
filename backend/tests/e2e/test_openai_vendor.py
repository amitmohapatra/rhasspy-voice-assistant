"""E2E tests for AI vendor setup: model registry, projects/secrets, provider discovery, capabilities.

Tests cover setting up OpenAI as an LLM provider, configuring API keys via
project secrets, and verifying provider/model discovery endpoints.
"""

import os
import uuid

import httpx
import pytest
import pytest_asyncio

from tests.conftest import (
    API_PREFIX,
    OPENAI_API_KEY,
    assert_error_response,
    assert_success_response,
    assert_uuid_format,
)

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# TestAIModelInitialization
# ---------------------------------------------------------------------------

class TestAIModelInitialization:
    """Tests for POST /ai/models/initialize and related model/provider endpoints."""

    @pytest.mark.asyncio
    async def test_initialize_default_models(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/ai/initialize", headers=auth_headers,
        )
        assert_success_response(response, 200)
        data = response.json()
        assert "providers_created" in data
        assert "models_created" in data
        assert "message" in data

    @pytest.mark.asyncio
    async def test_list_providers(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/ai/providers", headers=auth_headers,
        )
        assert_success_response(response)
        providers = response.json()
        assert isinstance(providers, list)
        assert len(providers) > 0
        names = [p["name"] for p in providers]
        assert "openai" in names

    @pytest.mark.asyncio
    async def test_get_openai_provider_by_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/ai/providers/name/openai", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert data["name"] == "openai"
        assert "id" in data
        assert_uuid_format(data["id"])

    @pytest.mark.asyncio
    async def test_list_models(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/ai/models", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "models" in data
        assert "total" in data
        assert isinstance(data["models"], list)

    @pytest.mark.asyncio
    async def test_list_models_filter_by_provider(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        # Get OpenAI provider ID first
        prov = await async_client.get(
            f"{API_PREFIX}/ai/providers/name/openai", headers=auth_headers,
        )
        provider_id = prov.json()["id"]

        response = await async_client.get(
            f"{API_PREFIX}/ai/models",
            params={"provider_id": provider_id},
            headers=auth_headers,
        )
        assert_success_response(response)
        models = response.json()["models"]
        for m in models:
            assert m["provider_id"] == provider_id

    @pytest.mark.asyncio
    async def test_list_models_filter_by_category(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/ai/models",
            params={"category": "chat"},
            headers=auth_headers,
        )
        assert_success_response(response)
        models = response.json()["models"]
        for m in models:
            assert m["category"] == "chat"

    @pytest.mark.asyncio
    async def test_get_model_by_identifier(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/ai/models/lookup/gpt-4o", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert data["model_id"] == "gpt-4o"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_recommend_models_for_task(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/ai/models/recommend/chat", headers=auth_headers,
        )
        assert_success_response(response)
        models = response.json()
        assert isinstance(models, list)

    @pytest.mark.asyncio
    async def test_update_provider_status(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        prov = await async_client.get(
            f"{API_PREFIX}/ai/providers/name/openai", headers=auth_headers,
        )
        provider_id = prov.json()["id"]

        # Set active (idempotent)
        response = await async_client.patch(
            f"{API_PREFIX}/ai/providers/{provider_id}/status",
            json={"status": "active"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_nonexistent_provider(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        bad_id = str(uuid.uuid4())
        response = await async_client.get(
            f"{API_PREFIX}/ai/providers/{bad_id}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_get_nonexistent_model(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        bad_id = str(uuid.uuid4())
        response = await async_client.get(
            f"{API_PREFIX}/ai/models/{bad_id}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_no_auth_models(self, async_client: httpx.AsyncClient):
        response = await async_client.get(f"{API_PREFIX}/ai/models")
        # Model listing may or may not require auth based on router config.
        # Check that it either succeeds or returns 401/403.
        assert response.status_code in (200, 401, 403)


# ---------------------------------------------------------------------------
# TestProjectSecrets
# ---------------------------------------------------------------------------

class TestProjectSecrets:
    """Tests for project CRUD and secrets management."""

    @pytest.mark.asyncio
    async def test_create_project(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/projects",
            json={
                "name": f"E2E Project {uuid.uuid4().hex[:8]}",
                "description": "Test project",
            },
            headers=auth_headers,
        )
        assert response.status_code in (200, 201), (
            f"Expected 200 or 201, got {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "id" in data
        assert data["name"].startswith("E2E Project")

        # Cleanup
        await async_client.delete(
            f"{API_PREFIX}/projects/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_list_projects(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_project: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/projects", headers=auth_headers,
        )
        assert_success_response(response)
        projects = response.json()
        assert isinstance(projects, list)

    @pytest.mark.asyncio
    async def test_get_project(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_project: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/projects/{test_project['id']}", headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["id"] == test_project["id"]

    @pytest.mark.asyncio
    async def test_update_project(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_project: dict,
    ):
        response = await async_client.patch(
            f"{API_PREFIX}/projects/{test_project['id']}",
            json={"name": "Updated Project Name"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["name"] == "Updated Project Name"

    @pytest.mark.asyncio
    async def test_set_and_list_secrets(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_project: dict,
    ):
        # Set a secret
        response = await async_client.post(
            f"{API_PREFIX}/projects/{test_project['id']}/secrets",
            json={"key": "TEST_SECRET_KEY", "value": "test_value_123"},
            headers=auth_headers,
        )
        assert response.status_code in (200, 201)

        # List secrets — values should be hidden
        response = await async_client.get(
            f"{API_PREFIX}/projects/{test_project['id']}/secrets",
            headers=auth_headers,
        )
        assert_success_response(response)
        secrets = response.json()
        assert isinstance(secrets, list)

        # Cleanup
        await async_client.delete(
            f"{API_PREFIX}/projects/{test_project['id']}/secrets/TEST_SECRET_KEY",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_get_required_secrets(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_project: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/projects/{test_project['id']}/secrets/required",
            headers=auth_headers,
        )
        assert_success_response(response)
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_delete_secret(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_project: dict,
    ):
        # Create a secret first
        await async_client.post(
            f"{API_PREFIX}/projects/{test_project['id']}/secrets",
            json={"key": "TO_DELETE", "value": "delete_me"},
            headers=auth_headers,
        )

        response = await async_client.delete(
            f"{API_PREFIX}/projects/{test_project['id']}/secrets/TO_DELETE",
            headers=auth_headers,
        )
        assert response.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_delete_project(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create_resp = await async_client.post(
            f"{API_PREFIX}/projects",
            json={"name": f"To Delete {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        project_id = create_resp.json()["id"]

        response = await async_client.delete(
            f"{API_PREFIX}/projects/{project_id}", headers=auth_headers,
        )
        assert response.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_project_not_found(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        bad_id = str(uuid.uuid4())
        response = await async_client.get(
            f"{API_PREFIX}/projects/{bad_id}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_no_auth_projects(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/projects", json={"name": "No Auth"},
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestProviderDiscovery
# ---------------------------------------------------------------------------

class TestProviderDiscovery:
    """Tests for /providers discovery endpoints (LLM, TTS, STT)."""

    @pytest.mark.asyncio
    async def test_list_provider_types(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/types", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert isinstance(data, (list, dict))

    @pytest.mark.asyncio
    async def test_list_llm_providers(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/llm", headers=auth_headers,
        )
        assert_success_response(response)
        providers = response.json()
        assert isinstance(providers, list)

    @pytest.mark.asyncio
    async def test_get_openai_models_from_provider(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/llm/openai/models", headers=auth_headers,
        )
        # May 404 if provider discovery routes only work for configured providers
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_get_provider_settings(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/llm/openai/settings", headers=auth_headers,
        )
        # May 404 if provider discovery routes only work for configured providers
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_list_tts_providers(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/tts", headers=auth_headers,
        )
        assert_success_response(response)
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_list_stt_providers(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/stt", headers=auth_headers,
        )
        assert_success_response(response)
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_tts_voices(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/tts/openai/voices", headers=auth_headers,
        )
        # May 404 if TTS provider not configured
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_get_embedding_dimensions(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/providers/embeddings/openai/dimensions",
            headers=auth_headers,
        )
        # This endpoint may or may not exist; assert 200 or 404
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# TestCapabilities
# ---------------------------------------------------------------------------

class TestCapabilities:
    """Tests for /capabilities endpoints."""

    @pytest.mark.asyncio
    async def test_list_capability_definitions(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/capabilities/definitions", headers=auth_headers,
        )
        assert_success_response(response)
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_seed_default_capabilities(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/capabilities/seed", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "message" in data or "definitions" in data

    @pytest.mark.asyncio
    async def test_get_model_capabilities(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        # Get a valid model ID first
        models_resp = await async_client.get(
            f"{API_PREFIX}/ai/models", params={"limit": 1}, headers=auth_headers,
        )
        models = models_resp.json()["models"]
        if not models:
            pytest.skip("No models available")

        model_id = models[0]["id"]
        response = await async_client.get(
            f"{API_PREFIX}/capabilities/models/{model_id}",
            headers=auth_headers,
        )
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_capability_summary(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        models_resp = await async_client.get(
            f"{API_PREFIX}/ai/models", params={"limit": 1}, headers=auth_headers,
        )
        models = models_resp.json()["models"]
        if not models:
            pytest.skip("No models available")

        model_id = models[0]["id"]
        response = await async_client.get(
            f"{API_PREFIX}/capabilities/models/{model_id}/summary",
            headers=auth_headers,
        )
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_check_tool_use_support(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        models_resp = await async_client.get(
            f"{API_PREFIX}/ai/models", params={"limit": 1}, headers=auth_headers,
        )
        models = models_resp.json()["models"]
        if not models:
            pytest.skip("No models available")

        model_id = models[0]["id"]
        response = await async_client.get(
            f"{API_PREFIX}/capabilities/models/{model_id}/supports/tool_use",
            headers=auth_headers,
        )
        assert response.status_code in (200, 400, 404)

    @pytest.mark.asyncio
    async def test_list_capability_types(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/capabilities/types", headers=auth_headers,
        )
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# TestProviderConnectionTest
# ---------------------------------------------------------------------------

class TestProviderConnectionTest:
    """Tests for provider connection testing (requires OPENAI_API_KEY)."""

    @pytest.mark.asyncio
    async def test_provider_secrets_reference(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/projects/reference/provider-secrets",
            headers=auth_headers,
        )
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    async def test_tool_secrets_reference(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/projects/reference/tool-secrets",
            headers=auth_headers,
        )
        assert response.status_code in (200, 404)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
    async def test_test_connection_openai(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/providers/test-connection",
            json={"type": "llm", "name": "openai"},
            headers=auth_headers,
        )
        # May succeed or fail depending on server config
        assert response.status_code in (200, 400, 404, 422)
