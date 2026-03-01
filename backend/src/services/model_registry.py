"""Model Registry Service - CRUD operations for AI models and providers."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, or_, select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import NotFoundError, ValidationError
from src.models.ai_model import (
    AIProvider,
    AIModel,
    ModelUsageStats,
    ProviderStatus,
    ModelStatus,
    ModelCategory,
    ModelTier,
    DEFAULT_PROVIDERS,
    SAMPLE_MODELS,
)


class ModelRegistryService:
    """Service for managing AI providers and models."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Provider Operations ====================

    async def list_providers(
        self,
        status: ProviderStatus | None = None,
        provider_type: str | None = None,
        include_models: bool = False,
    ) -> list[AIProvider]:
        """List all providers with optional filtering."""
        query = select(AIProvider)

        if status:
            query = query.where(AIProvider.status == status)
        if provider_type:
            query = query.where(AIProvider.provider_type == provider_type)

        if include_models:
            query = query.options(selectinload(AIProvider.models))

        query = query.order_by(AIProvider.sort_order, AIProvider.name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_provider(
        self,
        provider_id: uuid.UUID | None = None,
        name: str | None = None,
        include_models: bool = False,
    ) -> AIProvider:
        """Get a provider by ID or name."""
        query = select(AIProvider)

        if provider_id:
            query = query.where(AIProvider.id == provider_id)
        elif name:
            query = query.where(AIProvider.name == name)
        else:
            raise ValidationError("Either provider_id or name must be provided")

        if include_models:
            query = query.options(selectinload(AIProvider.models))

        result = await self.db.execute(query)
        provider = result.scalar_one_or_none()

        if not provider:
            raise NotFoundError(f"Provider not found: {provider_id or name}")

        return provider

    async def create_provider(self, data: dict[str, Any]) -> AIProvider:
        """Create a new provider."""
        provider = AIProvider(**data)
        self.db.add(provider)
        await self.db.flush()
        return provider

    async def update_provider(
        self,
        provider_id: uuid.UUID,
        data: dict[str, Any],
    ) -> AIProvider:
        """Update a provider."""
        provider = await self.get_provider(provider_id=provider_id)

        for key, value in data.items():
            if hasattr(provider, key):
                setattr(provider, key, value)

        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def update_provider_status(
        self,
        provider_id: uuid.UUID,
        status: ProviderStatus,
        status_message: str | None = None,
    ) -> AIProvider:
        """Update provider status (enable/disable/maintenance)."""
        provider = await self.get_provider(provider_id=provider_id)
        provider.status = status
        provider.status_message = status_message
        await self.db.flush()
        await self.db.refresh(provider)
        return provider

    async def delete_provider(self, provider_id: uuid.UUID) -> None:
        """Delete a provider and all its models."""
        provider = await self.get_provider(provider_id=provider_id)
        await self.db.delete(provider)
        await self.db.flush()

    # ==================== Model Operations ====================

    async def list_models(
        self,
        provider_id: uuid.UUID | None = None,
        provider_name: str | None = None,
        status: ModelStatus | None = None,
        category: ModelCategory | None = None,
        tier: ModelTier | None = None,
        supports_tools: bool | None = None,
        supports_vision: bool | None = None,
        is_reasoning_model: bool | None = None,
        is_featured: bool | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[AIModel], int]:
        """List models with filtering and pagination."""
        query = select(AIModel).options(selectinload(AIModel.provider))

        # Apply filters
        if provider_id:
            query = query.where(AIModel.provider_id == provider_id)
        if provider_name:
            query = query.join(AIProvider).where(AIProvider.name == provider_name)
        if status:
            query = query.where(AIModel.status == status)
        if category:
            query = query.where(AIModel.category == category)
        if tier:
            query = query.where(AIModel.tier == tier)
        if supports_tools is not None:
            query = query.where(AIModel.supports_tools == supports_tools)
        if supports_vision is not None:
            query = query.where(AIModel.supports_vision == supports_vision)
        if is_reasoning_model is not None:
            query = query.where(AIModel.is_reasoning_model == is_reasoning_model)
        if is_featured is not None:
            query = query.where(AIModel.is_featured == is_featured)

        # Search in name, display_name, description, aliases
        if search:
            search_term = f"%{search.lower()}%"
            query = query.where(
                or_(
                    func.lower(AIModel.name).like(search_term),
                    func.lower(AIModel.display_name).like(search_term),
                    func.lower(AIModel.short_description).like(search_term),
                    func.lower(AIModel.model_id).like(search_term),
                )
            )

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.execute(count_query)
        total_count = total.scalar() or 0

        # Apply ordering and pagination
        query = query.order_by(
            AIModel.is_featured.desc(),
            AIModel.sort_order,
            AIModel.display_name,
        )
        query = query.offset(offset).limit(limit)

        result = await self.db.execute(query)
        models = list(result.scalars().all())

        return models, total_count

    async def get_model(
        self,
        model_id: uuid.UUID | None = None,
        model_identifier: str | None = None,
        provider_name: str | None = None,
    ) -> AIModel:
        """Get a model by ID or model_id string."""
        query = select(AIModel).options(selectinload(AIModel.provider))

        if model_id:
            query = query.where(AIModel.id == model_id)
        elif model_identifier:
            # Search by model_id or alias
            if provider_name:
                query = query.join(AIProvider).where(
                    and_(
                        AIProvider.name == provider_name,
                        or_(
                            AIModel.model_id == model_identifier,
                            AIModel.name == model_identifier,
                            AIModel.aliases.contains([model_identifier]),
                        )
                    )
                )
            else:
                query = query.where(
                    or_(
                        AIModel.model_id == model_identifier,
                        AIModel.name == model_identifier,
                        AIModel.aliases.contains([model_identifier]),
                    )
                )
        else:
            raise ValidationError("Either model_id or model_identifier must be provided")

        result = await self.db.execute(query)
        model = result.scalar_one_or_none()

        if not model:
            raise NotFoundError(f"Model not found: {model_id or model_identifier}")

        return model

    async def create_model(self, data: dict[str, Any]) -> AIModel:
        """Create a new model."""
        # Resolve provider if name provided
        if "provider_name" in data:
            provider = await self.get_provider(name=data.pop("provider_name"))
            data["provider_id"] = provider.id

        model = AIModel(**data)
        self.db.add(model)
        await self.db.flush()

        # Auto-populate model-tool support rows
        from src.services.model_tool_support_service import ModelToolSupportService
        mts_service = ModelToolSupportService(self.db)
        await mts_service.populate_for_model(model)

        return model

    async def update_model(
        self,
        model_id: uuid.UUID,
        data: dict[str, Any],
    ) -> AIModel:
        """Update a model."""
        model = await self.get_model(model_id=model_id)

        for key, value in data.items():
            if hasattr(model, key) and key not in ("id", "created_at", "provider_id"):
                setattr(model, key, value)

        await self.db.flush()
        return model

    async def update_model_status(
        self,
        model_id: uuid.UUID,
        status: ModelStatus,
        deprecation_date: datetime | None = None,
        retirement_date: datetime | None = None,
    ) -> AIModel:
        """Update model status (enable/disable/deprecate)."""
        model = await self.get_model(model_id=model_id)
        model.status = status

        if deprecation_date:
            model.deprecation_date = deprecation_date
        if retirement_date:
            model.retirement_date = retirement_date

        await self.db.flush()
        return model

    async def delete_model(self, model_id: uuid.UUID) -> None:
        """Delete a model."""
        model = await self.get_model(model_id=model_id)
        await self.db.delete(model)
        await self.db.flush()

    async def bulk_update_model_status(
        self,
        provider_id: uuid.UUID | None = None,
        current_status: ModelStatus | None = None,
        new_status: ModelStatus = ModelStatus.DISABLED,
    ) -> int:
        """Bulk update model status (e.g., disable all models for a provider)."""
        query = update(AIModel).values(status=new_status)

        if provider_id:
            query = query.where(AIModel.provider_id == provider_id)
        if current_status:
            query = query.where(AIModel.status == current_status)

        result = await self.db.execute(query)
        await self.db.flush()
        return result.rowcount

    # ==================== Model Discovery ====================

    async def get_models_for_task(
        self,
        task_type: str,
        require_tools: bool = False,
        require_vision: bool = False,
        max_context_needed: int | None = None,
        budget_tier: ModelTier | None = None,
    ) -> list[AIModel]:
        """Get recommended models for a specific task type."""
        # Map task types to categories and capabilities
        task_mappings = {
            "chat": {"category": ModelCategory.CHAT},
            "coding": {"category": ModelCategory.CODING},
            "reasoning": {"is_reasoning_model": True},
            "analysis": {"category": ModelCategory.CHAT, "is_reasoning_model": True},
            "vision": {"supports_vision": True},
            "embedding": {"category": ModelCategory.EMBEDDING},
            "translation": {"category": ModelCategory.TRANSLATION},
        }

        filters = task_mappings.get(task_type, {})

        query = select(AIModel).options(selectinload(AIModel.provider)).where(
            AIModel.status == ModelStatus.ACTIVE
        )

        # Apply task-specific filters
        if "category" in filters:
            query = query.where(AIModel.category == filters["category"])
        if filters.get("is_reasoning_model"):
            query = query.where(AIModel.is_reasoning_model == True)
        if filters.get("supports_vision"):
            query = query.where(AIModel.supports_vision == True)

        # Apply additional requirements
        if require_tools:
            query = query.where(AIModel.supports_tools == True)
        if require_vision:
            query = query.where(AIModel.supports_vision == True)
        if max_context_needed:
            query = query.where(AIModel.context_window >= max_context_needed)
        if budget_tier:
            query = query.where(AIModel.tier == budget_tier)

        # Only active providers
        query = query.join(AIProvider).where(AIProvider.status == ProviderStatus.ACTIVE)

        # Order by featured, then sort_order
        query = query.order_by(
            AIModel.is_featured.desc(),
            AIModel.sort_order,
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_default_model(
        self,
        provider_name: str | None = None,
        category: ModelCategory = ModelCategory.CHAT,
    ) -> AIModel | None:
        """Get the default model for a provider or category."""
        query = select(AIModel).options(selectinload(AIModel.provider)).where(
            and_(
                AIModel.status == ModelStatus.ACTIVE,
                AIModel.is_default == True,
            )
        )

        if provider_name:
            query = query.join(AIProvider).where(AIProvider.name == provider_name)
        else:
            query = query.where(AIModel.category == category)

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def resolve_model_alias(
        self,
        alias: str,
        provider_name: str | None = None,
    ) -> str | None:
        """Resolve a model alias to the actual model_id."""
        try:
            model = await self.get_model(
                model_identifier=alias,
                provider_name=provider_name,
            )
            return model.model_id
        except NotFoundError:
            return None

    # ==================== Statistics ====================

    async def get_provider_stats(
        self,
        provider_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Get statistics for a provider."""
        provider = await self.get_provider(provider_id=provider_id, include_models=True)

        # Count models by status
        status_counts = {}
        category_counts = {}

        for model in provider.models:
            status_counts[model.status.value] = status_counts.get(model.status.value, 0) + 1
            category_counts[model.category.value] = category_counts.get(model.category.value, 0) + 1

        return {
            "provider_id": str(provider.id),
            "provider_name": provider.name,
            "total_models": len(provider.models),
            "active_models": status_counts.get("active", 0),
            "models_by_status": status_counts,
            "models_by_category": category_counts,
        }

    async def get_model_comparison(
        self,
        model_ids: list[uuid.UUID],
    ) -> list[dict[str, Any]]:
        """Get comparison data for multiple models."""
        query = select(AIModel).options(selectinload(AIModel.provider)).where(
            AIModel.id.in_(model_ids)
        )

        result = await self.db.execute(query)
        models = result.scalars().all()

        return [
            {
                "id": str(m.id),
                "name": m.display_name,
                "provider": m.provider.display_name,
                "category": m.category.value,
                "context_window": m.context_window,
                "supports_tools": m.supports_tools,
                "supports_vision": m.supports_vision,
                "is_reasoning_model": m.is_reasoning_model,
                "input_price": float(m.input_price_per_1m) if m.input_price_per_1m else None,
                "output_price": float(m.output_price_per_1m) if m.output_price_per_1m else None,
                "best_for": m.best_for,
                "limitations": m.limitations,
            }
            for m in models
        ]

    # ==================== Initialization ====================

    async def initialize_defaults(self) -> dict[str, int]:
        """Initialize default providers and sample models."""
        providers_created = 0
        models_created = 0

        # Create default providers
        for provider_data in DEFAULT_PROVIDERS:
            # Check if provider exists
            query = select(AIProvider).where(AIProvider.name == provider_data["name"])
            result = await self.db.execute(query)
            existing = result.scalar_one_or_none()

            if not existing:
                provider = AIProvider(**provider_data)
                self.db.add(provider)
                providers_created += 1

        await self.db.flush()

        # Valid AIModel column names (used to filter seed data)
        model_columns = {c.key for c in AIModel.__table__.columns}
        model_columns.discard("id")  # Auto-generated
        model_columns.discard("created_at")
        model_columns.discard("updated_at")

        # Create sample models
        for model_data in SAMPLE_MODELS:
            provider_name = model_data.get("provider_name")

            # Separate valid DB columns from extra metadata
            db_fields = {}
            extra_fields = {}
            for k, v in model_data.items():
                if k == "provider_name":
                    continue
                elif k in model_columns:
                    db_fields[k] = v
                else:
                    extra_fields[k] = v

            # Store extra fields in the config JSONB column
            if extra_fields:
                from decimal import Decimal as _Decimal
                config = db_fields.get("config") or {}
                # Convert Decimal to float for JSON serialization
                for ek, ev in extra_fields.items():
                    config[ek] = float(ev) if isinstance(ev, _Decimal) else ev
                db_fields["config"] = config

            # Get provider
            query = select(AIProvider).where(AIProvider.name == provider_name)
            result = await self.db.execute(query)
            provider = result.scalar_one_or_none()

            if provider:
                # Check if model exists
                query = select(AIModel).where(
                    and_(
                        AIModel.provider_id == provider.id,
                        AIModel.model_id == db_fields["model_id"],
                    )
                )
                result = await self.db.execute(query)
                existing = result.scalar_one_or_none()

                if not existing:
                    model = AIModel(provider_id=provider.id, **db_fields)
                    self.db.add(model)
                    models_created += 1

        await self.db.flush()

        return {
            "providers_created": providers_created,
            "models_created": models_created,
        }
