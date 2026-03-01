"""Provider management API routes."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel

from src.providers import ProviderRegistry, ProviderFactory, ProviderType, ProviderConfig


router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    """Provider information."""
    name: str
    display_name: str
    description: str
    requires_api_key: bool


class ProviderModel(BaseModel):
    """Provider model information."""
    id: str
    name: str
    description: str | None = None
    dimensions: int | None = None  # For embeddings


class ProviderSettings(BaseModel):
    """Provider settings schema."""
    schema_json: dict[str, Any]


class TestConnectionRequest(BaseModel):
    """Request to test provider connection."""
    provider_type: str
    provider_name: str
    api_key: str | None = None
    model: str | None = None
    settings: dict[str, Any] = {}


class TestConnectionResponse(BaseModel):
    """Response from connection test."""
    success: bool
    message: str
    details: dict[str, Any] | None = None


class TTSRequest(BaseModel):
    """Text-to-speech request."""
    text: str
    provider_name: str
    api_key: str | None = None
    model: str | None = None
    voice: str | None = None
    settings: dict[str, Any] = {}


class EmbeddingsRequest(BaseModel):
    """Embeddings request."""
    texts: list[str]
    provider_name: str
    api_key: str | None = None
    model: str | None = None
    settings: dict[str, Any] = {}


class EmbeddingsResponse(BaseModel):
    """Embeddings response."""
    embeddings: list[list[float]]
    model: str
    dimensions: int


# ========== List Providers ==========

@router.get("/types")
async def list_provider_types() -> list[str]:
    """List all provider types."""
    return [pt.value for pt in ProviderType]


@router.get("/{provider_type}")
async def list_providers(provider_type: str) -> list[ProviderInfo]:
    """List all providers for a given type."""
    try:
        pt = ProviderType(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    providers = ProviderRegistry.list_providers(pt)
    return [
        ProviderInfo(
            name=p.name,
            display_name=p.display_name,
            description=p.description,
            requires_api_key=p.requires_api_key,
        )
        for p in providers
    ]


@router.get("/{provider_type}/{provider_name}/models")
async def list_provider_models(
    provider_type: str,
    provider_name: str,
) -> list[ProviderModel]:
    """List available models for a provider."""
    try:
        pt = ProviderType(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    provider_class = ProviderRegistry.get(pt, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

    models = provider_class.get_available_models()
    return [ProviderModel(**model) for model in models]


@router.get("/{provider_type}/{provider_name}/settings")
async def get_provider_settings(
    provider_type: str,
    provider_name: str,
) -> ProviderSettings:
    """Get settings schema for a provider."""
    try:
        pt = ProviderType(provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {provider_type}")

    provider_class = ProviderRegistry.get(pt, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"Provider not found: {provider_name}")

    schema = provider_class.get_settings_schema()
    return ProviderSettings(schema_json=schema)


# ========== Test Connection ==========

@router.post("/test-connection")
async def test_connection(request: TestConnectionRequest) -> TestConnectionResponse:
    """Test connection to a provider."""
    try:
        pt = ProviderType(request.provider_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider type: {request.provider_type}")

    provider_class = ProviderRegistry.get(pt, request.provider_name)
    if not provider_class:
        raise HTTPException(
            status_code=404,
            detail=f"Provider not found: {request.provider_name}"
        )

    # Check if API key is required
    if provider_class.requires_api_key and not request.api_key:
        return TestConnectionResponse(
            success=False,
            message="API key is required for this provider",
        )

    try:
        config = ProviderConfig(
            provider_type=pt,
            provider_name=request.provider_name,
            api_key=request.api_key,
            model=request.model,
            settings=request.settings,
        )
        provider = ProviderFactory.create(config)

        # Test based on provider type
        if pt == ProviderType.STT:
            # STT requires audio, just verify initialization
            return TestConnectionResponse(
                success=True,
                message="Provider initialized successfully",
                details={"models": [m["id"] for m in provider.get_available_models()]},
            )

        elif pt == ProviderType.TTS:
            # Get available voices
            voices = await provider.get_voices()
            return TestConnectionResponse(
                success=True,
                message=f"Connected successfully. Found {len(voices)} voices.",
                details={"voice_count": len(voices)},
            )

        elif pt == ProviderType.EMBEDDINGS:
            # Try a simple embedding
            result = await provider.embed(["test"])
            return TestConnectionResponse(
                success=True,
                message=f"Connected successfully. Dimensions: {result.dimensions}",
                details={"dimensions": result.dimensions, "model": result.model},
            )

        elif pt == ProviderType.VECTORSTORE:
            # Try listing collections
            collections = await provider.list_collections()
            return TestConnectionResponse(
                success=True,
                message=f"Connected successfully. Found {len(collections)} collections.",
                details={"collections": collections},
            )

        else:
            return TestConnectionResponse(
                success=True,
                message="Provider initialized successfully",
            )

    except Exception as e:
        return TestConnectionResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )


# ========== STT Operations ==========

@router.post("/stt/transcribe")
async def transcribe_audio(
    audio: UploadFile = File(...),
    provider_name: str = "openai_whisper",
    api_key: str | None = None,
    model: str | None = None,
    language: str | None = None,
) -> dict[str, Any]:
    """Transcribe audio using STT provider."""
    provider_class = ProviderRegistry.get(ProviderType.STT, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"STT provider not found: {provider_name}")

    if provider_class.requires_api_key and not api_key:
        raise HTTPException(status_code=400, detail="API key required")

    try:
        config = ProviderConfig(
            provider_type=ProviderType.STT,
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            settings={},
        )
        provider = ProviderFactory.create(config)

        audio_data = await audio.read()
        kwargs = {}
        if language:
            kwargs["language"] = language

        result = await provider.transcribe(audio_data, **kwargs)

        return {
            "text": result.text,
            "language": result.language,
            "duration": result.duration,
            "segments": [seg.model_dump() for seg in result.segments] if result.segments else None,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== TTS Operations ==========

@router.post("/tts/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Synthesize speech using TTS provider."""
    from fastapi.responses import StreamingResponse

    provider_class = ProviderRegistry.get(ProviderType.TTS, request.provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"TTS provider not found: {request.provider_name}")

    if provider_class.requires_api_key and not request.api_key:
        raise HTTPException(status_code=400, detail="API key required")

    try:
        config = ProviderConfig(
            provider_type=ProviderType.TTS,
            provider_name=request.provider_name,
            api_key=request.api_key,
            model=request.model,
            settings=request.settings,
        )
        provider = ProviderFactory.create(config)

        kwargs = {}
        if request.voice:
            kwargs["voice"] = request.voice

        result = await provider.synthesize(request.text, **kwargs)

        return StreamingResponse(
            iter([result.audio_data]),
            media_type=result.content_type,
            headers={
                "Content-Disposition": f"attachment; filename=speech.{result.format}",
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tts/{provider_name}/voices")
async def list_voices(
    provider_name: str,
    api_key: str | None = None,
) -> list[dict[str, Any]]:
    """List available voices for a TTS provider."""
    provider_class = ProviderRegistry.get(ProviderType.TTS, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"TTS provider not found: {provider_name}")

    try:
        config = ProviderConfig(
            provider_type=ProviderType.TTS,
            provider_name=provider_name,
            api_key=api_key,
            settings={},
        )
        provider = ProviderFactory.create(config)
        voices = await provider.get_voices()
        return [v.model_dump() for v in voices]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== Embeddings Operations ==========

@router.post("/embeddings/embed")
async def generate_embeddings(request: EmbeddingsRequest) -> EmbeddingsResponse:
    """Generate embeddings using embeddings provider."""
    provider_class = ProviderRegistry.get(ProviderType.EMBEDDINGS, request.provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"Embeddings provider not found: {request.provider_name}")

    if provider_class.requires_api_key and not request.api_key:
        raise HTTPException(status_code=400, detail="API key required")

    try:
        config = ProviderConfig(
            provider_type=ProviderType.EMBEDDINGS,
            provider_name=request.provider_name,
            api_key=request.api_key,
            model=request.model,
            settings=request.settings,
        )
        provider = ProviderFactory.create(config)
        result = await provider.embed(request.texts, **request.settings)

        return EmbeddingsResponse(
            embeddings=result.embeddings,
            model=result.model,
            dimensions=result.dimensions,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/{provider_name}/dimensions")
async def get_embedding_dimensions(
    provider_name: str,
    model: str | None = None,
) -> dict[str, int]:
    """Get embedding dimensions for a model."""
    provider_class = ProviderRegistry.get(ProviderType.EMBEDDINGS, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"Embeddings provider not found: {provider_name}")

    dimensions = provider_class.get_dimensions(model or "")
    return {"dimensions": dimensions}


# ========== Vector Store Operations ==========

@router.get("/vectorstore/{provider_name}/collections")
async def list_collections(
    provider_name: str,
    api_key: str | None = None,
    url: str | None = None,
) -> list[str]:
    """List collections in a vector store."""
    provider_class = ProviderRegistry.get(ProviderType.VECTORSTORE, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"Vector store not found: {provider_name}")

    try:
        settings = {}
        if url:
            settings["url"] = url

        config = ProviderConfig(
            provider_type=ProviderType.VECTORSTORE,
            provider_name=provider_name,
            api_key=api_key,
            settings=settings,
        )
        provider = ProviderFactory.create(config)
        return await provider.list_collections()

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/vectorstore/{provider_name}/collections/{collection_name}/stats")
async def get_collection_stats(
    provider_name: str,
    collection_name: str,
    api_key: str | None = None,
    url: str | None = None,
) -> dict[str, Any]:
    """Get statistics for a collection."""
    provider_class = ProviderRegistry.get(ProviderType.VECTORSTORE, provider_name)
    if not provider_class:
        raise HTTPException(status_code=404, detail=f"Vector store not found: {provider_name}")

    try:
        settings = {}
        if url:
            settings["url"] = url

        config = ProviderConfig(
            provider_type=ProviderType.VECTORSTORE,
            provider_name=provider_name,
            api_key=api_key,
            settings=settings,
        )
        provider = ProviderFactory.create(config)
        return await provider.get_collection_stats(collection_name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
