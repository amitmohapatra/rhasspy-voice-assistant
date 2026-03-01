"""Database models."""

from src.models.user import User
from src.models.project import Project
from src.models.secret import Secret, PROVIDER_SECRETS, TOOL_SECRETS
from src.models.assistant import Assistant
from src.models.conversation import Conversation
from src.models.response import Response, ResponseItem
from src.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument, Document, DocumentChunk
from src.models.tool import Tool, ToolExecution
from src.models.builtin_tool import BuiltinTool, BuiltinToolModelOverride, ToolCategory
from src.models.api_key import APIKey
from src.models.usage import UsageLog
from src.models.avatar import Avatar, SYSTEM_AVATARS
from src.models.ai_model import (
    ProviderStatus,
    ModelStatus,
    ModelCategory,
    ModelTier,
    AIProvider,
    AIModel,
    ModelUsageStats,
    DEFAULT_PROVIDERS,
    SAMPLE_MODELS,
)
from src.models.capability import (
    ModelCapability,
    CapabilityDefinition,
    ToolCapabilityRequirement,
    VendorCapabilityMapping,
    CapabilityType,
)
from src.models.integration import IntegrationCatalog, UserIntegration
from src.models.model_tool_support import ModelToolSupport
from src.models.voice_preset import VoicePreset

__all__ = [
    "User",
    "Project",
    "Secret",
    "PROVIDER_SECRETS",
    "TOOL_SECRETS",
    "Assistant",
    "Conversation",
    "Response",
    "ResponseItem",
    "KnowledgeBase",
    "KnowledgeBaseDocument",
    "Document",
    "DocumentChunk",
    "Tool",
    "ToolExecution",
    "BuiltinTool",
    "BuiltinToolModelOverride",
    "ToolCategory",
    "APIKey",
    "UsageLog",
    # Avatar
    "Avatar",
    "SYSTEM_AVATARS",
    # AI Model Registry
    "ProviderStatus",
    "ModelStatus",
    "ModelCategory",
    "ModelTier",
    "AIProvider",
    "AIModel",
    "ModelUsageStats",
    "DEFAULT_PROVIDERS",
    "SAMPLE_MODELS",
    # Integrations
    "IntegrationCatalog",
    "UserIntegration",
    # Model-Tool Support
    "ModelToolSupport",
    # Voice Presets
    "VoicePreset",
]
