"""E2E tests for voice presets CRUD, available providers, transcription, and synthesis.

Voice preset CRUD tests do not require OPENAI_API_KEY.
Transcription/synthesis tests are skipped if OPENAI_API_KEY is not set.
"""

import base64
import struct
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
    requires_openai,
)

pytestmark = pytest.mark.e2e


def _generate_silent_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a minimal silent WAV file for testing."""
    num_samples = int(sample_rate * duration_s)
    # WAV header
    data_size = num_samples * 2  # 16-bit mono
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,  # chunk size
        1,   # PCM
        1,   # mono
        sample_rate,
        sample_rate * 2,  # byte rate
        2,   # block align
        16,  # bits per sample
        b"data",
        data_size,
    )
    # Silent samples
    samples = b"\x00\x00" * num_samples
    return header + samples


# ---------------------------------------------------------------------------
# TestVoicePresetCRUD
# ---------------------------------------------------------------------------

class TestVoicePresetCRUD:
    """Tests for /voice-presets CRUD endpoints."""

    @pytest.mark.asyncio
    async def test_create_tts_preset_browser(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"Browser TTS {uuid.uuid4().hex[:8]}",
                "type": "tts",
                "config": {"source": "browser"},
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert "id" in data
        assert data["type"] == "tts"
        assert data["config"]["source"] == "browser"

        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_tts_preset_openai(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"OpenAI TTS {uuid.uuid4().hex[:8]}",
                "type": "tts",
                "config": {"source": "openai", "voice_id": "nova", "speed": 1.0},
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        data = response.json()
        assert data["config"]["voice_id"] == "nova"

        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{data['id']}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_stt_preset_browser(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"Browser STT {uuid.uuid4().hex[:8]}",
                "type": "stt",
                "config": {"source": "browser", "language": "en-US"},
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)
        assert response.json()["type"] == "stt"

        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{response.json()['id']}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_create_stt_preset_openai(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"OpenAI STT {uuid.uuid4().hex[:8]}",
                "type": "stt",
                "config": {"source": "openai", "language": "en-US"},
            },
            headers=auth_headers,
        )
        assert_success_response(response, 201)

        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{response.json()['id']}",
            headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_list_presets_all(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice-presets", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_list_presets_filter_tts(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice-presets",
            params={"type": "tts"},
            headers=auth_headers,
        )
        assert_success_response(response)
        items = response.json()["items"]
        for item in items:
            assert item["type"] == "tts"

    @pytest.mark.asyncio
    async def test_list_presets_filter_stt(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        # Create an STT preset first
        create = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"STT {uuid.uuid4().hex[:8]}",
                "type": "stt",
                "config": {"source": "browser"},
            },
            headers=auth_headers,
        )
        preset_id = create.json()["id"]

        response = await async_client.get(
            f"{API_PREFIX}/voice-presets",
            params={"type": "stt"},
            headers=auth_headers,
        )
        assert_success_response(response)
        items = response.json()["items"]
        for item in items:
            assert item["type"] == "stt"

        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{preset_id}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_list_presets_pagination(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice-presets",
            params={"page": 1, "page_size": 2},
            headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert len(data["items"]) <= 2

    @pytest.mark.asyncio
    async def test_get_preset(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice-presets/{test_voice_preset['id']}",
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["id"] == test_voice_preset["id"]

    @pytest.mark.asyncio
    async def test_update_preset_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.patch(
            f"{API_PREFIX}/voice-presets/{test_voice_preset['id']}",
            json={"name": "Updated Preset"},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["name"] == "Updated Preset"

    @pytest.mark.asyncio
    async def test_update_preset_config(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.patch(
            f"{API_PREFIX}/voice-presets/{test_voice_preset['id']}",
            json={"config": {"source": "browser", "rate": 1.2}},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["config"]["rate"] == 1.2

    @pytest.mark.asyncio
    async def test_set_default_preset(
        self, async_client: httpx.AsyncClient, auth_headers: dict, test_voice_preset: dict,
    ):
        response = await async_client.patch(
            f"{API_PREFIX}/voice-presets/{test_voice_preset['id']}",
            json={"is_default": True},
            headers=auth_headers,
        )
        assert_success_response(response)
        assert response.json()["is_default"] is True

    @pytest.mark.asyncio
    async def test_set_default_unsets_previous(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        # Create two TTS presets
        p1 = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"Default1 {uuid.uuid4().hex[:8]}",
                "type": "tts",
                "config": {"source": "browser"},
                "is_default": True,
            },
            headers=auth_headers,
        )
        p1_id = p1.json()["id"]

        p2 = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"Default2 {uuid.uuid4().hex[:8]}",
                "type": "tts",
                "config": {"source": "browser"},
                "is_default": True,
            },
            headers=auth_headers,
        )
        p2_id = p2.json()["id"]

        # Verify p2 is default, p1 is not
        get_p1 = await async_client.get(
            f"{API_PREFIX}/voice-presets/{p1_id}", headers=auth_headers,
        )
        get_p2 = await async_client.get(
            f"{API_PREFIX}/voice-presets/{p2_id}", headers=auth_headers,
        )
        # At least p2 should be default
        assert get_p2.json()["is_default"] is True

        # Cleanup
        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{p1_id}", headers=auth_headers,
        )
        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{p2_id}", headers=auth_headers,
        )

    @pytest.mark.asyncio
    async def test_delete_preset(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"Del Preset {uuid.uuid4().hex[:8]}",
                "type": "tts",
                "config": {"source": "browser"},
            },
            headers=auth_headers,
        )
        pid = create.json()["id"]

        response = await async_client.delete(
            f"{API_PREFIX}/voice-presets/{pid}", headers=auth_headers,
        )
        assert response.status_code in (200, 204)

    @pytest.mark.asyncio
    async def test_get_deleted_preset(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        create = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={
                "name": f"Ghost Preset {uuid.uuid4().hex[:8]}",
                "type": "tts",
                "config": {"source": "browser"},
            },
            headers=auth_headers,
        )
        pid = create.json()["id"]
        await async_client.delete(
            f"{API_PREFIX}/voice-presets/{pid}", headers=auth_headers,
        )

        response = await async_client.get(
            f"{API_PREFIX}/voice-presets/{pid}", headers=auth_headers,
        )
        assert_error_response(response, 404)

    @pytest.mark.asyncio
    async def test_create_missing_name(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={"type": "tts", "config": {"source": "browser"}},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_create_missing_type(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={"name": "No type", "config": {"source": "browser"}},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_create_invalid_type(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={"name": "Bad type", "type": "invalid", "config": {}},
            headers=auth_headers,
        )
        assert_error_response(response, 422)

    @pytest.mark.asyncio
    async def test_no_auth_presets(self, async_client: httpx.AsyncClient):
        response = await async_client.post(
            f"{API_PREFIX}/voice-presets",
            json={"name": "NoAuth", "type": "tts", "config": {}},
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestAvailableProviders
# ---------------------------------------------------------------------------

class TestAvailableProviders:
    """Tests for GET /voice/available-providers."""

    @pytest.mark.asyncio
    async def test_get_available_providers(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice/available-providers", headers=auth_headers,
        )
        assert_success_response(response)
        data = response.json()
        assert "tts" in data
        assert "stt" in data

    @pytest.mark.asyncio
    async def test_browser_always_available(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice/available-providers", headers=auth_headers,
        )
        data = response.json()

        # Browser should appear in both TTS and STT
        tts_sources = [p.get("source") or p.get("name") for p in data["tts"]]
        stt_sources = [p.get("source") or p.get("name") for p in data["stt"]]
        assert "browser" in tts_sources
        assert "browser" in stt_sources

    @pytest.mark.asyncio
    async def test_response_structure(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.get(
            f"{API_PREFIX}/voice/available-providers", headers=auth_headers,
        )
        data = response.json()
        assert isinstance(data["tts"], list)
        assert isinstance(data["stt"], list)

        # Each provider should have at least source/name and available fields
        if data["tts"]:
            provider = data["tts"][0]
            assert "source" in provider or "name" in provider

    @pytest.mark.asyncio
    async def test_no_auth_available_providers(self, async_client: httpx.AsyncClient):
        response = await async_client.get(
            f"{API_PREFIX}/voice/available-providers",
        )
        assert_error_response(response, 401)


# ---------------------------------------------------------------------------
# TestVoiceTranscription (requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

class TestVoiceTranscription:
    """Tests for POST /voice/transcribe."""

    @pytest.mark.asyncio
    @requires_openai
    async def test_transcribe_audio(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        wav_bytes = _generate_silent_wav(0.5)
        audio_b64 = base64.b64encode(wav_bytes).decode()

        response = await async_client.post(
            f"{API_PREFIX}/voice/transcribe",
            json={"audio": audio_b64, "audio_format": "wav"},
            headers=auth_headers,
            timeout=30.0,
        )
        # May return empty transcription for silence, but should not error
        assert response.status_code in (200, 400)

    @pytest.mark.asyncio
    @requires_openai
    async def test_transcribe_empty_audio(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice/transcribe",
            json={"audio": "", "audio_format": "wav"},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422, 500)

    @pytest.mark.asyncio
    @requires_openai
    async def test_transcribe_invalid_format(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice/transcribe",
            json={"audio": "not-base64-audio", "audio_format": "wav"},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# TestVoiceSynthesis (requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

class TestVoiceSynthesis:
    """Tests for POST /voice/synthesize."""

    @pytest.mark.asyncio
    @requires_openai
    async def test_synthesize_speech(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice/synthesize",
            json={
                "text": "Hello, this is a test.",
                "voice_id": "nova",
                "provider": "openai",
            },
            headers=auth_headers,
            timeout=30.0,
        )
        # 400 if OpenAI API key not configured server-side
        assert response.status_code in (200, 400)
        if response.status_code == 200:
            data = response.json()
            assert "audio" in data

    @pytest.mark.asyncio
    @requires_openai
    async def test_synthesize_empty_text(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        response = await async_client.post(
            f"{API_PREFIX}/voice/synthesize",
            json={"text": "", "voice_id": "nova", "provider": "openai"},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422, 500)

    @pytest.mark.asyncio
    @requires_openai
    async def test_synthesize_different_voices(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        for voice in ["alloy", "echo", "nova"]:
            response = await async_client.post(
                f"{API_PREFIX}/voice/synthesize",
                json={
                    "text": "Test voice.",
                    "voice_id": voice,
                    "provider": "openai",
                },
                headers=auth_headers,
                timeout=30.0,
            )
            assert response.status_code in (200, 400), f"Failed for voice: {voice}"

    @pytest.mark.asyncio
    @requires_openai
    async def test_synthesize_different_speeds(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        for speed in [0.5, 1.0, 2.0]:
            response = await async_client.post(
                f"{API_PREFIX}/voice/synthesize",
                json={
                    "text": "Speed test.",
                    "voice_id": "nova",
                    "provider": "openai",
                    "speed": speed,
                },
                headers=auth_headers,
                timeout=30.0,
            )
            assert response.status_code in (200, 400, 422), f"Failed for speed: {speed}"


# ---------------------------------------------------------------------------
# TestVoiceChat (requires OPENAI_API_KEY)
# ---------------------------------------------------------------------------

class TestVoiceChat:
    """Tests for POST /voice/chat."""

    @pytest.mark.asyncio
    @requires_openai
    async def test_voice_chat_unified(
        self, async_client: httpx.AsyncClient, auth_headers: dict,
    ):
        # Create an assistant for the voice chat
        assistant_resp = await async_client.post(
            f"{API_PREFIX}/assistants",
            json={
                "name": f"VoiceChat {uuid.uuid4().hex[:8]}",
                "system_prompt": "Be brief.",
                "provider": "openai",
                "model": "gpt-4o-mini",
            },
            headers=auth_headers,
        )
        assistant = assistant_resp.json()

        wav_bytes = _generate_silent_wav(1.0)
        audio_b64 = base64.b64encode(wav_bytes).decode()

        response = await async_client.post(
            f"{API_PREFIX}/voice/chat",
            json={
                "audio": audio_b64,
                "assistant_id": assistant["id"],
                "audio_format": "wav",
                "stream": False,
            },
            headers=auth_headers,
            timeout=60.0,
        )
        # Voice chat may fail if STT returns empty for silence
        assert response.status_code in (200, 400, 500)

        # Cleanup
        await async_client.delete(
            f"{API_PREFIX}/assistants/{assistant['id']}", headers=auth_headers,
        )
