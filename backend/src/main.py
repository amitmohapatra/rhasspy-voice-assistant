"""FastAPI application entry point with comprehensive Swagger documentation."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from src.api.routes import api_router
from src.core.config import settings
from src.core.exceptions import (
    AIError,
    NotFoundError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
)


# OpenAPI Tags for Swagger UI organization
OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": "User registration, login, and token management. All protected endpoints require a valid JWT token in the Authorization header.",
    },
    {
        "name": "Users",
        "description": "User profile management and settings.",
    },
    {
        "name": "Assistants",
        "description": "AI assistant configuration and management. Create assistants with custom prompts, models, and capabilities.",
    },
    {
        "name": "Conversations",
        "description": "Conversation management. Each conversation maintains context and history for continued interactions.",
    },
    {
        "name": "Chat",
        "description": "Send messages to assistants and receive responses. Supports both streaming (SSE) and non-streaming responses.",
    },
    {
        "name": "Voice",
        "description": "Speech-to-Text (STT) and Text-to-Speech (TTS) endpoints for voice interactions.",
    },
    {
        "name": "Real-time",
        "description": "WebSocket endpoint for real-time voice conversations with the assistant.",
    },
    {
        "name": "Knowledge Bases",
        "description": "Document storage and semantic search for RAG (Retrieval-Augmented Generation).",
    },
    {
        "name": "Documents",
        "description": "Document upload and management within knowledge bases.",
    },
    {
        "name": "Tools",
        "description": "Custom tool configuration for extending assistant capabilities.",
    },
    {
        "name": "Analytics",
        "description": "Usage analytics and reporting.",
    },
    {
        "name": "Health",
        "description": "Health check and readiness endpoints for monitoring.",
    },
    {
        "name": "Document Processing",
        "description": "Document extraction and processing for multimodal RAG. Configure ML models for OCR, vision, charts.",
    },
]


def custom_openapi(app: FastAPI) -> dict:
    """Generate custom OpenAPI schema with enhanced documentation."""
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.project_name,
        version=settings.version,
        description="""
# Rhasspy Voice Assistant API

Enterprise AI Voice Assistant Platform with multi-provider LLM support, 3D avatars, and comprehensive voice capabilities.

## Features

- **Multi-Provider LLM Support**: OpenAI, Anthropic, Google, Azure, and more
- **Voice Capabilities**: Speech-to-Text (STT) and Text-to-Speech (TTS) with multiple providers
- **3D Avatar Support**: Animated avatars with lip-sync and emotion detection
- **RAG Integration**: Knowledge base with semantic search for context-aware responses
- **Streaming Responses**: Real-time streaming via Server-Sent Events (SSE)
- **WebSocket Real-time**: Live voice conversations with the assistant
- **Tool Calling**: Extensible tool system for custom functionality

## Authentication

Most endpoints require authentication using JWT Bearer tokens. To authenticate:

1. Register a new user via `POST /api/v1/auth/register`
2. Login to get tokens via `POST /api/v1/auth/login`
3. Include the access token in the `Authorization` header: `Bearer <token>`

## Rate Limits

- Free tier: 100 requests/minute
- Professional tier: 1000 requests/minute
- Enterprise tier: Unlimited

## Error Handling

All errors follow a consistent format:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {}
}
```

## Streaming

For streaming endpoints (chat), responses are sent as Server-Sent Events (SSE).
Each event has the format:
```
data: {"type": "text_delta", "data": "Hello"}

