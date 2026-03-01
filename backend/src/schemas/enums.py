"""Enumeration types for API schemas.

All enums appear as dropdowns in Swagger UI.
"""

from enum import Enum


class LLMProvider(str, Enum):
    """LLM provider options."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    BEDROCK = "bedrock"
    COHERE = "cohere"
    LOCAL = "local"


class OpenAIModel(str, Enum):
    """OpenAI model options."""
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4 = "gpt-4"
    GPT_35_TURBO = "gpt-3.5-turbo"
    O1_PREVIEW = "o1-preview"
    O1_MINI = "o1-mini"


class AnthropicModel(str, Enum):
    """Anthropic model options."""
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_5_HAIKU = "claude-3-5-haiku-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    CLAUDE_3_HAIKU = "claude-3-haiku-20240307"


class GoogleModel(str, Enum):
    """Google model options."""
    GEMINI_2_FLASH = "gemini-2.0-flash-exp"
    GEMINI_15_PRO = "gemini-1.5-pro"
    GEMINI_15_FLASH = "gemini-1.5-flash"
    GEMINI_PRO = "gemini-pro"


class STTProvider(str, Enum):
    """Speech-to-text provider options."""
    OPENAI = "openai"
    DEEPGRAM = "deepgram"
    ASSEMBLY = "assembly"
    GOOGLE = "google"
    AZURE = "azure"


class TTSProvider(str, Enum):
    """Text-to-speech provider options."""
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    AZURE = "azure"
    GOOGLE = "google"


class AudioFormat(str, Enum):
    """Audio format options."""
    WEBM = "webm"
    WAV = "wav"
    MP3 = "mp3"
    OGG = "ogg"
    FLAC = "flac"


class MessageRole(str, Enum):
    """Message role in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ContentType(str, Enum):
    """Content type for messages."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    FILE = "file"


class ConversationStatus(str, Enum):
    """Conversation status."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class KnowledgeBaseStatus(str, Enum):
    """Knowledge base processing status."""
    ACTIVE = "active"
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class DocumentStatus(str, Enum):
    """Document processing status."""
    UPLOADED = "uploaded"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class FileType(str, Enum):
    """Supported file types for documents."""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    PPTX = "pptx"
    XLSX = "xlsx"
    TXT = "txt"
    MD = "md"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    EPUB = "epub"
    PNG = "png"
    JPG = "jpg"
    JPEG = "jpeg"
    TIFF = "tiff"
    TIF = "tif"
    TEX = "tex"
    RTF = "rtf"


class ElementType(str, Enum):
    """Document element types from Docling parsing."""
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    EQUATION = "equation"
    CODE = "code"
    HEADING = "heading"


class ToolType(str, Enum):
    """Tool type options."""
    FUNCTION = "function"
    API = "api"
    MCP = "mcp"
    BUILTIN = "builtin"


class ToolExecutionStatus(str, Enum):
    """Tool execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    TIMEOUT = "timeout"


class StreamEventType(str, Enum):
    """Stream event types for SSE."""
    CONVERSATION_ID = "conversation_id"
    MESSAGE_START = "message_start"
    TEXT_DELTA = "text_delta"
    TEXT_DONE = "text_done"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_DELTA = "tool_call_delta"
    TOOL_CALL_DONE = "tool_call_done"
    TOOL_RESULT = "tool_result"
    AUDIO_CHUNK = "audio_chunk"
    EMOTION = "emotion"
    SOURCES = "sources"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"


class Emotion(str, Enum):
    """Avatar emotion states."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    SURPRISED = "surprised"
    THINKING = "thinking"
    CONFUSED = "confused"
    EXCITED = "excited"


class Language(str, Enum):
    """Supported languages."""
    EN_US = "en-US"
    EN_GB = "en-GB"
    ES_ES = "es-ES"
    ES_MX = "es-MX"
    FR_FR = "fr-FR"
    DE_DE = "de-DE"
    IT_IT = "it-IT"
    PT_BR = "pt-BR"
    JA_JP = "ja-JP"
    ZH_CN = "zh-CN"
    KO_KR = "ko-KR"


class OpenAIVoice(str, Enum):
    """OpenAI TTS voice options."""
    ALLOY = "alloy"
    ECHO = "echo"
    FABLE = "fable"
    ONYX = "onyx"
    NOVA = "nova"
    SHIMMER = "shimmer"


class KBType(str, Enum):
    """Knowledge base type."""
    PROVIDER_MANAGED = "provider_managed"  # Provider's assistant infra (OpenAI/Azure file search)
    PLATFORM_MANAGED = "platform_managed"  # Our RAG pipeline (Docling+BGE-M3+Qdrant)


class IntegrationAuthType(str, Enum):
    """Authentication type for integrations."""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    WEBHOOK = "webhook"
    BEARER_TOKEN = "bearer_token"


class IntegrationCategory(str, Enum):
    """Integration category."""
    COMMUNICATION = "communication"  # Slack, Teams, Discord
    PRODUCTIVITY = "productivity"    # Jira, Linear, Notion, Asana
    DEVELOPMENT = "development"      # GitHub, GitLab, Bitbucket
    EMAIL = "email"                  # Outlook, Gmail
    CRM = "crm"                      # Salesforce, HubSpot
    STORAGE = "storage"              # Google Drive, Dropbox, OneDrive
    ANALYTICS = "analytics"          # Datadog, Mixpanel
    CUSTOM = "custom"                # User-built


class ResponseStatus(str, Enum):
    """Response processing status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResponseItemType(str, Enum):
    """Type of response item."""
    MESSAGE = "message"
    FUNCTION_CALL = "function_call"
    FUNCTION_CALL_OUTPUT = "function_call_output"
    RAG_CONTEXT = "rag_context"


class ItemDirection(str, Enum):
    """Direction of a response item."""
    INPUT = "input"
    OUTPUT = "output"
