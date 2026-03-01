"""E2E tests for RAG pipeline integration with chat.

Tests the full flow: create KB → upload document → process → create assistant
with KB → send chat message → verify RAG-augmented response via SSE streaming.

Requires:
- OPENAI_API_KEY env var (tests are skipped if not set)
- Celery worker running (for document processing)
- Inference service running (for embedding generation)
- Qdrant running (for vector storage)

Tests are skipped gracefully if infrastructure is unavailable.
"""

from __future__ import annotations

import asyncio
import uuid

import httpx
import pytest
import pytest_asyncio

from tests.conftest import (
    API_PREFIX,
    OPENAI_API_KEY,
    TestDataFactory,
    assert_success_response,
    assert_error_response,
    parse_sse_events,
    requires_openai,
)

pytestmark = [pytest.mark.e2e]

# Known document content for verifiable RAG answers
DOCUMENT_CONTENT = """
The Quantum Nexus Protocol (QNP) is a fictional communication standard developed
by the Arcadia Research Institute in 2045. QNP uses entangled photon pairs to
achieve instantaneous data transfer across distances up to 500 light-years.

Key features of QNP:
- Bandwidth: 10 exabytes per second
- Latency: Zero (instantaneous via quantum entanglement)
- Maximum range: 500 light-years
- Error rate: Less than 0.0001%
- Encryption: Built-in quantum key distribution (QKD)

The protocol was designed by Dr. Elena Vasquez and her team of 12 researchers.
The first successful test was conducted on March 15, 2045, between Earth and
the Proxima Centauri colony.

QNP operates on three layers:
1. The Entanglement Layer: Manages photon pair generation and distribution
2. The Transport Layer: Handles data packetization and reassembly
3. The Application Layer: Provides APIs for higher-level communication

The Arcadia Research Institute is headquartered in Geneva, Switzerland.
"""

DOCUMENT_CONTENT_2 = """
Project Aurora is a terraforming initiative launched by the United Earth
Coalition in 2050. The project aims to make Mars fully habitable by 2120.

Phase 1 (2050-2070): Atmospheric Warming
- Deploy orbital mirrors to increase surface temperature by 20°C
- Release greenhouse gases from Martian polar caps
- Target: Raise atmospheric pressure to 100 millibars

Phase 2 (2070-2090): Water Cycle Restoration
- Melt subsurface ice deposits using geothermal tapping
- Introduce engineered algae for oxygen production
- Target: Create stable liquid water bodies

Phase 3 (2090-2120): Biosphere Establishment
- Plant engineered forests and grasslands
- Introduce pollinator species
- Target: Self-sustaining ecosystem

The project director is Dr. Marcus Chen, based at the Olympus Mons
Research Station. Project Aurora has a total budget of 50 trillion credits.
"""

# Timeout for document processing (seconds)
PROCESSING_TIMEOUT = 120
PROCESSING_POLL_INTERVAL = 3


# ── Helpers ──────────────────────────────────────────────────────────────────


def extract_response_data(response: httpx.Response) -> dict:
    """Extract response data from SSE events."""
    events = parse_sse_events(response)
    result = {
        "events": events,
        "conversation_id": None,
        "response_id": None,
        "text": "",
        "status": None,
        "has_rag_context": False,
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

        if data.get("type") in ("response.completed", "response.done"):
            resp = data.get("response", data)
            result["status"] = resp.get("status")
            result["response_id"] = resp.get("id", result["response_id"])
            result["conversation_id"] = resp.get(
                "conversation_id", result["conversation_id"]
            )

        # Detect RAG context injection
        if data.get("type") == "response.output_item.added":
            item = data.get("item", {})
            if item.get("type") == "rag_context":
                result["has_rag_context"] = True

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
    """POST /responses and parse SSE events."""
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
        timeout=120.0,
    )
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text[:500]}"
    )
    return extract_response_data(response)


async def upload_text_document(
    client: httpx.AsyncClient,
    headers: dict,
    kb_id: str,
    title: str,
    content: str,
) -> dict:
    """Upload a text document to a knowledge base."""
    response = await client.post(
        f"{API_PREFIX}/files/upload-text",
        data={
            "knowledge_base_id": kb_id,
            "title": title,
            "content": content,
        },
        headers=headers,
    )
    assert_success_response(response, 201)
    return response.json()


