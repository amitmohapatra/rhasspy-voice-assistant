"""Voice API routes for transcription and synthesis."""

import base64
import logging
from uuid import UUID
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.api.deps import DbSession, CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(tags=["voice"])


# ===================
# AVAILABLE PROVIDERS
# ===================


@router.get("/available-providers")
async def get_available_voice_providers(
    db: DbSession,
    current_user: CurrentUser,
):
    """Return which STT/TTS vendors are available.

    A vendor is available if:
    1. Its API key exists and is_set in the secrets table
    2. Its provider is toggled active in ai_providers (status='active')

    Browser is always available (no key/toggle needed).
    """
    from sqlalchemy import select
    from src.models.secret import Secret
    from src.models.ai_model import AIProvider, ProviderStatus

    # Fetch all secrets to check which keys are set
    result = await db.execute(select(Secret.key, Secret.is_set))
    secrets_map: dict[str, bool] = {row.key: row.is_set for row in result.all()}

    # Fetch all providers to check status
    result = await db.execute(select(AIProvider.name, AIProvider.status))
    providers_map: dict[str, str] = {row.name: row.status.value if hasattr(row.status, 'value') else row.status for row in result.all()}

    def _check(provider_name: str, secret_key: str) -> tuple[bool, str | None]:
        """Check if a provider is available (has key + is active)."""
        key_set = secrets_map.get(secret_key, False)
        provider_active = providers_map.get(provider_name, None)

        if not key_set:
            return False, "API key not configured"
        if provider_active is None:
            # Provider not in ai_providers table — allow if key is set
            return True, None
        if provider_active != "active":
            return False, "Provider not enabled"
        return True, None

    # TTS providers
    tts = [
        {"source": "browser", "name": "Browser", "available": True},
    ]

    openai_tts_ok, openai_tts_reason = _check("openai", "OPENAI_API_KEY")
    tts.append({
        "source": "openai",
        "name": "OpenAI TTS",
        "available": openai_tts_ok,
        "voices": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        **({"reason": openai_tts_reason} if openai_tts_reason else {}),
    })

    el_ok, el_reason = _check("elevenlabs", "ELEVENLABS_API_KEY")
    tts.append({
        "source": "elevenlabs",
        "name": "ElevenLabs",
        "available": el_ok,
        **({"reason": el_reason} if el_reason else {}),
    })

    azure_tts_ok, azure_tts_reason = _check("azure", "AZURE_SPEECH_KEY")
    tts.append({
        "source": "azure",
        "name": "Azure TTS",
        "available": azure_tts_ok,
        **({"reason": azure_tts_reason} if azure_tts_reason else {}),
    })

    google_tts_ok, google_tts_reason = _check("google", "GOOGLE_API_KEY")
    tts.append({
        "source": "google",
        "name": "Google TTS",
        "available": google_tts_ok,
        **({"reason": google_tts_reason} if google_tts_reason else {}),
    })

    # STT providers
    stt = [
        {"source": "browser", "name": "Browser", "available": True},
    ]

    openai_stt_ok, openai_stt_reason = _check("openai", "OPENAI_API_KEY")
    stt.append({
        "source": "openai",
        "name": "OpenAI Whisper",
        "available": openai_stt_ok,
        **({"reason": openai_stt_reason} if openai_stt_reason else {}),
    })

    dg_ok, dg_reason = _check("deepgram", "DEEPGRAM_API_KEY")
    stt.append({
        "source": "deepgram",
        "name": "Deepgram Nova-2",
        "available": dg_ok,
        **({"reason": dg_reason} if dg_reason else {}),
    })

    asm_ok, asm_reason = _check("assemblyai", "ASSEMBLYAI_API_KEY")
    stt.append({
        "source": "assembly",
        "name": "AssemblyAI",
        "available": asm_ok,
        **({"reason": asm_reason} if asm_reason else {}),
    })

    azure_stt_ok, azure_stt_reason = _check("azure", "AZURE_SPEECH_KEY")
    stt.append({
        "source": "azure",
        "name": "Azure Speech",
        "available": azure_stt_ok,
        **({"reason": azure_stt_reason} if azure_stt_reason else {}),
    })

    google_stt_ok, google_stt_reason = _check("google", "GOOGLE_API_KEY")
    stt.append({
        "source": "google",
        "name": "Google Speech",
        "available": google_stt_ok,
        **({"reason": google_stt_reason} if google_stt_reason else {}),
    })

    return {"tts": tts, "stt": stt}


