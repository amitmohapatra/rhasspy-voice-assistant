"""API routes."""

from fastapi import APIRouter

from src.api.routes.v1 import (
    api_keys,
    auth,
    assistants,
    assistant_tools,
    knowledge_bases,
    chat,
    responses,
    tools,
    builtin_tools,
    capabilities,
    files,
    providers,
    projects,
    avatars,
    realtime,
    voice,
    voice_presets,
    models,
    rag_pipelines,
    integrations,
    model_tool_support,
    document_viewer,
    llm_keys,
    document_chat,
)

api_router = APIRouter()

# V1 API routes - Core
api_router.include_router(api_keys.router, prefix="/v1/api-keys", tags=["api-keys"])
api_router.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
api_router.include_router(assistants.router, prefix="/v1/assistants", tags=["assistants"])
api_router.include_router(
    knowledge_bases.router, prefix="/v1/knowledge-bases", tags=["knowledge-bases"]
)
api_router.include_router(chat.router, prefix="/v1/chat", tags=["chat"])
api_router.include_router(responses.router, prefix="/v1/responses", tags=["responses"])
api_router.include_router(tools.router, prefix="/v1/tools", tags=["tools"])
api_router.include_router(assistant_tools.router, prefix="/v1", tags=["assistant-tools"])
api_router.include_router(builtin_tools.router, prefix="/v1", tags=["builtin-tools"])
api_router.include_router(capabilities.router, prefix="/v1", tags=["capabilities"])
api_router.include_router(files.router, prefix="/v1/files", tags=["files"])
api_router.include_router(providers.router, prefix="/v1", tags=["providers"])
api_router.include_router(projects.router, prefix="/v1", tags=["projects"])

# V1 API routes - Enterprise
api_router.include_router(avatars.router, prefix="/v1/avatars", tags=["avatars"])

# V1 API routes - Voice & Real-time
api_router.include_router(realtime.router, prefix="/v1/realtime", tags=["realtime"])
api_router.include_router(voice.router, prefix="/v1/voice", tags=["voice"])
api_router.include_router(voice_presets.router, prefix="/v1", tags=["voice-presets"])

# V1 API routes - AI Model Registry
api_router.include_router(models.router, prefix="/v1/ai", tags=["ai-models"])

# V1 API routes - RAG Pipeline Builder
api_router.include_router(
    rag_pipelines.router, prefix="/v1/rag-pipelines", tags=["rag-pipelines"]
)

# V1 API routes - Integrations (Slack, Teams, Outlook, etc.)
api_router.include_router(
    integrations.router, prefix="/v1/integrations", tags=["integrations"]
)

# V1 API routes - Model-Tool Support
api_router.include_router(
    model_tool_support.router, prefix="/v1", tags=["model-tool-support"]
)

# V1 API routes - Document Viewer (Agentic Docs)
api_router.include_router(
    document_viewer.router, prefix="/v1/documents", tags=["document-viewer"]
)

# V1 API routes - LLM Vendor Keys
api_router.include_router(
    llm_keys.router, prefix="/v1/settings/llm-keys", tags=["llm-keys"]
)

# V1 API routes - Document Chat
api_router.include_router(
    document_chat.router, prefix="/v1/documents", tags=["document-chat"]
)
