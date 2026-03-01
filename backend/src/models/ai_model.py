"""AI Model and Provider Registry - Dynamic model management."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ProviderStatus(str, enum.Enum):
    """Provider operational status."""
    ACTIVE = "active"           # Fully operational
    DEGRADED = "degraded"       # Experiencing issues
    MAINTENANCE = "maintenance" # Planned downtime
    DISABLED = "disabled"       # Manually disabled
    DEPRECATED = "deprecated"   # Being phased out


class ModelStatus(str, enum.Enum):
    """Model availability status."""
    ACTIVE = "active"           # Available for use
    BETA = "beta"               # Preview/beta access
    DEPRECATED = "deprecated"   # Still works, being phased out
    DISABLED = "disabled"       # Manually disabled
    RETIRED = "retired"         # No longer available


class ModelCategory(str, enum.Enum):
    """Model capability categories."""
    # Chat & Reasoning
    CHAT = "chat"               # General chat/conversation
    REASONING = "reasoning"     # Extended thinking/chain-of-thought
    FLAGSHIP = "flagship"       # Provider's top-tier model
    STANDARD = "standard"       # General purpose balanced model
    EFFICIENT = "efficient"     # Optimized for speed/cost
    EDGE = "edge"               # Edge/on-device deployment

    # Specialized
    CODING = "coding"           # Code generation/editing
    CODE = "code"               # Alias for coding
    VISION = "vision"           # Image understanding
    MULTIMODAL = "multimodal"   # Multiple modalities (text+image+audio)
    SEARCH = "search"           # Search-augmented models

    # Embeddings & Retrieval
    EMBEDDING = "embedding"     # Text embeddings
    RERANKING = "reranking"     # Document reranking

    # Audio
    AUDIO_STT = "audio_stt"     # Speech-to-text
    AUDIO_TTS = "audio_tts"     # Text-to-speech

    # Generation
    IMAGE_GEN = "image_gen"     # Image generation
    VIDEO_GEN = "video_gen"     # Video generation

    # Moderation & Safety
    MODERATION = "moderation"   # Content moderation
    TRANSLATION = "translation" # Language translation


class ModelTier(str, enum.Enum):
    """Model pricing/capability tier."""
    FREE = "free"               # Free tier models
    STANDARD = "standard"       # Standard pricing
    PREMIUM = "premium"         # Higher capability/cost
    ENTERPRISE = "enterprise"   # Enterprise-only


class AIProvider(Base):
    """AI Provider/Vendor configuration.

    Represents a vendor like OpenAI, Anthropic, Google, etc.
    Allows enabling/disabling entire providers and storing credentials.
    """

    __tablename__ = "ai_providers"

    # Basic info
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(500))
    docs_url: Mapped[str | None] = mapped_column(String(500))

    # Provider type/category
    provider_type: Mapped[str] = mapped_column(
        String(50),
        default="llm",
        comment="Type: llm, image, audio, video, embedding"
    )

    # Status
    status: Mapped[ProviderStatus] = mapped_column(
        Enum(ProviderStatus, values_callable=lambda x: [e.value for e in x]),
        default=ProviderStatus.ACTIVE,
        nullable=False,
    )
    status_message: Mapped[str | None] = mapped_column(Text)

    # Configuration
    base_url: Mapped[str | None] = mapped_column(String(500))
    api_version: Mapped[str | None] = mapped_column(String(50))

    # Required secret keys (references to secrets model)
    required_secrets: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment="List of required secret names, e.g., ['openai_api_key']"
    )

    # Features supported
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_function_calling: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_audio: Mapped[bool] = mapped_column(Boolean, default=False)

    # Rate limits (default for provider)
    default_rpm: Mapped[int | None] = mapped_column(Integer, comment="Requests per minute")
    default_tpm: Mapped[int | None] = mapped_column(Integer, comment="Tokens per minute")

    # Metadata
    logo_url: Mapped[str | None] = mapped_column(String(500))
    color: Mapped[str | None] = mapped_column(String(20), comment="Brand color hex")

    # Ordering for UI
    sort_order: Mapped[int] = mapped_column(Integer, default=100)

    # Relationships
    models: Mapped[list["AIModel"]] = relationship(
        "AIModel",
        back_populates="provider",
        cascade="all, delete-orphan",
    )
    capability_mappings: Mapped[list["VendorCapabilityMapping"]] = relationship(
        "VendorCapabilityMapping",
        back_populates="provider",
        cascade="all, delete-orphan",
    )
    builtin_tools: Mapped[list["BuiltinTool"]] = relationship(
        "BuiltinTool",
        back_populates="provider",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_ai_providers_status", "status"),
        Index("ix_ai_providers_type", "provider_type"),
    )


class AIModel(Base):
    """AI Model definition with capabilities and metadata.

    Stores all model information including capabilities, pricing,
    context limits, and user-friendly descriptions.
    """

    __tablename__ = "ai_models"

    # Provider relationship
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_providers.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[AIProvider] = relationship("AIProvider", back_populates="models")

    # Capabilities relationship (DB-driven capabilities)
    capabilities: Mapped[list["ModelCapability"]] = relationship(
        "ModelCapability",
        back_populates="model",
        cascade="all, delete-orphan",
    )

    # Model-tool support entries
    tool_support_entries: Mapped[list["ModelToolSupport"]] = relationship(
        "ModelToolSupport",
        back_populates="model",
        cascade="all, delete-orphan",
    )

    # Model identification
    model_id: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="Official model ID used in API calls"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)

    # Aliases for convenience
    aliases: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment="Alternative names, e.g., ['gpt-4', 'gpt4']"
    )

    # Version info
    version: Mapped[str | None] = mapped_column(String(50))
    release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Status
    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus, values_callable=lambda x: [e.value for e in x]),
        default=ModelStatus.ACTIVE,
        nullable=False,
    )
    deprecation_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="When the model will be/was deprecated"
    )
    retirement_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="When the model will be/was retired"
    )

    # Categories and capabilities
    category: Mapped[ModelCategory] = mapped_column(
        Enum(ModelCategory, values_callable=lambda x: [e.value for e in x]),
        default=ModelCategory.CHAT,
        nullable=False,
    )
    tier: Mapped[ModelTier] = mapped_column(
        Enum(ModelTier, values_callable=lambda x: [e.value for e in x]),
        default=ModelTier.STANDARD,
        nullable=False,
    )

    # Descriptions (user-friendly)
    short_description: Mapped[str | None] = mapped_column(
        String(500),
        comment="Brief one-liner description"
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        comment="Detailed description of capabilities"
    )
    best_for: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment="Use cases this model excels at"
    )
    limitations: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment="Known limitations or warnings"
    )

    # Technical specifications
    context_window: Mapped[int] = mapped_column(
        Integer,
        default=4096,
        comment="Maximum context length in tokens"
    )
    max_output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        comment="Maximum output tokens (if different from context)"
    )

    # Capabilities flags
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_video: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_json_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_system_prompt: Mapped[bool] = mapped_column(Boolean, default=True)

    # Special capabilities
    is_reasoning_model: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Extended thinking / chain-of-thought"
    )
    is_moe: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Mixture of Experts architecture"
    )
    is_fine_tunable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_distilled: Mapped[bool] = mapped_column(Boolean, default=False)

    # Architecture info
    parameter_count: Mapped[str | None] = mapped_column(
        String(50),
        comment="e.g., '70B', '8x7B', '17B active / 400B total'"
    )
    architecture: Mapped[str | None] = mapped_column(
        String(100),
        comment="e.g., 'Transformer', 'MoE', 'Mamba'"
    )
    training_cutoff: Mapped[str | None] = mapped_column(
        String(50),
        comment="Training data cutoff date, e.g., 'April 2024'"
    )

    # Pricing (per 1M tokens, in USD)
    input_price_per_1m: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        comment="Input cost per 1M tokens in USD"
    )
    output_price_per_1m: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        comment="Output cost per 1M tokens in USD"
    )
    cached_input_price_per_1m: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4),
        comment="Cached/prompt caching input price"
    )

    # Rate limits (model-specific overrides)
    rpm_limit: Mapped[int | None] = mapped_column(Integer)
    tpm_limit: Mapped[int | None] = mapped_column(Integer)
    rpd_limit: Mapped[int | None] = mapped_column(Integer, comment="Requests per day")

    # Default parameters
    default_temperature: Mapped[float | None] = mapped_column(Numeric(3, 2))
    default_top_p: Mapped[float | None] = mapped_column(Numeric(3, 2))
    default_max_tokens: Mapped[int | None] = mapped_column(Integer)

    # Recommended parameters
    recommended_temperature: Mapped[float | None] = mapped_column(
        Numeric(3, 2),
        comment="Recommended temperature for best results"
    )

    # Languages supported
    supported_languages: Mapped[list[str] | None] = mapped_column(
        ARRAY(String),
        comment="ISO language codes, null = all"
    )

    # Extra configuration/metadata
    config: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="Additional model-specific configuration"
    )

    # UI/Display
    icon: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(20))
    badge: Mapped[str | None] = mapped_column(
        String(50),
        comment="Badge text like 'NEW', 'FAST', 'RECOMMENDED'"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Default model for this provider"
    )

    __table_args__ = (
        UniqueConstraint("provider_id", "model_id", name="uq_provider_model"),
        Index("ix_ai_models_provider", "provider_id"),
        Index("ix_ai_models_status", "status"),
        Index("ix_ai_models_category", "category"),
        Index("ix_ai_models_tier", "tier"),
        Index("ix_ai_models_featured", "is_featured"),
    )


class ModelUsageStats(Base):
    """Track model usage statistics for analytics."""

    __tablename__ = "model_usage_stats"

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_models.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Usage period
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Counts
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    # Tokens
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Latency (milliseconds)
    avg_latency_ms: Mapped[int | None] = mapped_column(Integer)
    p50_latency_ms: Mapped[int | None] = mapped_column(Integer)
    p95_latency_ms: Mapped[int | None] = mapped_column(Integer)
    p99_latency_ms: Mapped[int | None] = mapped_column(Integer)

    # Cost
    total_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))

    __table_args__ = (
        Index("ix_model_usage_model_period", "model_id", "period_start"),
    )


# ModelCapability and VendorCapabilityMapping are defined in src.models.capability
# They are imported here for relationship resolution via SQLAlchemy string references.


# Pre-defined provider configurations
DEFAULT_PROVIDERS: list[dict[str, Any]] = [
    {
        "name": "openai",
        "display_name": "OpenAI",
        "description": "OpenAI's GPT models including GPT-5.2, GPT-4.1, and o3/o4 reasoning models. Industry-leading capabilities for chat, coding, and complex reasoning.",
        "website": "https://openai.com",
        "docs_url": "https://platform.openai.com/docs",
        "provider_type": "llm",
        "required_secrets": ["openai_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_audio": True,
        "logo_url": "/logos/openai.svg",
        "color": "#10A37F",
        "sort_order": 1,
    },
    {
        "name": "anthropic",
        "display_name": "Anthropic",
        "description": "Claude models from Anthropic. Known for safety, helpfulness, and strong performance on complex tasks. Claude Opus 4.6 is the most capable model.",
        "website": "https://anthropic.com",
        "docs_url": "https://docs.anthropic.com",
        "provider_type": "llm",
        "required_secrets": ["anthropic_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/anthropic.svg",
        "color": "#D4A574",
        "sort_order": 2,
    },
    {
        "name": "google",
        "display_name": "Google AI",
        "description": "Google's Gemini models with multimodal capabilities. Gemini 3 Pro leads benchmarks with exceptional reasoning and long context support.",
        "website": "https://ai.google.dev",
        "docs_url": "https://ai.google.dev/docs",
        "provider_type": "llm",
        "required_secrets": ["google_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_audio": True,
        "logo_url": "/logos/google.svg",
        "color": "#4285F4",
        "sort_order": 3,
    },
    {
        "name": "mistral",
        "display_name": "Mistral AI",
        "description": "European AI lab offering efficient, multilingual models. Mistral Large 3 provides frontier capabilities with MoE architecture.",
        "website": "https://mistral.ai",
        "docs_url": "https://docs.mistral.ai",
        "provider_type": "llm",
        "required_secrets": ["mistral_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/mistral.svg",
        "color": "#FF7000",
        "sort_order": 4,
    },
    {
        "name": "cohere",
        "display_name": "Cohere",
        "description": "Enterprise-focused AI with Command models optimized for RAG and tool use. Native grounding and citation support.",
        "website": "https://cohere.com",
        "docs_url": "https://docs.cohere.com",
        "provider_type": "llm",
        "required_secrets": ["cohere_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/cohere.svg",
        "color": "#39594D",
        "sort_order": 5,
    },
    {
        "name": "groq",
        "display_name": "Groq",
        "description": "Ultra-fast inference on custom LPU hardware. Best for latency-sensitive applications. Supports Llama 4, DeepSeek R1, and more.",
        "website": "https://groq.com",
        "docs_url": "https://console.groq.com/docs",
        "provider_type": "llm",
        "required_secrets": ["groq_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/groq.svg",
        "color": "#F55036",
        "sort_order": 6,
    },
    {
        "name": "together",
        "display_name": "Together AI",
        "description": "Run open-source models at scale with optimized inference. Wide selection including Llama 4, Qwen 3, and DeepSeek models.",
        "website": "https://together.ai",
        "docs_url": "https://docs.together.ai",
        "provider_type": "llm",
        "required_secrets": ["together_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/together.svg",
        "color": "#0066FF",
        "sort_order": 7,
    },
    {
        "name": "fireworks",
        "display_name": "Fireworks AI",
        "description": "Fast, cost-effective inference for open-source models. Great for production workloads with competitive pricing.",
        "website": "https://fireworks.ai",
        "docs_url": "https://docs.fireworks.ai",
        "provider_type": "llm",
        "required_secrets": ["fireworks_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/fireworks.svg",
        "color": "#FF6B35",
        "sort_order": 8,
    },
    {
        "name": "bedrock",
        "display_name": "AWS Bedrock",
        "description": "Access multiple foundation models through AWS. Includes Claude, Llama, Mistral, and Amazon Titan. Enterprise-grade security.",
        "website": "https://aws.amazon.com/bedrock",
        "docs_url": "https://docs.aws.amazon.com/bedrock",
        "provider_type": "llm",
        "required_secrets": ["aws_access_key_id", "aws_secret_access_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/aws.svg",
        "color": "#FF9900",
        "sort_order": 9,
    },
    {
        "name": "replicate",
        "display_name": "Replicate",
        "description": "Run any ML model via simple API. Thousands of open-source models without managing infrastructure.",
        "website": "https://replicate.com",
        "docs_url": "https://replicate.com/docs",
        "provider_type": "llm",
        "required_secrets": ["replicate_api_token"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "logo_url": "/logos/replicate.svg",
        "color": "#000000",
        "sort_order": 10,
    },
    {
        "name": "xai",
        "display_name": "xAI",
        "description": "Grok models from xAI with real-time X (Twitter) integration. Unique access to current events and social trends.",
        "website": "https://x.ai",
        "docs_url": "https://docs.x.ai",
        "provider_type": "llm",
        "required_secrets": ["xai_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "logo_url": "/logos/xai.svg",
        "color": "#1DA1F2",
        "sort_order": 11,
    },
    {
        "name": "perplexity",
        "display_name": "Perplexity",
        "description": "Search-grounded AI with real-time web access. Sonar models provide cited responses with up-to-date information.",
        "website": "https://perplexity.ai",
        "docs_url": "https://docs.perplexity.ai",
        "provider_type": "llm",
        "required_secrets": ["perplexity_api_key"],
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_vision": False,
        "logo_url": "/logos/perplexity.svg",
        "color": "#1FB8CD",
        "sort_order": 12,
    },
    {
        "name": "deepseek",
        "display_name": "DeepSeek",
        "description": "Open-source MoE models with GPT-4 class performance at fraction of cost. DeepSeek R1 rivals o1 on reasoning benchmarks.",
        "website": "https://deepseek.com",
        "docs_url": "https://platform.deepseek.com/docs",
        "provider_type": "llm",
        "required_secrets": ["deepseek_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": False,
        "logo_url": "/logos/deepseek.svg",
        "color": "#4D6BFE",
        "sort_order": 13,
    },
    {
        "name": "qwen",
        "display_name": "Qwen (Alibaba)",
        "description": "Alibaba's Qwen models with industry-leading 1M context and strong multilingual support. Excellent for Chinese and Asian languages.",
        "website": "https://qwen.ai",
        "docs_url": "https://help.aliyun.com/zh/model-studio",
        "provider_type": "llm",
        "required_secrets": ["qwen_api_key"],
        "supports_streaming": True,
        "supports_function_calling": True,
        "supports_vision": True,
        "supports_audio": True,
        "logo_url": "/logos/qwen.svg",
        "color": "#7C3AED",
        "sort_order": 14,
    },
    # Audio providers
    {
        "name": "deepgram",
        "display_name": "Deepgram",
        "description": "Industry-leading STT with sub-300ms latency. Best for real-time voice applications and call center analytics.",
        "website": "https://deepgram.com",
        "docs_url": "https://developers.deepgram.com",
        "provider_type": "audio",
        "required_secrets": ["deepgram_api_key"],
        "supports_streaming": True,
        "supports_function_calling": False,
        "logo_url": "/logos/deepgram.svg",
        "color": "#13EF93",
        "sort_order": 15,
    },
    {
        "name": "elevenlabs",
        "display_name": "ElevenLabs",
        "description": "Most realistic AI voices with voice cloning and emotion control. Premium text-to-speech for content creation.",
        "website": "https://elevenlabs.io",
        "docs_url": "https://docs.elevenlabs.io",
        "provider_type": "audio",
        "required_secrets": ["elevenlabs_api_key"],
        "supports_streaming": True,
        "supports_function_calling": False,
        "logo_url": "/logos/elevenlabs.svg",
        "color": "#000000",
        "sort_order": 16,
    },
    {
        "name": "azure",
        "display_name": "Azure AI",
        "description": "Microsoft Azure Cognitive Services for speech and language. 400+ voices in 140+ languages with custom voice training.",
        "website": "https://azure.microsoft.com/services/cognitive-services",
        "docs_url": "https://docs.microsoft.com/azure/cognitive-services",
        "provider_type": "audio",
        "required_secrets": ["azure_speech_key", "azure_speech_region"],
        "supports_streaming": True,
        "supports_function_calling": False,
        "supports_audio": True,
        "logo_url": "/logos/azure.svg",
        "color": "#0078D4",
        "sort_order": 17,
    },
    # Embedding providers
    {
        "name": "voyage",
        "display_name": "Voyage AI",
        "description": "Specialized embedding models for code, legal, and finance domains. High-performance retrieval embeddings.",
        "website": "https://voyage.ai",
        "docs_url": "https://docs.voyageai.com",
        "provider_type": "embedding",
        "required_secrets": ["voyage_api_key"],
        "supports_streaming": False,
        "supports_function_calling": False,
        "logo_url": "/logos/voyage.svg",
        "color": "#5046E5",
        "sort_order": 18,
    },
    {
        "name": "jina",
        "display_name": "Jina AI",
        "description": "Multimodal embeddings supporting text and images. Optimized for cross-modal search and retrieval.",
        "website": "https://jina.ai",
        "docs_url": "https://docs.jina.ai",
        "provider_type": "embedding",
        "required_secrets": ["jina_api_key"],
        "supports_streaming": False,
        "supports_function_calling": False,
        "logo_url": "/logos/jina.svg",
        "color": "#FF6A00",
        "sort_order": 19,
    },
]


# Complete model definitions for all supported providers
SAMPLE_MODELS: list[dict[str, Any]] = [
    # ========================================
    # OpenAI Models
    # ========================================
    # GPT-4o family (flagship)
    {
        "provider_name": "openai",
        "model_id": "gpt-4o",
        "name": "gpt-4o",
        "display_name": "GPT-4o",
        "aliases": ["gpt4o", "4o"],
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.PREMIUM,
        "short_description": "Most capable GPT-4 with native multimodal understanding and web search.",
        "description": "GPT-4o is OpenAI's flagship multimodal model with native vision, audio understanding, and built-in web search via Responses API. Excellent for complex tasks requiring real-time information.",
        "best_for": ["Multimodal tasks", "Web search", "Complex reasoning", "Code generation", "Analysis"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "input_price_per_1m": Decimal("2.50"),
        "output_price_per_1m": Decimal("10.00"),
        "badge": "FLAGSHIP",
        "is_featured": True,
        "is_default": True,
        "sort_order": 1,
    },
    {
        "provider_name": "openai",
        "model_id": "gpt-4o-mini",
        "name": "gpt-4o-mini",
        "display_name": "GPT-4o Mini",
        "aliases": ["4o-mini", "gpt4o-mini"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Fast, affordable GPT-4o variant with web search support.",
        "description": "GPT-4o Mini offers excellent performance at a fraction of the cost. Supports web search and function calling. Great for high-volume applications.",
        "best_for": ["High-volume tasks", "Cost-sensitive apps", "Quick responses", "Web search"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "input_price_per_1m": Decimal("0.15"),
        "output_price_per_1m": Decimal("0.60"),
        "badge": "BEST VALUE",
        "is_featured": True,
        "sort_order": 2,
    },
    # GPT-4.1 family (latest)
    {
        "provider_name": "openai",
        "model_id": "gpt-4.1",
        "name": "gpt-4.1",
        "display_name": "GPT-4.1",
        "aliases": ["gpt41"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "short_description": "Latest GPT-4 variant with improved reasoning and web search.",
        "description": "GPT-4.1 is the latest iteration of GPT-4 with improved instruction following, reasoning capabilities, and native web search support via Responses API.",
        "best_for": ["Complex reasoning", "Coding", "Analysis", "Web research"],
        "context_window": 128000,
        "max_output_tokens": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "input_price_per_1m": Decimal("2.00"),
        "output_price_per_1m": Decimal("8.00"),
        "badge": "NEW",
        "sort_order": 3,
    },
    {
        "provider_name": "openai",
        "model_id": "gpt-4.1-mini",
        "name": "gpt-4.1-mini",
        "display_name": "GPT-4.1 Mini",
        "aliases": ["gpt41-mini"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Efficient GPT-4.1 variant with web search.",
        "description": "GPT-4.1 Mini provides GPT-4.1 capabilities at lower cost. Supports web search and function calling.",
        "best_for": ["Cost-effective tasks", "Web search", "General chat"],
        "context_window": 128000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.10"),
        "output_price_per_1m": Decimal("0.40"),
        "sort_order": 4,
    },
    {
        "provider_name": "openai",
        "model_id": "gpt-4.1-nano",
        "name": "gpt-4.1-nano",
        "display_name": "GPT-4.1 Nano",
        "aliases": ["gpt41-nano"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.FREE,
        "short_description": "Most efficient GPT-4.1 for simple tasks.",
        "description": "GPT-4.1 Nano is the most cost-effective option for simple chat and basic tasks.",
        "best_for": ["Simple tasks", "High volume", "Classification"],
        "context_window": 32000,
        "max_output_tokens": 8192,
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.05"),
        "output_price_per_1m": Decimal("0.20"),
        "sort_order": 5,
    },
    # GPT-4 Turbo
    {
        "provider_name": "openai",
        "model_id": "gpt-4-turbo",
        "name": "gpt-4-turbo",
        "display_name": "GPT-4 Turbo",
        "aliases": ["gpt4-turbo"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "short_description": "Fast GPT-4 with vision and large context.",
        "description": "GPT-4 Turbo offers fast inference with 128K context. Good for vision tasks and complex reasoning.",
        "best_for": ["Long documents", "Vision tasks", "Complex reasoning"],
        "context_window": 128000,
        "max_output_tokens": 4096,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("10.00"),
        "output_price_per_1m": Decimal("30.00"),
        "sort_order": 10,
    },
    # GPT-5.2 (latest flagship)
    {
        "provider_name": "openai",
        "model_id": "gpt-5.2",
        "name": "gpt-5.2",
        "display_name": "GPT-5.2",
        "aliases": ["gpt5", "gpt-5"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "OpenAI's most capable flagship model.",
        "description": "GPT-5.2 is OpenAI's latest flagship model with superior reasoning, coding, and multimodal capabilities. Supports web search, tool use, and vision natively.",
        "best_for": ["Complex reasoning", "Advanced coding", "Multimodal analysis", "Research", "Agentic workflows"],
        "context_window": 256000,
        "max_output_tokens": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "input_price_per_1m": Decimal("10.00"),
        "output_price_per_1m": Decimal("30.00"),
        "badge": "FLAGSHIP",
        "is_featured": True,
        "sort_order": 0,
    },
    # o-series reasoning models
    {
        "provider_name": "openai",
        "model_id": "o1",
        "name": "o1",
        "display_name": "o1",
        "aliases": ["o1-full"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.PREMIUM,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Deprecated reasoning model (use o3 instead).",
        "description": "o1 uses extended thinking to solve complex problems. Superseded by o3 for most use cases.",
        "best_for": ["Mathematical proofs", "Scientific reasoning", "Complex coding"],
        "limitations": ["Higher latency", "No tool calling", "Higher cost", "Deprecated - use o3"],
        "context_window": 200000,
        "supports_tools": False,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("15.00"),
        "output_price_per_1m": Decimal("60.00"),
        "sort_order": 30,
    },
    {
        "provider_name": "openai",
        "model_id": "o1-mini",
        "name": "o1-mini",
        "display_name": "o1 Mini",
        "aliases": ["o1mini"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Deprecated reasoning model (use o4-mini instead).",
        "description": "o1 Mini offers reasoning capabilities at lower cost. Superseded by o4-mini.",
        "best_for": ["Coding", "Math", "Logic puzzles"],
        "context_window": 128000,
        "supports_tools": False,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("3.00"),
        "output_price_per_1m": Decimal("12.00"),
        "sort_order": 31,
    },
    # o3 family (latest reasoning)
    {
        "provider_name": "openai",
        "model_id": "o3",
        "name": "o3",
        "display_name": "o3",
        "aliases": ["o3-full"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.PREMIUM,
        "short_description": "Full reasoning model with tool use support.",
        "description": "o3 is OpenAI's most capable reasoning model with extended thinking and full tool/function calling support. Excels at math, science, and complex analysis.",
        "best_for": ["Mathematical proofs", "Scientific reasoning", "Complex coding", "Multi-step analysis"],
        "limitations": ["Higher latency", "Higher cost"],
        "context_window": 200000,
        "max_output_tokens": 100000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("10.00"),
        "output_price_per_1m": Decimal("40.00"),
        "badge": "REASONING",
        "is_featured": True,
        "sort_order": 20,
    },
    {
        "provider_name": "openai",
        "model_id": "o3-mini",
        "name": "o3-mini",
        "display_name": "o3 Mini",
        "aliases": ["o3mini"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "short_description": "Efficient reasoning model for STEM tasks.",
        "description": "o3 Mini is an efficient reasoning model with strong performance on STEM tasks.",
        "best_for": ["STEM problems", "Coding", "Analysis"],
        "context_window": 200000,
        "supports_tools": False,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("1.10"),
        "output_price_per_1m": Decimal("4.40"),
        "sort_order": 22,
    },
    {
        "provider_name": "openai",
        "model_id": "o4-mini",
        "name": "o4-mini",
        "display_name": "o4 Mini",
        "aliases": ["o4mini"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "short_description": "Latest efficient reasoning model with tool support.",
        "description": "o4 Mini is the latest efficient reasoning model combining strong STEM performance with tool use and vision capabilities.",
        "best_for": ["STEM problems", "Coding", "Agentic tasks", "Cost-effective reasoning"],
        "context_window": 200000,
        "max_output_tokens": 100000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("1.10"),
        "output_price_per_1m": Decimal("4.40"),
        "badge": "NEW",
        "is_featured": True,
        "sort_order": 21,
    },
    # Legacy GPT models
    {
        "provider_name": "openai",
        "model_id": "gpt-4",
        "name": "gpt-4",
        "display_name": "GPT-4",
        "aliases": ["gpt4"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Original GPT-4 (use gpt-4o instead).",
        "description": "Original GPT-4 model. Consider using GPT-4o for better performance and features.",
        "context_window": 8192,
        "max_output_tokens": 4096,
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("30.00"),
        "output_price_per_1m": Decimal("60.00"),
        "sort_order": 50,
    },
    {
        "provider_name": "openai",
        "model_id": "gpt-3.5-turbo",
        "name": "gpt-3.5-turbo",
        "display_name": "GPT-3.5 Turbo",
        "aliases": ["gpt35", "chatgpt"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.FREE,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Legacy model (use gpt-4o-mini instead).",
        "description": "Legacy GPT-3.5. Consider using GPT-4o Mini for better performance at similar cost.",
        "context_window": 16385,
        "max_output_tokens": 4096,
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.50"),
        "output_price_per_1m": Decimal("1.50"),
        "sort_order": 51,
    },

    # ========================================
    # Anthropic Claude Models
    # ========================================
    # Claude Opus 4.6 (most intelligent)
    {
        "provider_name": "anthropic",
        "model_id": "claude-opus-4-6-20260115",
        "name": "claude-opus-4.6",
        "display_name": "Claude Opus 4.6",
        "aliases": ["claude-opus", "opus-4.6", "opus"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "Anthropic's most intelligent model with hybrid extended thinking.",
        "description": "Claude Opus 4.6 is the pinnacle of Anthropic's model family with hybrid extended thinking, exceptional reasoning, and agentic capabilities. Best for complex analysis, research, and software engineering.",
        "best_for": ["Complex analysis", "Research synthesis", "Software engineering", "Agentic workflows", "Nuanced writing"],
        "context_window": 200000,
        "max_output_tokens": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("15.00"),
        "output_price_per_1m": Decimal("75.00"),
        "badge": "MOST INTELLIGENT",
        "is_featured": True,
        "is_default": True,
        "sort_order": 0,
    },
    # Claude Opus 4.5
    {
        "provider_name": "anthropic",
        "model_id": "claude-opus-4-5-20251101",
        "name": "claude-opus-4.5",
        "display_name": "Claude Opus 4.5",
        "aliases": ["claude-opus", "opus-4.5", "opus"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "short_description": "Anthropic's most intelligent model with hybrid extended thinking.",
        "description": "Claude Opus 4.5 is the pinnacle of Anthropic's model family with hybrid extended thinking for complex reasoning. Exceptional at nuanced analysis, creative writing, and research synthesis.",
        "best_for": ["Complex analysis", "Research synthesis", "Nuanced writing", "Ethical reasoning"],
        "context_window": 1000000,
        "max_output_tokens": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("15.00"),
        "output_price_per_1m": Decimal("75.00"),
        "badge": "MOST INTELLIGENT",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "anthropic",
        "model_id": "claude-opus-4-1-20250805",
        "name": "claude-opus-4.1",
        "display_name": "Claude Opus 4.1",
        "aliases": ["opus-4.1"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "short_description": "Improved code and search capabilities.",
        "description": "Claude Opus 4.1 features improved code generation, tool use, and search integration.",
        "context_window": 200000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("12.00"),
        "output_price_per_1m": Decimal("60.00"),
        "sort_order": 2,
    },
    {
        "provider_name": "anthropic",
        "model_id": "claude-opus-4-20250522",
        "name": "claude-opus-4",
        "display_name": "Claude Opus 4",
        "aliases": ["opus-4"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "short_description": "Base Opus 4 model with strong capabilities.",
        "description": "Claude Opus 4 is the base version of the Opus 4 family with exceptional reasoning.",
        "context_window": 200000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("10.00"),
        "output_price_per_1m": Decimal("50.00"),
        "sort_order": 3,
    },
    # Claude Sonnet 4.x (best for coding)
    {
        "provider_name": "anthropic",
        "model_id": "claude-sonnet-4-5-20250929",
        "name": "claude-sonnet-4.5",
        "display_name": "Claude Sonnet 4.5",
        "aliases": ["claude-sonnet", "sonnet-4.5", "sonnet"],
        "category": ModelCategory.CODING,
        "tier": ModelTier.STANDARD,
        "short_description": "Best coding model with excellent balance of capability and speed.",
        "description": "Claude Sonnet 4.5 is optimized for software development and agentic tasks. Leads benchmarks in code generation, debugging, and complex codebase understanding.",
        "best_for": ["Code generation", "Debugging", "Code review", "AI agents", "Technical writing"],
        "context_window": 200000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("3.00"),
        "output_price_per_1m": Decimal("15.00"),
        "badge": "BEST FOR CODE",
        "is_featured": True,
        "is_default": True,
        "sort_order": 10,
    },
    {
        "provider_name": "anthropic",
        "model_id": "claude-sonnet-4-20250522",
        "name": "claude-sonnet-4",
        "display_name": "Claude Sonnet 4",
        "aliases": ["sonnet-4"],
        "category": ModelCategory.CODING,
        "tier": ModelTier.STANDARD,
        "short_description": "Base Sonnet 4 with strong coding capabilities.",
        "description": "Claude Sonnet 4 is the base version with excellent coding and reasoning abilities.",
        "context_window": 200000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("2.50"),
        "output_price_per_1m": Decimal("12.50"),
        "sort_order": 11,
    },
    # Claude Haiku 4.x (fast and efficient)
    {
        "provider_name": "anthropic",
        "model_id": "claude-haiku-4-5-20251015",
        "name": "claude-haiku-4.5",
        "display_name": "Claude Haiku 4.5",
        "aliases": ["claude-haiku", "haiku-4.5", "haiku"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.FREE,
        "short_description": "Fast, affordable model near frontier performance.",
        "description": "Claude Haiku 4.5 offers near-frontier capabilities at the lowest cost. Excellent for high-volume applications and quick responses.",
        "best_for": ["High volume", "Quick responses", "Classification", "Simple tasks"],
        "context_window": 200000,
        "max_output_tokens": 8192,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("0.25"),
        "output_price_per_1m": Decimal("1.25"),
        "badge": "FAST",
        "is_featured": True,
        "sort_order": 20,
    },
    # Legacy Claude 3.x
    {
        "provider_name": "anthropic",
        "model_id": "claude-3-5-sonnet-20241022",
        "name": "claude-3.5-sonnet",
        "display_name": "Claude 3.5 Sonnet",
        "aliases": ["claude-35-sonnet"],
        "category": ModelCategory.CODING,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Legacy model (use Sonnet 4.5 instead).",
        "context_window": 200000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("3.00"),
        "output_price_per_1m": Decimal("15.00"),
        "sort_order": 50,
    },
    {
        "provider_name": "anthropic",
        "model_id": "claude-3-5-haiku-20241022",
        "name": "claude-3.5-haiku",
        "display_name": "Claude 3.5 Haiku",
        "aliases": ["claude-35-haiku"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.FREE,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Legacy model (use Haiku 4.5 instead).",
        "context_window": 200000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.25"),
        "output_price_per_1m": Decimal("1.25"),
        "sort_order": 51,
    },
    {
        "provider_name": "anthropic",
        "model_id": "claude-3-opus-20240229",
        "name": "claude-3-opus",
        "display_name": "Claude 3 Opus",
        "category": ModelCategory.CHAT,
        "tier": ModelTier.PREMIUM,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Deprecated (use Opus 4.5 instead).",
        "context_window": 200000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("15.00"),
        "output_price_per_1m": Decimal("75.00"),
        "sort_order": 52,
    },
    {
        "provider_name": "anthropic",
        "model_id": "claude-3-haiku-20240307",
        "name": "claude-3-haiku",
        "display_name": "Claude 3 Haiku",
        "category": ModelCategory.CHAT,
        "tier": ModelTier.FREE,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Legacy fast model.",
        "context_window": 200000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.25"),
        "output_price_per_1m": Decimal("1.25"),
        "sort_order": 53,
    },

    # ========================================
    # Google Gemini Models
    # ========================================
    # Gemini 3.x (latest)
    {
        "provider_name": "google",
        "model_id": "gemini-3-pro",
        "name": "gemini-3-pro",
        "display_name": "Gemini 3 Pro",
        "aliases": ["gemini-3", "gemini-pro", "gemini"],
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.PREMIUM,
        "short_description": "#1 on LMArena with exceptional multimodal and reasoning.",
        "description": "Gemini 3 Pro leads public benchmarks with state-of-the-art performance across text, image, audio, and video. Native 2M context window.",
        "best_for": ["Multimodal tasks", "Complex reasoning", "Long context", "Research"],
        "context_window": 2000000,
        "max_output_tokens": 65536,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": True,
        "supports_video": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("7.00"),
        "output_price_per_1m": Decimal("21.00"),
        "badge": "#1 BENCHMARK",
        "is_featured": True,
        "is_default": True,
        "sort_order": 1,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-3-deep-think",
        "name": "gemini-3-deep-think",
        "display_name": "Gemini 3 Deep Think",
        "aliases": ["gemini-deep-think"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.PREMIUM,
        "short_description": "Extended thinking model for complex problems.",
        "description": "Gemini 3 Deep Think uses extended reasoning for complex math, science, and analysis tasks.",
        "best_for": ["Mathematical proofs", "Scientific analysis", "Complex reasoning"],
        "context_window": 2000000,
        "supports_tools": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("10.00"),
        "output_price_per_1m": Decimal("30.00"),
        "badge": "DEEP THINKING",
        "sort_order": 2,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-3-flash",
        "name": "gemini-3-flash",
        "display_name": "Gemini 3 Flash",
        "aliases": ["gemini-flash"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Fast and affordable with 1M context.",
        "description": "Gemini 3 Flash offers excellent performance at low cost with 1M context window.",
        "best_for": ["High volume", "Quick responses", "Long documents"],
        "context_window": 1000000,
        "max_output_tokens": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.075"),
        "output_price_per_1m": Decimal("0.30"),
        "badge": "FAST",
        "is_featured": True,
        "sort_order": 3,
    },
    # Gemini 2.5 family
    {
        "provider_name": "google",
        "model_id": "gemini-2.5-pro",
        "name": "gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.PREMIUM,
        "short_description": "Previous generation with 2M context.",
        "context_window": 2000000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_audio": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("5.00"),
        "output_price_per_1m": Decimal("15.00"),
        "sort_order": 10,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-2.5-flash",
        "name": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Fast 2.5 generation model.",
        "context_window": 1000000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.05"),
        "output_price_per_1m": Decimal("0.20"),
        "sort_order": 11,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-2.5-flash-lite",
        "name": "gemini-2.5-flash-lite",
        "display_name": "Gemini 2.5 Flash Lite",
        "category": ModelCategory.CHAT,
        "tier": ModelTier.FREE,
        "short_description": "Most efficient Gemini model.",
        "context_window": 1000000,
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.02"),
        "output_price_per_1m": Decimal("0.08"),
        "sort_order": 12,
    },
    # Gemini 2.0 family
    {
        "provider_name": "google",
        "model_id": "gemini-2.0-pro",
        "name": "gemini-2.0-pro",
        "display_name": "Gemini 2.0 Pro",
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Retiring March 2026.",
        "context_window": 1000000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("3.50"),
        "output_price_per_1m": Decimal("10.50"),
        "sort_order": 20,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-2.0-flash",
        "name": "gemini-2.0-flash",
        "display_name": "Gemini 2.0 Flash",
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Retiring March 2026.",
        "context_window": 1000000,
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("0.04"),
        "output_price_per_1m": Decimal("0.16"),
        "sort_order": 21,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-2.0-flash-thinking",
        "name": "gemini-2.0-flash-thinking",
        "display_name": "Gemini 2.0 Flash Thinking",
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.DEPRECATED,
        "short_description": "Retiring March 2026.",
        "context_window": 1000000,
        "supports_tools": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("0.06"),
        "output_price_per_1m": Decimal("0.24"),
        "sort_order": 22,
    },
    # Legacy Gemini 1.5
    {
        "provider_name": "google",
        "model_id": "gemini-1.5-pro",
        "name": "gemini-1.5-pro",
        "display_name": "Gemini 1.5 Pro",
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.RETIRED,
        "short_description": "Retired - use Gemini 3 Pro.",
        "context_window": 2000000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "sort_order": 50,
    },
    {
        "provider_name": "google",
        "model_id": "gemini-1.5-flash",
        "name": "gemini-1.5-flash",
        "display_name": "Gemini 1.5 Flash",
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "status": ModelStatus.RETIRED,
        "short_description": "Retired - use Gemini 3 Flash.",
        "context_window": 1000000,
        "supports_tools": True,
        "supports_streaming": True,
        "sort_order": 51,
    },

    # ========================================
    # Other Providers (samples)
    # ========================================
    # DeepSeek R1 (via Groq)
    {
        "provider_name": "groq",
        "model_id": "deepseek-r1-distill-llama-70b",
        "name": "deepseek-r1-70b",
        "display_name": "DeepSeek R1 Distill 70B",
        "aliases": ["deepseek-r1", "r1-70b"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "short_description": "Open-source reasoning model with 94.5% on MATH-500.",
        "description": "DeepSeek R1 Distill brings frontier reasoning to an efficient 70B model via Groq's ultra-fast inference.",
        "best_for": ["Math problems", "Logic puzzles", "Scientific reasoning"],
        "limitations": ["No tool calling", "English-focused"],
        "context_window": 128000,
        "supports_tools": False,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "is_distilled": True,
        "parameter_count": "70B",
        "input_price_per_1m": Decimal("0.59"),
        "output_price_per_1m": Decimal("0.79"),
        "badge": "FAST REASONING",
        "is_featured": True,
        "sort_order": 1,
    },
    # Llama 4 (via Together)
    {
        "provider_name": "together",
        "model_id": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-Turbo",
        "name": "llama-4-maverick",
        "display_name": "Llama 4 Maverick",
        "aliases": ["llama-4", "maverick"],
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.STANDARD,
        "short_description": "Meta's flagship open-weight MoE model with 1M context.",
        "description": "Llama 4 Maverick uses MoE architecture (17B active, 400B total) with native multimodal support.",
        "best_for": ["General chat", "Multimodal tasks", "Long documents"],
        "context_window": 1000000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "is_moe": True,
        "parameter_count": "17B active / 400B total",
        "architecture": "MoE (128 experts)",
        "input_price_per_1m": Decimal("0.27"),
        "output_price_per_1m": Decimal("0.85"),
        "badge": "OPEN SOURCE",
        "is_featured": True,
        "sort_order": 1,
    },
    # =========================================================================
    # Mistral AI Models
    # =========================================================================
    {
        "provider_name": "mistral",
        "model_id": "mistral-large-latest",
        "name": "mistral-large",
        "display_name": "Mistral Large 2",
        "aliases": ["mistral-large-2", "mistral-large-2411"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "Mistral's most capable model with 128K context.",
        "description": "Mistral Large 2 is a 123B parameter model excelling at complex reasoning, multilingual tasks, code generation, and agentic workflows with native tool calling.",
        "best_for": ["Complex reasoning", "Multilingual (12+ languages)", "Code generation", "Agentic workflows"],
        "limitations": ["Higher cost than smaller variants"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "parameter_count": "123B",
        "input_price_per_1m": Decimal("2.00"),
        "output_price_per_1m": Decimal("6.00"),
        "badge": "FLAGSHIP",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "mistral",
        "model_id": "mistral-small-latest",
        "name": "mistral-small",
        "display_name": "Mistral Small",
        "aliases": ["mistral-small-2501"],
        "category": ModelCategory.EFFICIENT,
        "tier": ModelTier.STANDARD,
        "short_description": "Cost-effective model for bulk operations.",
        "description": "Mistral Small offers excellent price-performance for translation, summarization, and sentiment analysis with 32K context.",
        "best_for": ["Translation", "Summarization", "Classification", "Bulk processing"],
        "context_window": 32000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "parameter_count": "22B",
        "input_price_per_1m": Decimal("0.10"),
        "output_price_per_1m": Decimal("0.30"),
        "badge": "EFFICIENT",
        "is_featured": False,
        "sort_order": 3,
    },
    {
        "provider_name": "mistral",
        "model_id": "codestral-latest",
        "name": "codestral",
        "display_name": "Codestral",
        "aliases": ["codestral-2501"],
        "category": ModelCategory.CODE,
        "tier": ModelTier.STANDARD,
        "short_description": "Specialized code generation model with 256K context.",
        "description": "Codestral is Mistral's dedicated coding model trained on 80+ programming languages with fill-in-the-middle (FIM) support and 256K context.",
        "best_for": ["Code completion", "Code generation", "Debugging", "Documentation"],
        "limitations": ["Code-focused, less versatile for general chat"],
        "context_window": 256000,
        "supports_tools": False,
        "supports_streaming": True,
        "supports_fim": True,
        "parameter_count": "22B",
        "input_price_per_1m": Decimal("0.30"),
        "output_price_per_1m": Decimal("0.90"),
        "badge": "CODE SPECIALIST",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "mistral",
        "model_id": "pixtral-large-latest",
        "name": "pixtral-large",
        "display_name": "Pixtral Large",
        "aliases": ["pixtral-large-2411"],
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.PREMIUM,
        "short_description": "Mistral's flagship multimodal model.",
        "description": "Pixtral Large combines 123B language model with vision capabilities for document understanding, image analysis, and multimodal reasoning.",
        "best_for": ["Document understanding", "Image analysis", "Visual Q&A", "Chart interpretation"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "parameter_count": "124B",
        "input_price_per_1m": Decimal("2.00"),
        "output_price_per_1m": Decimal("6.00"),
        "badge": "MULTIMODAL",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "mistral",
        "model_id": "ministral-8b-latest",
        "name": "ministral-8b",
        "display_name": "Ministral 8B",
        "aliases": ["ministral-8b-2410"],
        "category": ModelCategory.EDGE,
        "tier": ModelTier.FREE,
        "short_description": "Edge-optimized model for on-device deployment.",
        "description": "Ministral 8B is designed for edge computing and on-device deployment with excellent efficiency and 128K context support.",
        "best_for": ["Edge deployment", "Mobile apps", "Low-latency applications", "Privacy-sensitive tasks"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_streaming": True,
        "parameter_count": "8B",
        "input_price_per_1m": Decimal("0.10"),
        "output_price_per_1m": Decimal("0.10"),
        "badge": "EDGE",
        "is_featured": False,
        "sort_order": 5,
    },
    # =========================================================================
    # Cohere Models
    # =========================================================================
    {
        "provider_name": "cohere",
        "model_id": "command-r-plus-08-2024",
        "name": "command-r-plus",
        "display_name": "Command R+",
        "aliases": ["command-r-plus", "c4ai-aya-expanse-32b"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "Cohere's most capable model for enterprise RAG.",
        "description": "Command R+ is optimized for enterprise RAG workflows with excellent retrieval, summarization, and multilingual support across 23 languages.",
        "best_for": ["RAG applications", "Enterprise search", "Multilingual tasks", "Document analysis"],
        "limitations": ["Optimized for RAG, may be overkill for simple tasks"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_documents": True,
        "parameter_count": "104B",
        "input_price_per_1m": Decimal("2.50"),
        "output_price_per_1m": Decimal("10.00"),
        "badge": "RAG OPTIMIZED",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "cohere",
        "model_id": "command-r-08-2024",
        "name": "command-r",
        "display_name": "Command R",
        "aliases": ["command-r"],
        "category": ModelCategory.STANDARD,
        "tier": ModelTier.STANDARD,
        "short_description": "Balanced RAG model with great price-performance.",
        "description": "Command R offers excellent RAG performance at a lower cost, supporting 10 languages with tool use and document grounding.",
        "best_for": ["Cost-effective RAG", "Tool use", "Summarization", "Q&A systems"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_documents": True,
        "parameter_count": "35B",
        "input_price_per_1m": Decimal("0.15"),
        "output_price_per_1m": Decimal("0.60"),
        "badge": "BALANCED",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "cohere",
        "model_id": "command-light",
        "name": "command-light",
        "display_name": "Command Light",
        "aliases": ["command-light-nightly"],
        "category": ModelCategory.EFFICIENT,
        "tier": ModelTier.FREE,
        "short_description": "Lightweight model for high-throughput tasks.",
        "description": "Command Light is optimized for speed and cost, ideal for classification, extraction, and high-volume processing.",
        "best_for": ["Classification", "Entity extraction", "High-volume processing"],
        "context_window": 4096,
        "supports_tools": False,
        "supports_streaming": True,
        "parameter_count": "6B",
        "input_price_per_1m": Decimal("0.03"),
        "output_price_per_1m": Decimal("0.06"),
        "badge": "LIGHTWEIGHT",
        "is_featured": False,
        "sort_order": 4,
    },
    # =========================================================================
    # xAI Grok Models
    # =========================================================================
    {
        "provider_name": "xai",
        "model_id": "grok-3",
        "name": "grok-3",
        "display_name": "Grok 3",
        "aliases": ["grok3", "grok-3-latest"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "xAI's flagship model with web search and reasoning.",
        "description": "Grok 3 is xAI's most capable model with enhanced reasoning, real-time web search, and X integration. Strong performance on benchmarks.",
        "best_for": ["Current events", "Real-time information", "Complex reasoning", "Code generation"],
        "context_window": 131072,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "input_price_per_1m": Decimal("3.00"),
        "output_price_per_1m": Decimal("15.00"),
        "badge": "NEW",
        "is_featured": True,
        "is_default": True,
        "sort_order": 0,
    },
    {
        "provider_name": "xai",
        "model_id": "grok-3-mini",
        "name": "grok-3-mini",
        "display_name": "Grok 3 Mini",
        "aliases": ["grok3-mini"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "short_description": "Efficient reasoning model from xAI.",
        "description": "Grok 3 Mini is an efficient reasoning model with extended thinking capabilities at lower cost.",
        "best_for": ["STEM problems", "Coding", "Quick reasoning", "Cost-effective analysis"],
        "context_window": 131072,
        "supports_tools": True,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "input_price_per_1m": Decimal("0.30"),
        "output_price_per_1m": Decimal("0.50"),
        "badge": "REASONING",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "xai",
        "model_id": "grok-2-latest",
        "name": "grok-2",
        "display_name": "Grok 2",
        "aliases": ["grok-2-1212", "grok2"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "xAI's flagship model with real-time X integration.",
        "description": "Grok 2 excels at reasoning, coding, and real-time information with native access to X (Twitter) data for current events.",
        "best_for": ["Current events", "Real-time information", "Reasoning", "Code generation"],
        "limitations": ["X integration may not be available in all regions"],
        "context_window": 131072,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "parameter_count": "Unknown",
        "input_price_per_1m": Decimal("2.00"),
        "output_price_per_1m": Decimal("10.00"),
        "badge": "REAL-TIME",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "xai",
        "model_id": "grok-2-vision-latest",
        "name": "grok-2-vision",
        "display_name": "Grok 2 Vision",
        "aliases": ["grok-2-vision-1212"],
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.PREMIUM,
        "short_description": "Grok 2 with advanced vision capabilities.",
        "description": "Grok 2 Vision combines Grok 2's capabilities with image understanding for document analysis, image Q&A, and visual reasoning.",
        "best_for": ["Image analysis", "Document understanding", "Visual Q&A", "Multimodal reasoning"],
        "context_window": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "parameter_count": "Unknown",
        "input_price_per_1m": Decimal("2.00"),
        "output_price_per_1m": Decimal("10.00"),
        "badge": "VISION",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "xai",
        "model_id": "grok-beta",
        "name": "grok-beta",
        "display_name": "Grok Beta",
        "aliases": ["grok-1", "grok"],
        "category": ModelCategory.STANDARD,
        "tier": ModelTier.STANDARD,
        "short_description": "Original Grok model with witty personality.",
        "description": "Grok Beta is the original Grok model known for its witty responses and willingness to answer questions other AI might refuse.",
        "best_for": ["General chat", "Creative writing", "Uncensored responses"],
        "context_window": 8192,
        "supports_tools": False,
        "supports_streaming": True,
        "parameter_count": "314B MoE",
        "input_price_per_1m": Decimal("5.00"),
        "output_price_per_1m": Decimal("15.00"),
        "badge": "ORIGINAL",
        "is_featured": False,
        "sort_order": 3,
    },
    # =========================================================================
    # Perplexity Models (Search-Enhanced)
    # =========================================================================
    {
        "provider_name": "perplexity",
        "model_id": "sonar-pro",
        "name": "sonar-pro",
        "display_name": "Sonar Pro",
        "aliases": ["pplx-sonar-pro", "sonar-large"],
        "category": ModelCategory.SEARCH,
        "tier": ModelTier.PREMIUM,
        "short_description": "Advanced search-grounded model with citations.",
        "description": "Sonar Pro provides real-time web search with comprehensive answers, citations, and follow-up questions. Ideal for research and fact-checking.",
        "best_for": ["Research queries", "Fact-checking", "Current events", "Academic research"],
        "limitations": ["Search-focused, not ideal for creative tasks"],
        "context_window": 200000,
        "supports_tools": False,
        "supports_streaming": True,
        "supports_search": True,
        "supports_citations": True,
        "parameter_count": "Unknown",
        "input_price_per_1m": Decimal("3.00"),
        "output_price_per_1m": Decimal("15.00"),
        "badge": "SEARCH PRO",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "perplexity",
        "model_id": "sonar",
        "name": "sonar",
        "display_name": "Sonar",
        "aliases": ["pplx-sonar", "sonar-small"],
        "category": ModelCategory.SEARCH,
        "tier": ModelTier.STANDARD,
        "short_description": "Lightweight search model for quick lookups.",
        "description": "Sonar provides fast, search-grounded responses with citations at a lower cost. Great for simple fact-checking and quick research.",
        "best_for": ["Quick lookups", "Simple fact-checking", "News summaries"],
        "context_window": 128000,
        "supports_tools": False,
        "supports_streaming": True,
        "supports_search": True,
        "supports_citations": True,
        "parameter_count": "8B",
        "input_price_per_1m": Decimal("1.00"),
        "output_price_per_1m": Decimal("1.00"),
        "badge": "SEARCH",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "perplexity",
        "model_id": "sonar-reasoning",
        "name": "sonar-reasoning",
        "display_name": "Sonar Reasoning",
        "aliases": ["pplx-reasoning", "sonar-deep-research"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.PREMIUM,
        "short_description": "Deep research with multi-step reasoning.",
        "description": "Sonar Reasoning combines web search with extended thinking for complex research questions requiring multi-step analysis and synthesis.",
        "best_for": ["Complex research", "Multi-source synthesis", "In-depth analysis", "Academic questions"],
        "context_window": 128000,
        "supports_tools": False,
        "supports_streaming": True,
        "supports_search": True,
        "supports_citations": True,
        "is_reasoning_model": True,
        "parameter_count": "70B",
        "input_price_per_1m": Decimal("1.00"),
        "output_price_per_1m": Decimal("5.00"),
        "reasoning_token_price_per_1m": Decimal("5.00"),
        "badge": "DEEP RESEARCH",
        "is_featured": True,
        "sort_order": 1,
    },
    # =========================================================================
    # DeepSeek Direct (Not via Groq)
    # =========================================================================
    {
        "provider_name": "deepseek",
        "model_id": "deepseek-v3-0324",
        "name": "deepseek-v3-0324",
        "display_name": "DeepSeek V3 (0324)",
        "aliases": ["deepseek-v3-latest"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Updated V3 with improved coding and reasoning.",
        "description": "DeepSeek V3 (March 2024 update) brings improved code generation and reasoning with 128K context at unbeatable pricing.",
        "best_for": ["Code generation", "Mathematical reasoning", "General chat", "Cost-effective scaling"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "is_moe": True,
        "parameter_count": "671B MoE (37B active)",
        "input_price_per_1m": Decimal("0.14"),
        "output_price_per_1m": Decimal("0.28"),
        "badge": "UPDATED",
        "is_featured": True,
        "sort_order": 0,
    },
    {
        "provider_name": "deepseek",
        "model_id": "deepseek-chat",
        "name": "deepseek-v3",
        "display_name": "DeepSeek V3",
        "aliases": ["deepseek-chat"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.STANDARD,
        "short_description": "671B MoE model rivaling GPT-4 at fraction of cost.",
        "description": "DeepSeek V3 is a 671B MoE model (37B active) achieving GPT-4 level performance at 1/20th the cost. Excellent for coding, math, and reasoning.",
        "best_for": ["Code generation", "Mathematical reasoning", "General chat", "Cost-effective scaling"],
        "limitations": ["Based in China, potential data residency concerns"],
        "context_window": 64000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "is_moe": True,
        "parameter_count": "671B MoE (37B active)",
        "input_price_per_1m": Decimal("0.14"),
        "output_price_per_1m": Decimal("0.28"),
        "badge": "BEST VALUE",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "deepseek",
        "model_id": "deepseek-reasoner",
        "name": "deepseek-r1",
        "display_name": "DeepSeek R1",
        "aliases": ["deepseek-reasoner", "r1"],
        "category": ModelCategory.REASONING,
        "tier": ModelTier.STANDARD,
        "short_description": "Open-source reasoning model matching o1 performance.",
        "description": "DeepSeek R1 achieves 97.3% on MATH-500 with transparent chain-of-thought reasoning. First open model to match proprietary reasoning capabilities.",
        "best_for": ["Mathematical proofs", "Scientific reasoning", "Logic puzzles", "Step-by-step analysis"],
        "limitations": ["Slower due to extended thinking", "English-focused"],
        "context_window": 64000,
        "supports_tools": False,
        "supports_streaming": True,
        "is_reasoning_model": True,
        "parameter_count": "671B MoE",
        "input_price_per_1m": Decimal("0.55"),
        "output_price_per_1m": Decimal("2.19"),
        "reasoning_token_price_per_1m": Decimal("0.55"),
        "badge": "REASONING",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "deepseek",
        "model_id": "deepseek-coder",
        "name": "deepseek-coder-v2",
        "display_name": "DeepSeek Coder V2",
        "aliases": ["deepseek-coder", "coder-v2"],
        "category": ModelCategory.CODE,
        "tier": ModelTier.FREE,
        "short_description": "Specialized coding model with 128K context.",
        "description": "DeepSeek Coder V2 is a 236B MoE model specialized for code with FIM support, achieving top scores on HumanEval and MBPP benchmarks.",
        "best_for": ["Code completion", "Code review", "Debugging", "Multi-file refactoring"],
        "context_window": 128000,
        "supports_tools": False,
        "supports_streaming": True,
        "supports_fim": True,
        "is_moe": True,
        "parameter_count": "236B MoE (21B active)",
        "input_price_per_1m": Decimal("0.14"),
        "output_price_per_1m": Decimal("0.28"),
        "badge": "CODE",
        "is_featured": True,
        "sort_order": 2,
    },
    # =========================================================================
    # Qwen Models (Alibaba Cloud)
    # =========================================================================
    {
        "provider_name": "qwen",
        "model_id": "qwen3-235b-a22b",
        "name": "qwen3-235b",
        "display_name": "Qwen 3 235B",
        "aliases": ["qwen3", "qwen-3"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "Qwen 3 flagship - 235B MoE with 22B active parameters.",
        "description": "Qwen 3 is Alibaba's latest flagship using MoE architecture (235B total, 22B active) with seamless switching between thinking and non-thinking modes.",
        "best_for": ["Complex reasoning", "Multilingual tasks", "Code generation", "Long context analysis"],
        "context_window": 131072,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "is_reasoning_model": True,
        "is_moe": True,
        "parameter_count": "235B MoE (22B active)",
        "architecture": "MoE",
        "input_price_per_1m": Decimal("1.20"),
        "output_price_per_1m": Decimal("4.80"),
        "badge": "NEW",
        "is_featured": True,
        "sort_order": 0,
    },
    {
        "provider_name": "qwen",
        "model_id": "qwen-max",
        "name": "qwen-max",
        "display_name": "Qwen Max",
        "aliases": ["qwen2.5-max", "qwen-max-latest"],
        "category": ModelCategory.FLAGSHIP,
        "tier": ModelTier.PREMIUM,
        "short_description": "Alibaba's flagship model with 1M context.",
        "description": "Qwen Max is Alibaba's most capable model with 1M context window, excelling at long document analysis, code generation, and multilingual tasks.",
        "best_for": ["Long documents", "Code generation", "Chinese/English", "Enterprise applications"],
        "context_window": 1000000,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_json_mode": True,
        "parameter_count": "Unknown (Large MoE)",
        "input_price_per_1m": Decimal("1.60"),
        "output_price_per_1m": Decimal("6.40"),
        "badge": "1M CONTEXT",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "qwen",
        "model_id": "qwen-plus",
        "name": "qwen-plus",
        "display_name": "Qwen Plus",
        "aliases": ["qwen2.5-plus", "qwen-plus-latest"],
        "category": ModelCategory.STANDARD,
        "tier": ModelTier.STANDARD,
        "short_description": "Balanced model for general tasks.",
        "description": "Qwen Plus offers excellent performance for everyday tasks with 128K context and competitive pricing for the Asia-Pacific region.",
        "best_for": ["General chat", "Translation", "Summarization", "Asian market applications"],
        "context_window": 131072,
        "supports_tools": True,
        "supports_streaming": True,
        "parameter_count": "Unknown",
        "input_price_per_1m": Decimal("0.40"),
        "output_price_per_1m": Decimal("1.20"),
        "badge": "BALANCED",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "qwen",
        "model_id": "qwen-vl-max",
        "name": "qwen-vl-max",
        "display_name": "Qwen VL Max",
        "aliases": ["qwen2.5-vl-max", "qwen-vision"],
        "category": ModelCategory.MULTIMODAL,
        "tier": ModelTier.PREMIUM,
        "short_description": "Leading multimodal model for vision tasks.",
        "description": "Qwen VL Max achieves state-of-the-art on vision benchmarks with document understanding, video analysis, and visual reasoning capabilities.",
        "best_for": ["Document OCR", "Video understanding", "Visual reasoning", "Image analysis"],
        "context_window": 32768,
        "supports_tools": True,
        "supports_vision": True,
        "supports_video": True,
        "supports_streaming": True,
        "parameter_count": "72B",
        "input_price_per_1m": Decimal("2.00"),
        "output_price_per_1m": Decimal("6.00"),
        "badge": "VISION LEADER",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "qwen",
        "model_id": "qwen-coder-plus",
        "name": "qwen-coder-plus",
        "display_name": "Qwen Coder Plus",
        "aliases": ["qwen2.5-coder-32b"],
        "category": ModelCategory.CODE,
        "tier": ModelTier.STANDARD,
        "short_description": "Specialized coding model matching GPT-4 on code.",
        "description": "Qwen Coder Plus is trained on 5.5T code tokens with strong performance on HumanEval, MBPP, and LiveCodeBench.",
        "best_for": ["Code generation", "Code explanation", "Debugging", "Multi-language support"],
        "context_window": 131072,
        "supports_tools": True,
        "supports_streaming": True,
        "supports_fim": True,
        "parameter_count": "32B",
        "input_price_per_1m": Decimal("0.40"),
        "output_price_per_1m": Decimal("1.20"),
        "badge": "CODE",
        "is_featured": True,
        "sort_order": 2,
    },
    # =========================================================================
    # Embedding Models
    # =========================================================================
    {
        "provider_name": "openai",
        "model_id": "text-embedding-3-large",
        "name": "text-embedding-3-large",
        "display_name": "Text Embedding 3 Large",
        "aliases": ["embedding-3-large", "ada-3-large"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.STANDARD,
        "short_description": "Best OpenAI embedding model with 3072 dimensions.",
        "description": "text-embedding-3-large offers superior retrieval performance with 3072 dimensions. Supports dimension reduction for cost/performance tradeoff.",
        "best_for": ["Semantic search", "RAG", "Document similarity", "Clustering"],
        "context_window": 8191,
        "embedding_dimensions": 3072,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.13"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "BEST QUALITY",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "openai",
        "model_id": "text-embedding-3-small",
        "name": "text-embedding-3-small",
        "display_name": "Text Embedding 3 Small",
        "aliases": ["embedding-3-small", "ada-3-small"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.FREE,
        "short_description": "Cost-effective embedding model with 1536 dimensions.",
        "description": "text-embedding-3-small provides excellent price-performance for most use cases. 5x cheaper than large variant.",
        "best_for": ["General RAG", "Cost-effective search", "High-volume embedding"],
        "context_window": 8191,
        "embedding_dimensions": 1536,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.02"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "BEST VALUE",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "cohere",
        "model_id": "embed-english-v3.0",
        "name": "embed-english-v3",
        "display_name": "Cohere Embed English v3",
        "aliases": ["cohere-embed-v3", "embed-v3"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.STANDARD,
        "short_description": "Best-in-class English embeddings for RAG.",
        "description": "Cohere Embed v3 leads MTEB benchmarks for English with 1024 dimensions. Supports search_document and search_query input types.",
        "best_for": ["English RAG", "Enterprise search", "High-precision retrieval"],
        "context_window": 512,
        "embedding_dimensions": 1024,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.10"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "MTEB LEADER",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "cohere",
        "model_id": "embed-multilingual-v3.0",
        "name": "embed-multilingual-v3",
        "display_name": "Cohere Embed Multilingual v3",
        "aliases": ["cohere-embed-multi-v3"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.STANDARD,
        "short_description": "Multilingual embeddings supporting 100+ languages.",
        "description": "Cohere Embed Multilingual v3 provides consistent performance across 100+ languages. Great for international applications.",
        "best_for": ["Multilingual RAG", "Cross-lingual search", "Global applications"],
        "context_window": 512,
        "embedding_dimensions": 1024,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.10"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "MULTILINGUAL",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "google",
        "model_id": "text-embedding-004",
        "name": "text-embedding-004",
        "display_name": "Google Text Embedding 004",
        "aliases": ["gecko-004", "google-embed"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.FREE,
        "short_description": "Google's latest embedding model with 768 dimensions.",
        "description": "text-embedding-004 offers strong multilingual performance with task-type support for retrieval optimization.",
        "best_for": ["Multilingual search", "Vertex AI integration", "Google Cloud apps"],
        "context_window": 2048,
        "embedding_dimensions": 768,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.00"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "FREE TIER",
        "is_featured": True,
        "sort_order": 3,
    },
    {
        "provider_name": "mistral",
        "model_id": "mistral-embed",
        "name": "mistral-embed",
        "display_name": "Mistral Embed",
        "aliases": ["mistral-embedding"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.FREE,
        "short_description": "Mistral's embedding model with 1024 dimensions.",
        "description": "Mistral Embed provides strong European language support with good performance on retrieval benchmarks.",
        "best_for": ["European languages", "Cost-effective RAG", "Mistral ecosystem"],
        "context_window": 8192,
        "embedding_dimensions": 1024,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.10"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "EFFICIENT",
        "is_featured": False,
        "sort_order": 4,
    },
    # =========================================================================
    # Speech-to-Text (STT) Models
    # =========================================================================
    {
        "provider_name": "openai",
        "model_id": "whisper-1",
        "name": "whisper-1",
        "display_name": "Whisper",
        "aliases": ["whisper", "openai-whisper"],
        "category": ModelCategory.AUDIO_STT,
        "tier": ModelTier.STANDARD,
        "short_description": "OpenAI's speech recognition model.",
        "description": "Whisper provides accurate speech-to-text across 50+ languages with automatic language detection and punctuation.",
        "best_for": ["Transcription", "Voice assistants", "Meeting notes", "Multilingual audio"],
        "supports_streaming": False,
        "supported_formats": ["mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"],
        "max_file_size_mb": 25,
        "input_price_per_minute": Decimal("0.006"),
        "badge": "ACCURATE",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "google",
        "model_id": "chirp-2",
        "name": "chirp-2",
        "display_name": "Google Chirp 2",
        "aliases": ["google-stt", "chirp"],
        "category": ModelCategory.AUDIO_STT,
        "tier": ModelTier.STANDARD,
        "short_description": "Google's latest STT model with streaming support.",
        "description": "Chirp 2 offers real-time streaming transcription with speaker diarization and automatic punctuation.",
        "best_for": ["Real-time transcription", "Phone calls", "Live captioning"],
        "supports_streaming": True,
        "supports_diarization": True,
        "supported_languages": [],  # 125+ languages supported
        "input_price_per_minute": Decimal("0.016"),
        "badge": "STREAMING",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "deepgram",
        "model_id": "nova-2",
        "name": "nova-2",
        "display_name": "Deepgram Nova 2",
        "aliases": ["deepgram-nova", "nova2"],
        "category": ModelCategory.AUDIO_STT,
        "tier": ModelTier.STANDARD,
        "short_description": "Fast, accurate STT with real-time streaming.",
        "description": "Deepgram Nova 2 provides industry-leading accuracy with sub-300ms latency for real-time applications.",
        "best_for": ["Real-time voice", "Call centers", "Live events", "Low-latency apps"],
        "supports_streaming": True,
        "supports_diarization": True,
        "input_price_per_minute": Decimal("0.0043"),
        "badge": "FASTEST",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "groq",
        "model_id": "whisper-large-v3",
        "name": "whisper-large-v3-groq",
        "display_name": "Whisper Large v3 (Groq)",
        "aliases": ["groq-whisper"],
        "category": ModelCategory.AUDIO_STT,
        "tier": ModelTier.FREE,
        "short_description": "Ultra-fast Whisper on Groq hardware.",
        "description": "Whisper Large v3 on Groq LPU achieves 100x+ faster than real-time transcription at near-zero cost.",
        "best_for": ["Batch transcription", "Cost-sensitive apps", "Development"],
        "supports_streaming": False,
        "input_price_per_minute": Decimal("0.00"),
        "badge": "FREE & FAST",
        "is_featured": True,
        "sort_order": 1,
    },
    # =========================================================================
    # Text-to-Speech (TTS) Models
    # =========================================================================
    {
        "provider_name": "openai",
        "model_id": "tts-1-hd",
        "name": "tts-1-hd",
        "display_name": "TTS-1 HD",
        "aliases": ["openai-tts-hd"],
        "category": ModelCategory.AUDIO_TTS,
        "tier": ModelTier.PREMIUM,
        "short_description": "High-definition text-to-speech with natural voices.",
        "description": "TTS-1 HD generates the highest quality speech with 6 natural-sounding voices. Supports SSML and multiple output formats.",
        "best_for": ["Audiobooks", "Professional content", "High-quality voice"],
        "voices": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        "output_formats": ["mp3", "opus", "aac", "flac"],
        "supports_streaming": True,
        "output_price_per_1k_chars": Decimal("0.030"),
        "badge": "HIGHEST QUALITY",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "openai",
        "model_id": "tts-1",
        "name": "tts-1",
        "display_name": "TTS-1",
        "aliases": ["openai-tts"],
        "category": ModelCategory.AUDIO_TTS,
        "tier": ModelTier.STANDARD,
        "short_description": "Fast, cost-effective text-to-speech.",
        "description": "TTS-1 provides good quality speech at lower latency and cost. Same voices as TTS-1 HD.",
        "best_for": ["Real-time voice", "Chatbots", "Cost-sensitive apps"],
        "voices": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        "output_formats": ["mp3", "opus", "aac", "flac"],
        "supports_streaming": True,
        "output_price_per_1k_chars": Decimal("0.015"),
        "badge": "BALANCED",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "google",
        "model_id": "wavenet",
        "name": "google-wavenet",
        "display_name": "Google WaveNet",
        "aliases": ["wavenet", "google-tts"],
        "category": ModelCategory.AUDIO_TTS,
        "tier": ModelTier.PREMIUM,
        "short_description": "Google's neural TTS with 100+ voices.",
        "description": "WaveNet provides studio-quality voices in 40+ languages with SSML support, pronunciation control, and speaking rate adjustment.",
        "best_for": ["Multilingual TTS", "IVR systems", "Accessibility"],
        "supports_ssml": True,
        "supports_streaming": True,
        "languages": 40,
        "voices_count": 100,
        "output_price_per_1m_chars": Decimal("16.00"),
        "badge": "MULTILINGUAL",
        "is_featured": True,
        "sort_order": 2,
    },
    {
        "provider_name": "elevenlabs",
        "model_id": "eleven_turbo_v2_5",
        "name": "elevenlabs-turbo",
        "display_name": "ElevenLabs Turbo v2.5",
        "aliases": ["11labs", "elevenlabs"],
        "category": ModelCategory.AUDIO_TTS,
        "tier": ModelTier.PREMIUM,
        "short_description": "Ultra-realistic voice synthesis with cloning.",
        "description": "ElevenLabs Turbo offers the most natural-sounding voices with voice cloning, emotion control, and 32 languages.",
        "best_for": ["Voice cloning", "Emotional content", "Premium voice apps"],
        "supports_voice_cloning": True,
        "supports_streaming": True,
        "supports_emotion": True,
        "languages": 32,
        "output_price_per_1k_chars": Decimal("0.18"),
        "badge": "MOST REALISTIC",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "azure",
        "model_id": "neural-tts",
        "name": "azure-neural-tts",
        "display_name": "Azure Neural TTS",
        "aliases": ["azure-tts", "microsoft-tts"],
        "category": ModelCategory.AUDIO_TTS,
        "tier": ModelTier.STANDARD,
        "short_description": "Enterprise-grade TTS with 400+ voices.",
        "description": "Azure Neural TTS offers the widest voice selection with 400+ voices in 140+ languages, plus custom voice training.",
        "best_for": ["Enterprise apps", "Localization", "Custom voices"],
        "supports_custom_voice": True,
        "supports_ssml": True,
        "supports_streaming": True,
        "languages": 140,
        "voices_count": 400,
        "output_price_per_1m_chars": Decimal("15.00"),
        "badge": "ENTERPRISE",
        "is_featured": True,
        "sort_order": 3,
    },

    # =========================================================================
    # Fireworks AI Hosted Models
    # =========================================================================
    {
        "provider_name": "fireworks",
        "model_id": "accounts/fireworks/models/llama-v4-maverick",
        "name": "llama-4-maverick-fireworks",
        "display_name": "Llama 4 Maverick (Fireworks)",
        "aliases": ["fireworks-llama4", "fireworks-maverick"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Llama 4 Maverick on Fireworks fast inference.",
        "description": "Meta's Llama 4 Maverick MoE model hosted on Fireworks AI for fast, cost-effective inference.",
        "best_for": ["General chat", "Multimodal tasks", "Cost-effective inference"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "is_moe": True,
        "parameter_count": "17B active / 400B total",
        "input_price_per_1m": Decimal("0.22"),
        "output_price_per_1m": Decimal("0.88"),
        "badge": "OPEN SOURCE",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "fireworks",
        "model_id": "accounts/fireworks/models/deepseek-v3",
        "name": "deepseek-v3-fireworks",
        "display_name": "DeepSeek V3 (Fireworks)",
        "aliases": ["fireworks-deepseek"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "DeepSeek V3 on Fireworks fast inference.",
        "description": "DeepSeek V3 hosted on Fireworks AI for fast, US-based inference with competitive pricing.",
        "best_for": ["Code generation", "Reasoning", "US-hosted inference"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_streaming": True,
        "is_moe": True,
        "parameter_count": "671B MoE",
        "input_price_per_1m": Decimal("0.20"),
        "output_price_per_1m": Decimal("0.60"),
        "is_featured": True,
        "sort_order": 2,
    },

    # =========================================================================
    # AWS Bedrock Models
    # =========================================================================
    {
        "provider_name": "bedrock",
        "model_id": "anthropic.claude-sonnet-4-5-v1",
        "name": "claude-sonnet-4.5-bedrock",
        "display_name": "Claude Sonnet 4.5 (Bedrock)",
        "aliases": ["bedrock-claude-sonnet"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Claude Sonnet 4.5 on AWS Bedrock.",
        "description": "Claude Sonnet 4.5 available through AWS Bedrock with enterprise security, VPC endpoints, and AWS IAM integration.",
        "best_for": ["Enterprise apps", "AWS integration", "Code generation", "Secure deployments"],
        "context_window": 200000,
        "max_output_tokens": 16384,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "input_price_per_1m": Decimal("3.00"),
        "output_price_per_1m": Decimal("15.00"),
        "badge": "ENTERPRISE",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "bedrock",
        "model_id": "meta.llama4-maverick-v1",
        "name": "llama-4-maverick-bedrock",
        "display_name": "Llama 4 Maverick (Bedrock)",
        "aliases": ["bedrock-llama4"],
        "category": ModelCategory.CHAT,
        "tier": ModelTier.STANDARD,
        "short_description": "Llama 4 Maverick on AWS Bedrock.",
        "description": "Meta's Llama 4 Maverick available through AWS Bedrock for enterprise deployments with AWS security features.",
        "best_for": ["Enterprise apps", "AWS integration", "Multimodal tasks"],
        "context_window": 128000,
        "supports_tools": True,
        "supports_vision": True,
        "supports_streaming": True,
        "is_moe": True,
        "parameter_count": "17B active / 400B total",
        "input_price_per_1m": Decimal("0.36"),
        "output_price_per_1m": Decimal("0.94"),
        "is_featured": True,
        "sort_order": 2,
    },

    # =========================================================================
    # Additional Embedding Models
    # =========================================================================
    {
        "provider_name": "voyage",
        "model_id": "voyage-3-large",
        "name": "voyage-3-large",
        "display_name": "Voyage 3 Large",
        "aliases": ["voyage-large", "voyage-3"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.PREMIUM,
        "short_description": "Best embedding model for code and legal domains.",
        "description": "Voyage 3 Large is a premium embedding model with state-of-the-art performance on code, legal, and finance retrieval benchmarks.",
        "best_for": ["Code search", "Legal document retrieval", "Financial analysis", "High-precision RAG"],
        "context_window": 32000,
        "embedding_dimensions": 2048,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.18"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "BEST FOR CODE",
        "is_featured": True,
        "sort_order": 1,
    },
    {
        "provider_name": "jina",
        "model_id": "jina-embeddings-v3",
        "name": "jina-embeddings-v3",
        "display_name": "Jina Embeddings v3",
        "aliases": ["jina-v3", "jina-embed"],
        "category": ModelCategory.EMBEDDING,
        "tier": ModelTier.STANDARD,
        "short_description": "Multimodal embeddings with task-specific adapters.",
        "description": "Jina Embeddings v3 supports text and image embeddings with task-specific LoRA adapters for retrieval, classification, and clustering.",
        "best_for": ["Cross-modal search", "Multimodal RAG", "Classification", "Multilingual retrieval"],
        "context_window": 8192,
        "embedding_dimensions": 1024,
        "supports_batch": True,
        "input_price_per_1m": Decimal("0.02"),
        "output_price_per_1m": Decimal("0.00"),
        "badge": "MULTIMODAL",
        "is_featured": True,
        "sort_order": 1,
    },
]
