"""Avatar model for customizable AI personas."""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base


class Avatar(Base):
    """Avatar configuration for visual AI personas.

    Supports multiple avatar types:
    - 3D models (GLB/GLTF)
    - HeyGen LiveAvatar integration
    - Custom video avatars
    - Simple animated avatars
    """

    __tablename__ = "avatars"

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="general", nullable=False)

    # Avatar type
    avatar_type: Mapped[str] = mapped_column(String(50), default="3d", nullable=False)

    # Visual appearance
    appearance: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # 3D Model configuration (for type=3d)
    model_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # HeyGen integration (for type=heygen)
    heygen_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Voice configuration
    voice_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Personality traits (affects behavior)
    personality: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Default system prompt additions for this avatar
    system_prompt_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Greeting messages
    greetings: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Thumbnail/preview
    thumbnail_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    preview_video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Tags for categorization
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_public: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Avatar(id={self.id}, name={self.name}, type={self.avatar_type})>"


# Pre-defined system avatars
SYSTEM_AVATARS = [
    {
        "name": "Professional Assistant",
        "description": "A professional, business-focused AI assistant",
        "category": "general",
        "avatar_type": "3d",
        "appearance": {
            "gender": "female",
            "style": "professional",
            "outfit": "business",
        },
        "personality": {
            "tone": "professional",
            "empathy_level": "medium",
            "patience": "high",
        },
        "greetings": [
            "Hello! How can I assist you today?",
            "Welcome! I'm here to help with any questions you may have.",
        ],
        "tags": ["business", "professional", "default"],
    },
    {
        "name": "HR Assistant",
        "description": "Human Resources specialist for employee support",
        "category": "hr",
        "avatar_type": "3d",
        "appearance": {
            "gender": "female",
            "style": "approachable",
            "outfit": "smart_casual",
        },
        "personality": {
            "tone": "friendly",
            "empathy_level": "high",
            "patience": "very_high",
        },
        "system_prompt_prefix": "You are an HR specialist. Be empathetic, understanding, and maintain confidentiality. Help with employee questions about policies, benefits, and workplace matters.",
        "greetings": [
            "Hi there! I'm your HR assistant. How can I help you today?",
            "Hello! Feel free to ask me anything about HR policies or employee matters.",
        ],
        "tags": ["hr", "employee", "policies"],
    },
    {
        "name": "Finance Advisor",
        "description": "Financial expert for budgeting and reporting",
        "category": "finance",
        "avatar_type": "3d",
        "appearance": {
            "gender": "male",
            "style": "professional",
            "outfit": "formal",
        },
        "personality": {
            "tone": "professional",
            "empathy_level": "medium",
            "assertiveness": "high",
        },
        "system_prompt_prefix": "You are a finance expert. Provide accurate, data-driven financial advice. Be precise with numbers and always encourage proper financial practices.",
        "greetings": [
            "Hello! I'm your financial advisor. How can I help with your financial queries?",
            "Welcome! Let's discuss your financial questions.",
        ],
        "tags": ["finance", "accounting", "budget"],
    },
    {
        "name": "Tech Support",
        "description": "Technical support specialist for IT issues",
        "category": "technical",
        "avatar_type": "3d",
        "appearance": {
            "gender": "neutral",
            "style": "casual",
            "outfit": "tech_casual",
        },
        "personality": {
            "tone": "friendly",
            "patience": "very_high",
            "technical_depth": "high",
        },
        "system_prompt_prefix": "You are a technical support specialist. Help users troubleshoot issues step by step. Be patient and explain technical concepts in simple terms when needed.",
        "greetings": [
            "Hi! I'm here to help with any technical issues. What's going on?",
            "Hey there! Let's solve your tech problem together.",
        ],
        "tags": ["tech", "support", "it", "troubleshooting"],
    },
    {
        "name": "Sales Representative",
        "description": "Sales expert for product inquiries",
        "category": "sales",
        "avatar_type": "3d",
        "appearance": {
            "gender": "male",
            "style": "energetic",
            "outfit": "business_casual",
        },
        "personality": {
            "tone": "enthusiastic",
            "persuasiveness": "high",
            "friendliness": "high",
        },
        "system_prompt_prefix": "You are a sales representative. Be enthusiastic and helpful. Focus on understanding customer needs and matching them with the right solutions. Never be pushy.",
        "greetings": [
            "Hi! Great to meet you! What brings you here today?",
            "Hello! I'd love to help you find what you're looking for!",
        ],
        "tags": ["sales", "products", "customer"],
    },
    {
        "name": "Executive Assistant",
        "description": "High-level assistant for executives",
        "category": "executive",
        "avatar_type": "3d",
        "appearance": {
            "gender": "female",
            "style": "elegant",
            "outfit": "executive",
        },
        "personality": {
            "tone": "formal",
            "efficiency": "very_high",
            "discretion": "very_high",
        },
        "system_prompt_prefix": "You are an executive assistant. Be efficient, discreet, and professional. Prioritize time-sensitive matters and provide concise, actionable information.",
        "greetings": [
            "Good day. How may I assist you?",
            "Hello. What can I help you with today?",
        ],
        "tags": ["executive", "management", "scheduling"],
    },
]