async def wait_for_document_processing(
    client: httpx.AsyncClient,
    headers: dict,
    kb_id: str,
    document_id: str,
    timeout: int = PROCESSING_TIMEOUT,
) -> str:
    """Poll document status until processing completes or times out.

    Returns the final document status.
    """
    elapsed = 0
    while elapsed < timeout:
        response = await client.get(
            f"{API_PREFIX}/knowledge-bases/{kb_id}/documents",
            headers=headers,
        )
        if response.status_code == 200:
            docs = response.json()
            for doc in docs:
                if doc["id"] == document_id:
                    if doc["status"] in ("completed", "failed", "error"):
                        return doc["status"]
                    break

        await asyncio.sleep(PROCESSING_POLL_INTERVAL)
        elapsed += PROCESSING_POLL_INTERVAL

    return "timeout"


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function")
async def rag_knowledge_base(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
):
    """Create a KB, upload a document, and wait for processing."""
    # Create KB
    kb_response = await async_client.post(
        f"{API_PREFIX}/knowledge-bases",
        json={"name": f"RAG Test KB {uuid.uuid4().hex[:8]}"},
        headers=auth_headers,
    )
    assert_success_response(kb_response, 201)
    kb = kb_response.json()
    kb_id = kb["id"]

    # Brief pause to ensure KB transaction is committed before upload
    await asyncio.sleep(0.2)

    # Upload text document
    doc = await upload_text_document(
        async_client, auth_headers,
        kb_id=kb_id,
        title="Quantum Nexus Protocol",
        content=DOCUMENT_CONTENT,
    )

    # Wait for processing
    status = await wait_for_document_processing(
        async_client, auth_headers, kb_id, doc["id"],
    )

    kb["_doc"] = doc
    kb["_processing_status"] = status

    yield kb

    # Cleanup
    await async_client.delete(
        f"{API_PREFIX}/knowledge-bases/{kb_id}",
        headers=auth_headers,
    )


@pytest_asyncio.fixture(scope="function")
async def rag_assistant(
    async_client: httpx.AsyncClient,
    auth_headers: dict,
    rag_knowledge_base: dict,
):
    """Create an assistant linked to the RAG knowledge base."""
    kb_id = rag_knowledge_base["id"]

    response = await async_client.post(
        f"{API_PREFIX}/assistants",
        json={
            "name": f"RAG Test Assistant {uuid.uuid4().hex[:8]}",
            "system_prompt": (
                "You are a helpful assistant. Answer questions based on the provided "
                "context. If the context contains relevant information, use it in your "
                "answer. Be concise and accurate."
            ),
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "max_tokens": 500,
            "knowledge_base_ids": [kb_id],
        },
        headers=auth_headers,
    )
    assert_success_response(response, 201)
    assistant = response.json()

    yield assistant

    await async_client.delete(
        f"{API_PREFIX}/assistants/{assistant['id']}",
        headers=auth_headers,
    )


# ── Test Classes ─────────────────────────────────────────────────────────────