data: {"type": "done", "data": null}
```
        """,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token obtained from /api/v1/auth/login",
        }
    }

    # Add global security requirement
    openapi_schema["security"] = [{"BearerAuth": []}]

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Local development server",
        },
        {
            "url": "https://api.example.com",
            "description": "Production server",
        },
    ]

    # Add contact and license info
    openapi_schema["info"]["contact"] = {
        "name": "API Support",
        "email": "support@example.com",
    }
    openapi_schema["info"]["license"] = {
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.
    """
    # Startup
    print(f"Starting {settings.project_name} v{settings.version}")

    # Initialize database connection pool
    from src.db.session import engine
    print("Database connection pool initialized")

    # Seed model registry (providers + models) - idempotent
    try:
        from src.db.session import AsyncSessionLocal
        from src.services.model_registry import ModelRegistryService

        async with AsyncSessionLocal() as session:
            try:
                service = ModelRegistryService(session)
                result = await service.initialize_defaults()
                await session.commit()
                p_count = result["providers_created"]
                m_count = result["models_created"]
                if p_count > 0 or m_count > 0:
                    print(f"Model registry seeded: {p_count} providers, {m_count} models")
                else:
                    print("Model registry: all providers and models exist")
            except Exception as e:
                await session.rollback()
                print(f"Model registry seed skipped (DB may not be ready): {e}")
    except Exception as e:
        print(f"Model registry seed skipped: {e}")

    # Seed built-in tools (idempotent - skips existing, runs AFTER model registry so providers exist)
    try:
        from src.db.session import AsyncSessionLocal
        from src.db.seeds.builtin_tools_seed import seed_builtin_tools

        async with AsyncSessionLocal() as session:
            try:
                result = await seed_builtin_tools(session)
                created_count = result["summary"]["total_created"]
                skipped_count = result["summary"]["total_skipped"]
                if created_count > 0:
                    print(f"Built-in tools seeded: {created_count} created, {skipped_count} skipped")
                else:
                    print(f"Built-in tools: {skipped_count} already exist")
            except Exception as e:
                await session.rollback()
                print(f"Built-in tools seed skipped (DB may not be ready): {e}")
    except Exception as e:
        print(f"Built-in tools seed skipped: {e}")

    # Seed capability definitions + vendor mappings (idempotent)
    try:
        from src.db.session import AsyncSessionLocal
        from src.db.seeds.capability_seed import seed_capabilities

        async with AsyncSessionLocal() as session:
            try:
                result = await seed_capabilities(session)
                defs = result["definitions"]
                maps = result["vendor_mappings"]
                if defs["total_created"] > 0 or maps["total_created"] > 0:
                    print(f"Capabilities seeded: {defs['total_created']} definitions, {maps['total_created']} vendor mappings")
                else:
                    print(f"Capabilities: {defs['total_skipped']} definitions, {maps['total_skipped']} vendor mappings already exist")
            except Exception as e:
                await session.rollback()
                print(f"Capabilities seed skipped (DB may not be ready): {e}")
    except Exception as e:
        print(f"Capabilities seed skipped: {e}")

    # Seed model-tool support mappings (idempotent, runs AFTER tools + capabilities)
    try:
        from src.db.session import AsyncSessionLocal
        from src.db.seeds.model_tool_support_seed import seed_model_tool_support

        async with AsyncSessionLocal() as session:
            try:
                result = await seed_model_tool_support(session)
                await session.commit()
                created = result["created"]
                skipped = result["skipped"]
                migrated = result["overrides_migrated"]
                if created > 0:
                    print(f"Model-tool support seeded: {created} created, {skipped} skipped, {migrated} overrides migrated")
                else:
                    print(f"Model-tool support: {skipped} mappings already exist")
            except Exception as e:
                await session.rollback()
                print(f"Model-tool support seed skipped (DB may not be ready): {e}")
    except Exception as e:
        print(f"Model-tool support seed skipped: {e}")

    # Initialize Redis if configured
    if settings.redis_url:
        try:
            import redis.asyncio as redis
            app.state.redis = redis.from_url(settings.redis_url)
            await app.state.redis.ping()
            print("Redis connection established")
        except Exception as e:
            print(f"Redis connection failed: {e}")
            app.state.redis = None
    else:
        app.state.redis = None

    yield

    # Shutdown
    print("Shutting down application...")

    # Close HTTP connection pools
    try:
        from src.core.http_client import close_http_clients
        await close_http_clients()
        print("HTTP connection pools closed")
    except Exception as e:
        print(f"Error closing HTTP clients: {e}")

    # Close Redis connection
    if hasattr(app.state, "redis") and app.state.redis:
        await app.state.redis.close()
        print("Redis connection closed")

    # Close database connections
    await engine.dispose()
    print("Database connections closed")


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="Enterprise AI Voice Assistant Platform",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
        swagger_ui_parameters={
            "deepLinking": True,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
            "showExtensions": True,
            "showCommonExtensions": True,
            "tryItOutEnabled": True,
        },
    )

    # Set custom OpenAPI schema generator
    app.openapi = lambda: custom_openapi(app)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Specific exception handlers (registered before the base AIError handler
    # so FastAPI matches them first for more specific error types)
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc.message)},
        )

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc.message)},
        )

    @app.exception_handler(AuthenticationError)
    async def authentication_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc.message)},
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=403,
            content={"detail": str(exc.message)},
        )

    # Global exception handler for AIError (catch-all for other AIError subclasses)
    @app.exception_handler(AIError)
    async def ai_error_handler(request: Request, exc: AIError) -> JSONResponse:
        """Handle custom AI errors."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    # Global exception handler for unexpected errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Handle unexpected errors."""
        if settings.debug:
            import traceback
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "INTERNAL_ERROR",
                    "message": str(exc),
                    "details": {"traceback": traceback.format_exc()},
                },
            )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {},
            },
        )

    # Health check endpoint
    @app.get(
        "/health",
        tags=["Health"],
        summary="Health check",
        description="Check the health status of the API and its dependencies (database, Redis).",
        response_description="Health status of all components",
    )
    async def health_check() -> dict:
        """Health check endpoint."""
        health = {
            "status": "healthy",
            "version": settings.version,
            "components": {},
        }

        # Check database
        try:
            from src.db.session import AsyncSessionLocal
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            health["components"]["database"] = {"status": "healthy"}
        except Exception as e:
            health["components"]["database"] = {"status": "unhealthy", "error": str(e)}
            health["status"] = "degraded"

        # Check Redis
        if hasattr(app.state, "redis") and app.state.redis:
            try:
                await app.state.redis.ping()
                health["components"]["redis"] = {"status": "healthy"}
            except Exception as e:
                health["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"
        else:
            health["components"]["redis"] = {"status": "not_configured"}

        return health

    # Ready check for Kubernetes
    @app.get(
        "/ready",
        tags=["Health"],
        summary="Readiness check",
        description="Check if the API is ready to receive traffic. Used by Kubernetes readiness probes.",
        response_description="Readiness status",
    )
    async def ready_check() -> dict:
        """Readiness check endpoint."""
        return {"ready": True}

    # Live check for Kubernetes
    @app.get(
        "/live",
        tags=["Health"],
        summary="Liveness check",
        description="Check if the API is alive. Used by Kubernetes liveness probes.",
        response_description="Liveness status",
    )
    async def live_check() -> dict:
        """Liveness check endpoint."""
        return {"alive": True}

    # Include API routes
    app.include_router(api_router, prefix="/api")

    return app


# Create the application instance
app = create_application()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info",
    )