# ===================
# UNIFIED VOICE CHAT
# ===================


class VoiceChatRequest(BaseModel):
    """Unified voice chat request - does STT + LLM + TTS in one call."""
    audio: str  # Base64 encoded audio input
    audio_format: str = "webm"  # Input audio format
    assistant_id: str  # Assistant to chat with
    conversation_id: str | None = None  # Continue existing conversation
    language: str = "en-US"

    # TTS options
    voice_id: str | None = None
    speaking_rate: float = 1.0

    # Response options
    stream: bool = True  # Stream the audio response
    include_text: bool = True  # Include text in response


class VoiceChatResponse(BaseModel):
    """Response from unified voice chat (non-streaming)."""
    transcribed_text: str  # What user said
    response_text: str  # Assistant's response
    audio: str | None = None  # Base64 encoded TTS audio (if not streaming)
    audio_format: str = "mp3"
    conversation_id: str
    response_id: str | None = None


@router.post("/chat")
async def voice_chat(
    request: VoiceChatRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Unified voice chat endpoint.

    Does everything in one call:
    1. Transcribes audio input (STT)
    2. Sends to assistant (LLM)
    3. Converts response to speech (TTS)

    Supports streaming audio response for low latency.

    **Streaming Response Format:**
    When stream=True, returns Server-Sent Events:
    - `event: transcript` - User's transcribed text
    - `event: text` - Assistant's text response (chunked)
    - `event: audio` - Base64 audio chunks
    - `event: done` - Completion signal

    **Non-Streaming Response:**
    When stream=False, returns VoiceChatResponse JSON.
    """
    try:
        # 1. Decode and transcribe audio
        audio_bytes = base64.b64decode(request.audio)

        from sqlalchemy import select
        from src.models.assistant import Assistant
        from src.models.secret import Secret
        from src.core.config import settings

        # Get assistant
        result = await db.execute(
            select(Assistant).where(Assistant.id == request.assistant_id)
        )
        assistant = result.scalar_one_or_none()

        if not assistant:
            raise HTTPException(status_code=404, detail="Assistant not found")

        # Get STT provider config from app settings
        stt_provider = getattr(settings, "stt_provider", "openai")

        # Get API key
        result = await db.execute(
            select(Secret).where(
                Secret.key == f"{stt_provider.upper()}_API_KEY",
            )
        )
        secret = result.scalar_one_or_none()
        stt_api_key = secret.value if secret else None

        # Transcribe
        if stt_provider == "openai":
            transcribed_text = await _transcribe_openai(
                audio_bytes, request.audio_format, request.language, stt_api_key
            )
        elif stt_provider == "deepgram":
            transcribed_text = await _transcribe_deepgram(
                audio_bytes, request.audio_format, request.language, stt_api_key
            )
        else:
            transcribed_text = await _transcribe_openai(
                audio_bytes, request.audio_format, request.language, stt_api_key
            )

        if not transcribed_text.strip():
            raise HTTPException(status_code=400, detail="Could not transcribe audio")

        # 2. Get LLM response
        from src.models.conversation import Conversation
        from src.models.response import Response as ResponseModel, ResponseItem
        import uuid

        # Get or create conversation
        if request.conversation_id:
            result = await db.execute(
                select(Conversation).where(Conversation.id == request.conversation_id)
            )
            conversation = result.scalar_one_or_none()
            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            conversation = Conversation(
                id=uuid.uuid4(),
                user_id=current_user.id,
                assistant_id=assistant.id,
                status="active",
            )
            db.add(conversation)
            await db.flush()

        # Load history from previous responses
        result = await db.execute(
            select(ResponseItem)
            .join(ResponseModel, ResponseItem.response_id == ResponseModel.id)
            .where(ResponseModel.conversation_id == conversation.id)
            .order_by(ResponseModel.created_at, ResponseItem.sequence_order)
        )
        history_items = result.scalars().all()

        # Build messages for LLM
        messages = [{"role": "system", "content": assistant.system_prompt}]
        for item in history_items:
            if item.item_type == "message" and item.role and item.content:
                messages.append({"role": item.role, "content": item.content})
        messages.append({"role": "user", "content": transcribed_text})

        # Call LLM
        llm_response = await _call_llm(
            provider=assistant.provider,
            model=assistant.model,
            messages=messages,
            temperature=assistant.temperature,
            max_tokens=assistant.max_tokens,
            db=db,
        )

        # Create Response + ResponseItems
        previous_response_id = None
        if conversation.latest_response_id:
            previous_response_id = conversation.latest_response_id

        response_record = ResponseModel(
            id=uuid.uuid4(),
            user_id=current_user.id,
            assistant_id=assistant.id,
            conversation_id=conversation.id,
            previous_response_id=previous_response_id,
            model=assistant.model,
            provider=assistant.provider,
            instructions=assistant.system_prompt,
            temperature=assistant.temperature or 0.7,
            max_tokens=assistant.max_tokens,
            status="completed",
            status_reason="stop",
        )
        db.add(response_record)

        # User input item
        user_item = ResponseItem(
            id=uuid.uuid4(),
            response_id=response_record.id,
            sequence_order=0,
            item_type="message",
            direction="input",
            role="user",
            content=transcribed_text,
            content_type="audio",
        )
        db.add(user_item)

        # Assistant output item
        assistant_item = ResponseItem(
            id=uuid.uuid4(),
            response_id=response_record.id,
            sequence_order=1,
            item_type="message",
            direction="output",
            role="assistant",
            content=llm_response,
            content_type="text",
        )
        db.add(assistant_item)

        # Update conversation
        conversation.latest_response_id = response_record.id
        conversation.response_count = (conversation.response_count or 0) + 1

        await db.commit()

        # 3. Convert response to speech
        tts_provider = getattr(settings, "tts_provider", "openai")
        tts_voice = getattr(settings, "tts_voice", "alloy")
        voice_id = request.voice_id or tts_voice

        result = await db.execute(
            select(Secret).where(
                Secret.key == f"{tts_provider.upper()}_API_KEY",
            )
        )
        secret = result.scalar_one_or_none()
        tts_api_key = secret.value if secret else None

        if request.stream:
            # Return streaming response
            return StreamingResponse(
                _stream_voice_response(
                    transcribed_text=transcribed_text,
                    response_text=llm_response,
                    tts_provider=tts_provider,
                    voice_id=voice_id,
                    speaking_rate=request.speaking_rate,
                    api_key=tts_api_key,
                    conversation_id=str(conversation.id),
                ),
                media_type="text/event-stream",
            )
        else:
            # Non-streaming: synthesize full audio
            if tts_provider == "elevenlabs":
                audio_bytes, audio_format = await _synthesize_elevenlabs(
                    llm_response, voice_id, request.speaking_rate, tts_api_key
                )
            else:
                audio_bytes, audio_format = await _synthesize_openai(
                    llm_response, voice_id, request.speaking_rate, tts_api_key
                )

            return VoiceChatResponse(
                transcribed_text=transcribed_text,
                response_text=llm_response,
                audio=base64.b64encode(audio_bytes).decode(),
                audio_format=audio_format,
                conversation_id=str(conversation.id),
                response_id=str(response_record.id),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_voice_response(
    transcribed_text: str,
    response_text: str,
    tts_provider: str,
    voice_id: str,
    speaking_rate: float,
    api_key: str | None,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    """Stream voice chat response as SSE events."""
    import json

    # Send transcript
    yield f"event: transcript\ndata: {json.dumps({'text': transcribed_text})}\n\n"

    # Send text response
    yield f"event: text\ndata: {json.dumps({'text': response_text})}\n\n"

    # Send conversation ID
    yield f"event: conversation\ndata: {json.dumps({'id': conversation_id})}\n\n"

    # Generate and stream audio
    try:
        if tts_provider == "elevenlabs":
            audio_bytes, audio_format = await _synthesize_elevenlabs(
                response_text, voice_id, speaking_rate, api_key
            )
        else:
            audio_bytes, audio_format = await _synthesize_openai(
                response_text, voice_id, speaking_rate, api_key
            )

        # Send audio in chunks for streaming playback
        chunk_size = 8192  # 8KB chunks
        for i in range(0, len(audio_bytes), chunk_size):
            chunk = audio_bytes[i:i + chunk_size]
            chunk_b64 = base64.b64encode(chunk).decode()
            yield f"event: audio\ndata: {json.dumps({'chunk': chunk_b64, 'format': audio_format})}\n\n"

        yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"


async def _call_llm(
    provider: str,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int | None,
    db,
) -> str:
    """Call LLM provider and return response."""
    import httpx
    import os
    from sqlalchemy import select
    from src.models.secret import Secret

    # Get API key
    result = await db.execute(
        select(Secret).where(
            Secret.key == f"{provider.upper()}_API_KEY",
        )
    )
    secret = result.scalar_one_or_none()
    api_key = secret.value if secret else os.getenv(f"{provider.upper()}_API_KEY")

    if not api_key:
        raise HTTPException(status_code=400, detail=f"{provider} API key not configured")

    async with httpx.AsyncClient() as client:
        if provider == "openai":
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens or 1000,
                },
                timeout=60.0,
            )
            if response.status_code != 200:
                raise Exception(f"OpenAI error: {response.text}")
            return response.json()["choices"][0]["message"]["content"]

        elif provider == "anthropic":
            # Convert messages format for Anthropic
            system_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
            user_messages = [m for m in messages if m["role"] != "system"]

            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": model,
                    "max_tokens": max_tokens or 1000,
                    "system": system_msg,
                    "messages": user_messages,
                },
                timeout=60.0,
            )
            if response.status_code != 200:
                raise Exception(f"Anthropic error: {response.text}")
            return response.json()["content"][0]["text"]

        elif provider == "google":
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent",
                params={"key": api_key},
                json={
                    "contents": [{"parts": [{"text": m["content"]}]} for m in messages],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_tokens or 1000,
                    },
                },
                timeout=60.0,
            )
            if response.status_code != 200:
                raise Exception(f"Google error: {response.text}")
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


# ===================
# INDIVIDUAL ENDPOINTS (kept for backwards compatibility)
# ===================


class TranscribeRequest(BaseModel):
    """Request for audio transcription."""
    audio: str  # Base64 encoded audio
    format: str = "webm"  # Audio format: webm, wav, mp3
    language: str | None = None  # Optional language hint


class TranscribeResponse(BaseModel):
    """Response from transcription."""
    text: str
    language: str | None = None
    confidence: float | None = None
    duration_seconds: float | None = None


class SynthesizeRequest(BaseModel):
    """Request for text-to-speech synthesis."""
    text: str
    voice_id: str | None = None
    provider: str | None = None
    language: str = "en-US"
    speaking_rate: float = 1.0
    pitch: float = 0.0


class SynthesizeResponse(BaseModel):
    """Response from synthesis."""
    audio: str  # Base64 encoded audio
    format: str  # Audio format
    duration_seconds: float | None = None


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(
    request: TranscribeRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Transcribe audio to text using configured STT provider.

    Accepts base64-encoded audio in various formats (webm, wav, mp3).
    Uses the configured STT provider.
    """
    try:
        # Decode audio
        audio_bytes = base64.b64decode(request.audio)

        # Get STT provider configuration from app settings
        from sqlalchemy import select
        from src.models.secret import Secret
        from src.core.config import settings

        provider_name = getattr(settings, "stt_provider", "openai")

        # Get API key from secrets
        result = await db.execute(
            select(Secret).where(
                Secret.key == f"{provider_name.upper()}_API_KEY",
            )
        )
        secret = result.scalar_one_or_none()
        api_key = secret.value if secret else None

        # Transcribe based on provider
        if provider_name == "openai":
            text = await _transcribe_openai(audio_bytes, request.format, request.language, api_key)
        elif provider_name == "deepgram":
            text = await _transcribe_deepgram(audio_bytes, request.format, request.language, api_key)
        elif provider_name == "assembly":
            text = await _transcribe_assemblyai(audio_bytes, request.format, request.language, api_key)
        elif provider_name == "google":
            text = await _transcribe_google(audio_bytes, request.format, request.language, api_key)
        elif provider_name == "azure":
            text = await _transcribe_azure(audio_bytes, request.format, request.language, api_key)
        else:
            # Fallback to OpenAI
            text = await _transcribe_openai(audio_bytes, request.format, request.language, api_key)

        # Log usage
        from src.models.usage import UsageLog
        usage = UsageLog(
            user_id=current_user.id,
            provider=provider_name,
            model=provider_name,
            input_tokens=len(audio_bytes),
            output_tokens=len(text),
            total_tokens=len(audio_bytes) + len(text),
            request_type="stt",
        )
        db.add(usage)

        return TranscribeResponse(
            text=text,
            language=request.language,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription failed: {str(e)}",
        )


@router.post("/synthesize", response_model=SynthesizeResponse)
async def synthesize_speech(
    request: SynthesizeRequest,
    db: DbSession,
    current_user: CurrentUser,
):
    """Synthesize text to speech using configured TTS provider.

    Returns base64-encoded audio.
    """
    try:
        # Get TTS provider configuration from app settings
        from sqlalchemy import select
        from src.models.secret import Secret
        from src.core.config import settings

        tts_provider_default = getattr(settings, "tts_provider", "elevenlabs")
        tts_voice_default = getattr(settings, "tts_voice", "alloy")
        provider_name = request.provider or tts_provider_default

        # Get API key from secrets
        result = await db.execute(
            select(Secret).where(
                Secret.key == f"{provider_name.upper()}_API_KEY",
            )
        )
        secret = result.scalar_one_or_none()
        api_key = secret.value if secret else None

        # Synthesize based on provider
        voice_id = request.voice_id or tts_voice_default

        if provider_name == "elevenlabs":
            audio_bytes, format_type = await _synthesize_elevenlabs(
                request.text, voice_id, request.speaking_rate, api_key
            )
        elif provider_name == "openai":
            audio_bytes, format_type = await _synthesize_openai(
                request.text, voice_id, request.speaking_rate, api_key
            )
        elif provider_name == "azure":
            audio_bytes, format_type = await _synthesize_azure(
                request.text, voice_id, request.speaking_rate, request.language, api_key
            )
        elif provider_name == "google":
            audio_bytes, format_type = await _synthesize_google(
                request.text, voice_id, request.speaking_rate, request.language, api_key
            )
        else:
            audio_bytes, format_type = await _synthesize_openai(
                request.text, voice_id, request.speaking_rate, api_key
            )

        # Log usage
        from src.models.usage import UsageLog
        usage = UsageLog(
            user_id=current_user.id,
            provider=provider_name,
            model=voice_id,
            input_tokens=len(request.text),
            output_tokens=len(audio_bytes),
            total_tokens=len(request.text) + len(audio_bytes),
            request_type="tts",
        )
        db.add(usage)

        return SynthesizeResponse(
            audio=base64.b64encode(audio_bytes).decode(),
            format=format_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Synthesis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech synthesis failed: {str(e)}",
        )


# ==================
# Provider implementations
# ==================


async def _transcribe_openai(
    audio_bytes: bytes,
    format_type: str,
    language: str | None,
    api_key: str | None,
) -> str:
    """Transcribe using OpenAI Whisper."""
    import httpx
    import os

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key not configured",
        )

    # Determine file extension
    ext = "webm" if "webm" in format_type else "wav"

    async with httpx.AsyncClient() as client:
        files = {
            "file": (f"audio.{ext}", audio_bytes, f"audio/{ext}"),
            "model": (None, "whisper-1"),
        }
        if language:
            files["language"] = (None, language[:2])

        response = await client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files=files,
            timeout=60.0,
        )

        if response.status_code != 200:
            raise Exception(f"OpenAI API error: {response.text}")

        data = response.json()
        return data.get("text", "")


