"""Add AI providers and models tables

Revision ID: 20260203_000001
Revises: 20260201_000001
Create Date: 2026-02-03 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20260203_000001"
down_revision: Union[str, None] = "20260201_000001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # AI Providers table
    op.create_table(
        "ai_providers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("docs_url", sa.String(500), nullable=True),
        sa.Column("provider_type", sa.String(50), nullable=False, server_default="llm"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("status_message", sa.Text, nullable=True),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("api_version", sa.String(50), nullable=True),
        sa.Column("required_secrets", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("supports_streaming", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("supports_function_calling", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("supports_vision", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_audio", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("default_rpm", sa.Integer, nullable=True),
        sa.Column("default_tpm", sa.Integer, nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_providers_status", "ai_providers", ["status"])
    op.create_index("ix_ai_providers_type", "ai_providers", ["provider_type"])

    # AI Models table
    op.create_table(
        "ai_models",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model_id", sa.String(200), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("display_name", sa.String(300), nullable=False),
        sa.Column("aliases", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("release_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("deprecation_date", sa.Date, nullable=True),
        sa.Column("retirement_date", sa.Date, nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="chat"),
        sa.Column("tier", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("short_description", sa.String(500), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("best_for", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("limitations", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("context_window", sa.Integer, nullable=False, server_default="8192"),
        sa.Column("max_output_tokens", sa.Integer, nullable=True),
        sa.Column("supports_tools", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_vision", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_audio", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_video", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_streaming", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("supports_json_mode", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("supports_system_prompt", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_reasoning_model", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_moe", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_fine_tunable", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_distilled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("parameter_count", sa.String(50), nullable=True),
        sa.Column("architecture", sa.String(100), nullable=True),
        sa.Column("training_cutoff", sa.String(50), nullable=True),
        sa.Column("input_price_per_1m", sa.Numeric(12, 4), nullable=True),
        sa.Column("output_price_per_1m", sa.Numeric(12, 4), nullable=True),
        sa.Column("cached_input_price_per_1m", sa.Numeric(12, 4), nullable=True),
        sa.Column("rpm_limit", sa.Integer, nullable=True),
        sa.Column("tpm_limit", sa.Integer, nullable=True),
        sa.Column("rpd_limit", sa.Integer, nullable=True),
        sa.Column("default_temperature", sa.Float, nullable=True),
        sa.Column("default_top_p", sa.Float, nullable=True),
        sa.Column("default_max_tokens", sa.Integer, nullable=True),
        sa.Column("recommended_temperature", sa.Float, nullable=True),
        sa.Column("supported_languages", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column("color", sa.String(20), nullable=True),
        sa.Column("badge", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="100"),
        sa.Column("is_featured", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_ai_models_provider", "ai_models", ["provider_id"])
    op.create_index("ix_ai_models_status", "ai_models", ["status"])
    op.create_index("ix_ai_models_category", "ai_models", ["category"])
    op.create_index("ix_ai_models_tier", "ai_models", ["tier"])
    op.create_index("ix_ai_models_featured", "ai_models", ["is_featured"])
    op.create_unique_constraint("uq_provider_model", "ai_models", ["provider_id", "model_id"])

    # Model Capabilities table
    op.create_table(
        "model_capabilities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("capability_name", sa.String(100), nullable=False),
        sa.Column("capability_value", sa.String(500), nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_capabilities_model", "model_capabilities", ["model_id"])
    op.create_index("ix_model_capabilities_name", "model_capabilities", ["capability_name"])
    op.create_unique_constraint("uq_model_capability", "model_capabilities", ["model_id", "capability_name"])

    # Vendor Capability Mappings table
    op.create_table(
        "vendor_capability_mappings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_providers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_capability", sa.String(100), nullable=False),
        sa.Column("vendor_capability", sa.String(200), nullable=False),
        sa.Column("is_supported", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("config", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_vendor_capability_provider", "vendor_capability_mappings", ["provider_id"])
    op.create_index("ix_vendor_capability_standard", "vendor_capability_mappings", ["standard_capability"])
    op.create_unique_constraint("uq_vendor_capability_mapping", "vendor_capability_mappings", ["provider_id", "standard_capability"])

    # Model Usage Stats table
    op.create_table(
        "model_usage_stats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("model_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_input_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_output_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("avg_latency_ms", sa.Integer, nullable=True),
        sa.Column("p50_latency_ms", sa.Integer, nullable=True),
        sa.Column("p95_latency_ms", sa.Integer, nullable=True),
        sa.Column("p99_latency_ms", sa.Integer, nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(12, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_model_usage_model_period", "model_usage_stats", ["model_id", "period_start"])
    op.create_index("ix_model_usage_org", "model_usage_stats", ["organization_id"])


def downgrade() -> None:
    op.drop_table("model_usage_stats")
    op.drop_table("vendor_capability_mappings")
    op.drop_table("model_capabilities")
    op.drop_table("ai_models")
    op.drop_table("ai_providers")