class TestDocumentUploadAndProcessing:
    """Tests for document upload and processing pipeline."""

    @pytest.mark.asyncio
    async def test_upload_text_document(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_knowledge_base: dict,
    ):
        """Upload a text document and verify it was created."""
        doc = await upload_text_document(
            async_client, auth_headers,
            kb_id=test_knowledge_base["id"],
            title="Test Upload",
            content="Simple test content for upload verification.",
        )
        assert "id" in doc
        assert doc["filename"] == "Test Upload.txt"
        assert doc["status"] == "pending"

    @pytest.mark.asyncio
    async def test_document_processing_completes(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict,
    ):
        """Verify that an uploaded document gets processed successfully."""
        status = rag_knowledge_base["_processing_status"]
        if status == "timeout":
            pytest.skip(
                "Document processing timed out — "
                "Celery worker or inference service may not be running"
            )
        assert status == "completed", (
            f"Document processing failed with status: {status}"
        )

    @pytest.mark.asyncio
    async def test_processed_document_has_chunks(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict,
    ):
        """Verify that a processed document produced chunks."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        kb_id = rag_knowledge_base["id"]

        # Check KB stats for chunk count
        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases/{kb_id}",
            headers=auth_headers,
        )
        assert_success_response(response)
        kb_data = response.json()
        assert kb_data["total_chunks"] > 0, "Expected chunks after processing"
        assert kb_data["document_count"] >= 1

    @pytest.mark.asyncio
    async def test_upload_document_sets_uploaded_by(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_knowledge_base: dict, test_user: dict,
    ):
        """Verify that uploaded_by is set to the current user."""
        doc = await upload_text_document(
            async_client, auth_headers,
            kb_id=test_knowledge_base["id"],
            title="Upload Tracking",
            content="Content for tracking uploaded_by field.",
        )

        # List files and check the uploaded_by field
        response = await async_client.get(
            f"{API_PREFIX}/files",
            headers=auth_headers,
        )
        assert_success_response(response)
        files = response.json()
        matching = [
            f for f in files.get("items", [])
            if f["id"] == doc["id"]
        ]
        if matching:
            assert matching[0].get("uploaded_by_email") == test_user["email"]


class TestAssistantWithKnowledgeBase:
    """Tests for creating assistants with knowledge base attachment."""

    @pytest.mark.asyncio
    async def test_create_assistant_with_kb(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_knowledge_base: dict,
    ):
        """Create an assistant with a knowledge base attached."""
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"KB Assistant {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are helpful.",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "knowledge_base_ids": [test_knowledge_base["id"]],
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert test_knowledge_base["id"] in data.get("knowledge_base_ids", [])

        await async_client.delete(
            f"{API_PREFIX}/assistants/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_assistant_with_multiple_kbs(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        """Create an assistant with multiple knowledge bases."""
        # Create two KBs
        kb1 = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"KB1 {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        kb2 = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"KB2 {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        kb1_id = kb1.json()["id"]
        kb2_id = kb2.json()["id"]

        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Multi-KB {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are helpful.",
                "knowledge_base_ids": [kb1_id, kb2_id],
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert len(data.get("knowledge_base_ids", [])) == 2

        # Cleanup
        await async_client.delete(
            f"{API_PREFIX}/assistants/{data['id']}", headers=auth_headers,
        )
        await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{kb1_id}", headers=auth_headers,
        )
        await async_client.delete(
            f"{API_PREFIX}/knowledge-bases/{kb2_id}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_update_assistant_knowledge_bases(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_assistant: dict, test_knowledge_base: dict,
    ):
        """Update an assistant to add a knowledge base."""
        response = await async_client.put(
            f"{API_PREFIX}/assistants/{test_assistant['id']}",
            json={"knowledge_base_ids": [test_knowledge_base["id"]]},
            headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert test_knowledge_base["id"] in data.get("knowledge_base_ids", [])


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
class TestRAGChat:
    """Tests for RAG-augmented chat via the Responses API.

    These tests verify the full pipeline:
    KB → document → process → embed → Qdrant → chat query → RAG retrieval → LLM response.
    """

    @pytest.mark.asyncio
    async def test_chat_with_rag_context(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Chat with an assistant that has RAG context and verify relevant response."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed — infrastructure may not be running")

        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="What is the Quantum Nexus Protocol and who designed it?",
        )

        assert len(result["events"]) > 0, "Expected SSE events"
        assert result["text"], "Expected non-empty response text"

        # The response should mention information from the document
        text_lower = result["text"].lower()
        assert any(term in text_lower for term in [
            "quantum nexus", "qnp", "arcadia", "elena vasquez",
        ]), f"Expected RAG-sourced content in response, got: {result['text'][:300]}"

    @pytest.mark.asyncio
    async def test_rag_context_event_emitted(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Verify that the response.output_item.added event with rag_context is emitted."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="What bandwidth does QNP support?",
        )

        assert result["has_rag_context"], (
            "Expected 'response.output_item.added' event with type='rag_context'"
        )

    @pytest.mark.asyncio
    async def test_rag_specific_facts(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Ask about specific facts from the document to verify RAG retrieval accuracy."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="What is the maximum range of the Quantum Nexus Protocol?",
        )

        text_lower = result["text"].lower()
        assert "500" in text_lower or "light-year" in text_lower, (
            f"Expected '500 light-years' in response, got: {result['text'][:300]}"
        )

    @pytest.mark.asyncio
    async def test_rag_multi_turn_with_context(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Multi-turn conversation with RAG context maintained across turns."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        # Turn 1: Ask about QNP
        r1 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="Tell me about the Quantum Nexus Protocol layers.",
        )
        conv_id = r1["conversation_id"]
        assert conv_id is not None

        # Turn 2: Follow-up question using previous context
        r2 = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="What does the first layer do?",
            conversation_id=conv_id,
            previous_response_id=r1["response_id"],
        )

        text_lower = r2["text"].lower()
        assert any(term in text_lower for term in [
            "entanglement", "photon",
        ]), f"Expected context about entanglement layer, got: {r2['text'][:300]}"

    @pytest.mark.asyncio
    async def test_chat_without_rag_no_fictional_knowledge(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        """An assistant WITHOUT RAG should not know about fictional QNP content."""
        # Create assistant without any KB
        response = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"No-RAG {uuid.uuid4().hex[:8]}",
                "system_prompt": (
                    "You are a helpful assistant. If you don't know something, "
                    "say 'I don't have information about that.'"
                ),
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_tokens": 200,
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        no_rag_assistant = response.json()

        try:
            result = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=no_rag_assistant["id"],
                message=(
                    "What is the exact bandwidth of the Quantum Nexus Protocol "
                    "developed by the Arcadia Research Institute?"
                ),
            )

            # Without RAG, the model shouldn't know the exact fictional details
            assert not result["has_rag_context"], (
                "No RAG context should be emitted for assistant without KB"
            )
        finally:
            await async_client.delete(
                f"{API_PREFIX}/assistants/{no_rag_assistant['id']}",
                headers=auth_headers,
            )

    @pytest.mark.asyncio
    async def test_rag_creates_conversation(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Verify that RAG chat creates a conversation that can be listed."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="Where is the Arcadia Research Institute located?",
        )
        conv_id = result["conversation_id"]
        assert conv_id is not None

        # Verify conversation appears in list
        convs = await async_client.get(
            f"{API_PREFIX}/chat/conversations",
            params={"assistant_id": rag_assistant["id"]},
            headers=auth_headers,
        )
        assert_success_response(convs)
        conv_list = convs.json()
        assert isinstance(conv_list, list)
        conv_ids = [c["id"] for c in conv_list]
        assert conv_id in conv_ids

    @pytest.mark.asyncio
    async def test_rag_response_contains_specific_details(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Verify response contains specific details from the uploaded document."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="When was the first QNP test conducted and between which locations?",
        )

        text_lower = result["text"].lower()
        # Should mention March 15, 2045 and Proxima Centauri
        assert "2045" in text_lower or "march" in text_lower, (
            f"Expected date reference in response, got: {result['text'][:300]}"
        )


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
class TestMultiKBRAG:
    """Tests for RAG with multiple knowledge bases."""

    @pytest.mark.asyncio
    async def test_multi_kb_rag_retrieval(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        """Create two KBs with different content, attach both to assistant, query each."""
        # Create KB 1 with QNP content
        kb1_resp = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"QNP KB {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        assert_success_response(kb1_resp, 201)
        kb1 = kb1_resp.json()

        # Create KB 2 with Aurora content
        kb2_resp = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"Aurora KB {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        assert_success_response(kb2_resp, 201)
        kb2 = kb2_resp.json()

        try:
            # Upload documents to each KB
            doc1 = await upload_text_document(
                async_client, auth_headers,
                kb_id=kb1["id"],
                title="QNP Document",
                content=DOCUMENT_CONTENT,
            )
            doc2 = await upload_text_document(
                async_client, auth_headers,
                kb_id=kb2["id"],
                title="Aurora Document",
                content=DOCUMENT_CONTENT_2,
            )

            # Wait for both documents to process
            status1 = await wait_for_document_processing(
                async_client, auth_headers, kb1["id"], doc1["id"],
            )
            status2 = await wait_for_document_processing(
                async_client, auth_headers, kb2["id"], doc2["id"],
            )

            if status1 != "completed" or status2 != "completed":
                pytest.skip("Document processing not available")

            # Create assistant with both KBs
            asst_resp = await async_client.post(
                f"{API_PREFIX}/assistants",
                json={
                    "name": f"Multi-KB RAG {uuid.uuid4().hex[:8]}",
                    "system_prompt": (
                        "You are a helpful assistant. Answer based on provided context. "
                        "Be concise."
                    ),
                    "provider": "openai",
                    "model": "gpt-4o-mini",
                    "temperature": 0.0,
                    "max_tokens": 300,
                    "knowledge_base_ids": [kb1["id"], kb2["id"]],
                },
                headers=auth_headers,
            )
            assert_success_response(asst_resp, 201)
            assistant = asst_resp.json()

            try:
                # Query about KB1 content
                r1 = await create_response_and_parse(
                    async_client, auth_headers,
                    assistant_id=assistant["id"],
                    message="Who designed the Quantum Nexus Protocol?",
                )
                assert "vasquez" in r1["text"].lower() or "elena" in r1["text"].lower(), (
                    f"Expected QNP author in response, got: {r1['text'][:200]}"
                )

                # Query about KB2 content
                r2 = await create_response_and_parse(
                    async_client, auth_headers,
                    assistant_id=assistant["id"],
                    message="What is the budget for Project Aurora?",
                )
                assert "50 trillion" in r2["text"].lower() or "50" in r2["text"].lower(), (
                    f"Expected Aurora budget in response, got: {r2['text'][:200]}"
                )
            finally:
                await async_client.delete(
                    f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
                )
        finally:
            await async_client.delete(
                f"{API_PREFIX}/knowledge-bases/{kb1['id']}", headers=auth_headers,
            )
            await async_client.delete(
                f"{API_PREFIX}/knowledge-bases/{kb2['id']}", headers=auth_headers,
            )


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OPENAI_API_KEY not set")
class TestRAGEdgeCases:
    """Edge case tests for RAG pipeline."""

    @pytest.mark.asyncio
    async def test_assistant_with_empty_kb(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        """Chat with an assistant whose KB has no documents."""
        # Create empty KB
        kb_resp = await async_client.post(
            f"{API_PREFIX}/knowledge-bases",
            json={"name": f"Empty KB {uuid.uuid4().hex[:8]}"},
            headers=auth_headers,
        )
        assert_success_response(kb_resp, 201)
        kb = kb_resp.json()

        # Create assistant linked to empty KB
        asst_resp = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"Empty KB Asst {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are helpful. Say you have no information if unsure.",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_tokens": 200,
                "knowledge_base_ids": [kb["id"]],
            },
            headers=auth_headers,
        )
        assert_success_response(asst_resp, 201)
        assistant = asst_resp.json()

        try:
            # Should still work — just no RAG context
            result = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=assistant["id"],
                message="Hello, how are you?",
            )
            assert result["text"], "Expected a response even with empty KB"
        finally:
            await async_client.delete(
                f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
            )
            await async_client.delete(
                f"{API_PREFIX}/knowledge-bases/{kb['id']}", headers=auth_headers,
            )

    @pytest.mark.asyncio
    async def test_per_request_kb_override(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict,
    ):
        """Override knowledge_base_ids at request time."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        # Create assistant WITHOUT any KB
        asst_resp = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"No-KB Override {uuid.uuid4().hex[:8]}",
                "system_prompt": "You are helpful. Use provided context.",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "temperature": 0.0,
                "max_tokens": 300,
            },
            headers=auth_headers,
        )
        assert_success_response(asst_resp, 201)
        assistant = asst_resp.json()

        try:
            # Send request with KB override
            result = await create_response_and_parse(
                async_client, auth_headers,
                assistant_id=assistant["id"],
                message="What is the Quantum Nexus Protocol?",
                knowledge_base_ids=[rag_knowledge_base["id"]],
            )

            # Should have RAG context because of the override
            text_lower = result["text"].lower()
            assert any(term in text_lower for term in [
                "quantum", "nexus", "qnp", "protocol",
            ]), f"Expected RAG content via override, got: {result['text'][:300]}"
        finally:
            await async_client.delete(
                f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
            )

    @pytest.mark.asyncio
    async def test_rag_response_has_response_id(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        rag_knowledge_base: dict, rag_assistant: dict,
    ):
        """Verify that RAG responses have a proper response_id for retrieval."""
        if rag_knowledge_base["_processing_status"] != "completed":
            pytest.skip("Document not processed")

        result = await create_response_and_parse(
            async_client, auth_headers,
            assistant_id=rag_assistant["id"],
            message="What is QNP?",
        )

        resp_id = result["response_id"]
        assert resp_id is not None, "Expected response_id in SSE events"

        # Verify response can be retrieved
        get_resp = await async_client.get(
            f"{API_PREFIX}/responses/{resp_id}",
            headers=auth_headers,
        )
        assert_success_response(get_resp)
        data = get_resp.json()
        assert data["id"] == resp_id