async def _transcribe_deepgram(
    audio_bytes: bytes,
    format_type: str,
    language: str | None,
    api_key: str | None,
) -> str:
    """Transcribe using Deepgram."""
    import httpx
    import os

    api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deepgram API key not configured",
        )

    params = {
        "model": "nova-2",
        "smart_format": "true",
    }
    if language:
        params["language"] = language[:2]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.deepgram.com/v1/listen",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": f"audio/{format_type}",
            },
            params=params,
            content=audio_bytes,
            timeout=60.0,
        )

        if response.status_code != 200:
            raise Exception(f"Deepgram API error: {response.text}")

        data = response.json()
        return data.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")


async def _transcribe_assemblyai(
    audio_bytes: bytes,
    format_type: str,
    language: str | None,
    api_key: str | None,
) -> str:
    """Transcribe using AssemblyAI."""
    import httpx
    import os

    api_key = api_key or os.getenv("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AssemblyAI API key not configured",
        )

    async with httpx.AsyncClient() as client:
        # Upload audio
        upload_response = await client.post(
            "https://api.assemblyai.com/v2/upload",
            headers={"Authorization": api_key},
            content=audio_bytes,
            timeout=60.0,
        )

        if upload_response.status_code != 200:
            raise Exception(f"AssemblyAI upload error: {upload_response.text}")

        upload_url = upload_response.json()["upload_url"]

        # Start transcription
        transcript_request = {"audio_url": upload_url}
        if language:
            transcript_request["language_code"] = language[:2]

        transcript_response = await client.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={"Authorization": api_key},
            json=transcript_request,
            timeout=60.0,
        )

        if transcript_response.status_code != 200:
            raise Exception(f"AssemblyAI transcript error: {transcript_response.text}")

        transcript_id = transcript_response.json()["id"]

        # Poll for result
        while True:
            poll_response = await client.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers={"Authorization": api_key},
                timeout=10.0,
            )
            poll_data = poll_response.json()

            if poll_data["status"] == "completed":
                return poll_data.get("text", "")
            elif poll_data["status"] == "error":
                raise Exception(f"AssemblyAI error: {poll_data.get('error')}")

            import asyncio
            await asyncio.sleep(1)


