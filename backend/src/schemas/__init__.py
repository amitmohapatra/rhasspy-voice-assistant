"""Pydantic schemas for request/response validation.

All schemas include comprehensive Swagger documentation with:
- Descriptions for all fields
- Examples for all fields
- Enum types for dropdown support in Swagger UI
- Complete response examples
"""

# Enums - All enums appear as dropdowns in Swagger UI
from src.schemas.enums import (
    LLMProvider,
    OpenAIModel,
    AnthropicModel,
    GoogleModel,
    STTProvider,
    TTSProvider,
    AudioFormat,
    MessageRole,
    ContentType,
    ConversationStatus,
    KnowledgeBaseStatus,
    DocumentStatus,
    FileType,
    ToolType,
    ToolExecutionStatus,
    StreamEventType,
    Emotion,
    Language,
    OpenAIVoice,
    ResponseStatus,
    ResponseItemType,
    ItemDirection,
)

# Error responses
from src.schemas.errors import (
    ErrorCode,
    ErrorDetail,
    ErrorResponse,
    ValidationErrorResponse,
    AuthenticationErrorResponse,
    AuthorizationErrorResponse,
    NotFoundErrorResponse,
    RateLimitErrorResponse,
    InternalErrorResponse,
    ProviderErrorResponse,
    ERROR_RESPONSES,
)

# User schemas
from src.schemas.user import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    PasswordChangeRequest,
)

# Assistant schemas
from src.schemas.assistant import (
    AssistantCreate,
    AssistantUpdate,
    AssistantResponse,
    AssistantListResponse,
)

# Conversation schemas
from src.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
)

# Knowledge Base schemas
from src.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    KnowledgeBaseSummary,
    DocumentUpload,
    DocumentResponse,
    SearchRequest,
    SearchResult,
    SearchResponse,
)

# Integration schemas
from src.schemas.integration import (
    IntegrationCatalogResponse,
    IntegrationCatalogCreate,
    UserIntegrationResponse,
    UserIntegrationCreate,
    UserIntegrationUpdate,
    IntegrationTestRequest,
    IntegrationTestResponse,
)

# Tool schemas
from src.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolListResponse,
    ToolExecutionRequest,
    ToolExecutionResponse,
)

# Response API schemas
from src.schemas.response import (
    InputItem,
    CreateResponseRequest,
    ResponseItemSchema,
    ResponseSchema,
)

# Voice chat schemas (kept from old chat module)
from src.schemas.chat import (
    VoiceChatRequest,
    VoiceChatResponse,
)

# Voice schemas
from src.schemas.voice import (
    TranscribeRequest,
    TranscribeResponse,
    SynthesizeRequest,
    SynthesizeResponse,
    VoiceInfo,
    VoiceListResponse,
    RealtimeSessionRequest,
    RealtimeEvent,
)

__all__ = [
    # Enums
    "LLMProvider",
    "OpenAIModel",
    "AnthropicModel",
    "GoogleModel",
    "STTProvider",
    "TTSProvider",
    "AudioFormat",
    "MessageRole",
    "ContentType",
    "ConversationStatus",
    "KnowledgeBaseStatus",
    "DocumentStatus",
    "FileType",
    "ToolType",
    "ToolExecutionStatus",
    "StreamEventType",
    "Emotion",
    "Language",
    "OpenAIVoice",
    "ResponseStatus",
    "ResponseItemType",
    "ItemDirection",
    # Error responses
    "ErrorCode",
    "ErrorDetail",
    "ErrorResponse",
    "ValidationErrorResponse",
    "AuthenticationErrorResponse",
    "AuthorizationErrorResponse",
    "NotFoundErrorResponse",
    "RateLimitErrorResponse",
    "InternalErrorResponse",
    "ProviderErrorResponse",
    "ERROR_RESPONSES",
    # User
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "TokenResponse",
    "RefreshTokenRequest",
    "PasswordChangeRequest",
    # Assistant
    "AssistantCreate",
    "AssistantUpdate",
    "AssistantResponse",
    "AssistantListResponse",
    # Conversation
    "ConversationCreate",
    "ConversationUpdate",
    "ConversationResponse",
    "ConversationListResponse",
    # Knowledge Base
    "KnowledgeBaseCreate",
    "KnowledgeBaseUpdate",
    "KnowledgeBaseResponse",
    "DocumentUpload",
    "DocumentResponse",
    "SearchRequest",
    "SearchResult",
    "SearchResponse",
    # Integration
    "IntegrationCatalogResponse",
    "IntegrationCatalogCreate",
    "UserIntegrationResponse",
    "UserIntegrationCreate",
    "UserIntegrationUpdate",
    "IntegrationTestRequest",
    "IntegrationTestResponse",
    # Tool
    "ToolCreate",
    "ToolUpdate",
    "ToolResponse",
    "ToolListResponse",
    "ToolExecutionRequest",
    "ToolExecutionResponse",
    # Response API
    "InputItem",
    "CreateResponseRequest",
    "ResponseItemSchema",
    "ResponseSchema",
    # Voice Chat
    "VoiceChatRequest",
    "VoiceChatResponse",
    # Voice
    "TranscribeRequest",
    "TranscribeResponse",
    "SynthesizeRequest",
    "SynthesizeResponse",
    "VoiceInfo",
    "VoiceListResponse",
    "RealtimeSessionRequest",
    "RealtimeEvent",
]