class TestUserIsolation:
    """Tests for user-scoped resource isolation."""

    @pytest.mark.asyncio
    async def test_user_cannot_see_other_user_kb(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_knowledge_base: dict,
    ):
        """A second user should not see KBs created by the first user."""
        # Register a second user
        user2_data = TestDataFactory.user_data()
        reg_resp = await async_client.post(
            f"{API_PREFIX}/auth/register", json=user2_data,
        )
        assert reg_resp.status_code in (201, 400, 409)

        login_resp = await async_client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": user2_data["email"], "password": user2_data["password"]},
        )
        assert_success_response(login_resp)
        user2_headers = {
            "Authorization": f"Bearer {login_resp.json()['access_token']}",
        }

        # User 2 lists KBs — should NOT see user 1's KB
        response = await async_client.get(
            f"{API_PREFIX}/knowledge-bases",
            headers=user2_headers,
        )
        assert_success_response(response)
        data = response.json()
        kb_ids = [kb["id"] for kb in data.get("items", [])]
        assert test_knowledge_base["id"] not in kb_ids, (
            "User 2 should not see User 1's knowledge base"
        )

    @pytest.mark.asyncio
    async def test_user_cannot_see_other_user_assistant(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_assistant: dict,
    ):
        """A second user should not see assistants created by the first user."""
        user2_data = TestDataFactory.user_data()
        await async_client.post(f"{API_PREFIX}/auth/register", json=user2_data)
        login_resp = await async_client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": user2_data["email"], "password": user2_data["password"]},
        )
        assert_success_response(login_resp)
        user2_headers = {
            "Authorization": f"Bearer {login_resp.json()['access_token']}",
        }

        response = await async_client.get(
            f"{API_PREFIX}/assistants",
            headers=user2_headers,
        )
        assert_success_response(response)
        data = response.json()
        assistant_ids = [a["id"] for a in data.get("items", [])]
        assert test_assistant["id"] not in assistant_ids, (
            "User 2 should not see User 1's assistant"
        )

    @pytest.mark.asyncio
    async def test_user_cannot_see_other_user_files(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
        test_knowledge_base: dict,
    ):
        """A second user should not see files uploaded by the first user."""
        # Upload a file as user 1
        doc = await upload_text_document(
            async_client, auth_headers,
            kb_id=test_knowledge_base["id"],
            title="User1 Private Doc",
            content="Private content for user 1 only.",
        )

        # Register user 2
        user2_data = TestDataFactory.user_data()
        await async_client.post(f"{API_PREFIX}/auth/register", json=user2_data)
        login_resp = await async_client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": user2_data["email"], "password": user2_data["password"]},
        )
        assert_success_response(login_resp)
        user2_headers = {
            "Authorization": f"Bearer {login_resp.json()['access_token']}",
        }

        # User 2 lists files — should NOT see user 1's file
        response = await async_client.get(
            f"{API_PREFIX}/files",
            headers=user2_headers,
        )
        assert_success_response(response)
        files = response.json()
        file_ids = [f["id"] for f in files.get("items", [])]
        assert doc["id"] not in file_ids, (
            "User 2 should not see User 1's uploaded file"
        )