async def _transcribe_google(
    audio_bytes: bytes,
    format_type: str,
    language: str | None,
    api_key: str | None,
) -> str:
    """Transcribe using Google Cloud Speech-to-Text."""
    import os

    try:
        from google.cloud import speech
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="google-cloud-speech not installed",
        )

    client = speech.SpeechClient()

    # Determine encoding
    if "webm" in format_type:
        encoding = speech.RecognitionConfig.AudioEncoding.WEBM_OPUS
    else:
        encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16

    config = speech.RecognitionConfig(
        encoding=encoding,
        sample_rate_hertz=16000,
        language_code=language or "en-US",
    )

    audio = speech.RecognitionAudio(content=audio_bytes)

    response = client.recognize(config=config, audio=audio)

    transcripts = []
    for result in response.results:
        transcripts.append(result.alternatives[0].transcript)

    return " ".join(transcripts)


async def _transcribe_azure(
    audio_bytes: bytes,
    format_type: str,
    language: str | None,
    api_key: str | None,
) -> str:
    """Transcribe using Azure Speech Services."""
    import os

    api_key = api_key or os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION", "eastus")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azure Speech API key not configured",
        )

    try:
        import azure.cognitiveservices.speech as speechsdk
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="azure-cognitiveservices-speech not installed",
        )

    speech_config = speechsdk.SpeechConfig(subscription=api_key, region=region)
    if language:
        speech_config.speech_recognition_language = language

    # Create audio stream from bytes
    import io
    audio_stream = speechsdk.AudioDataStream(audio_bytes)

    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=speechsdk.audio.AudioConfig(stream=audio_stream),
    )

    result = speech_recognizer.recognize_once()

    if result.reason == speechsdk.ResultReason.RecognizedSpeech:
        return result.text
    else:
        return ""


async def _synthesize_elevenlabs(
    text: str,
    voice_id: str,
    speaking_rate: float,
    api_key: str | None,
) -> tuple[bytes, str]:
    """Synthesize using ElevenLabs."""
    import httpx
    import os

    api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="ElevenLabs API key not configured",
        )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
            timeout=60.0,
        )

        if response.status_code != 200:
            raise Exception(f"ElevenLabs API error: {response.text}")

        return response.content, "mp3"


async def _synthesize_openai(
    text: str,
    voice_id: str,
    speaking_rate: float,
    api_key: str | None,
) -> tuple[bytes, str]:
    """Synthesize using OpenAI TTS."""
    import httpx
    import os

    api_key = api_key or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenAI API key not configured",
        )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "tts-1",
                "input": text,
                "voice": voice_id or "alloy",
                "speed": speaking_rate,
            },
            timeout=60.0,
        )

        if response.status_code != 200:
            raise Exception(f"OpenAI TTS API error: {response.text}")

        return response.content, "mp3"


async def _synthesize_azure(
    text: str,
    voice_id: str,
    speaking_rate: float,
    language: str,
    api_key: str | None,
) -> tuple[bytes, str]:
    """Synthesize using Azure Speech Services."""
    import httpx
    import os

    api_key = api_key or os.getenv("AZURE_SPEECH_KEY")
    region = os.getenv("AZURE_SPEECH_REGION", "eastus")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Azure Speech API key not configured",
        )

    voice_name = voice_id or f"{language}-JennyNeural"

    ssml = f"""
    <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='{language}'>
        <voice name='{voice_name}'>
            <prosody rate='{int((speaking_rate - 1) * 100)}%'>
                {text}
            </prosody>
        </voice>
    </speak>
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
            headers={
                "Ocp-Apim-Subscription-Key": api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
            },
            content=ssml,
            timeout=60.0,
        )

        if response.status_code != 200:
            raise Exception(f"Azure TTS API error: {response.text}")

        return response.content, "mp3"


async def _synthesize_google(
    text: str,
    voice_id: str,
    speaking_rate: float,
    language: str,
    api_key: str | None,
) -> tuple[bytes, str]:
    """Synthesize using Google Cloud Text-to-Speech."""
    try:
        from google.cloud import texttospeech
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="google-cloud-texttospeech not installed",
        )

    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code=language[:2] + "-" + language[3:5].upper() if len(language) > 2 else "en-US",
        name=voice_id or "en-US-Neural2-C",
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    return response.audio_content, "mp3"
