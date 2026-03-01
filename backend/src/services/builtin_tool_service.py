"""Built-in Tool Service - Database-driven vendor tool management.

All operations are database-driven. No hardcoded tools.
Admins can add/edit/remove built-in tools via API without code deployment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.builtin_tool import BuiltinTool, BuiltinToolModelOverride, ToolCategory
from src.models.capability import CapabilityType, ModelCapability
from src.models.ai_model import AIModel, AIProvider
from src.models.model_tool_support import ModelToolSupport


class BuiltinToolService:
    """Service for managing vendor built-in tools - fully database-driven."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== CRUD Operations ====================

    async def create_builtin_tool(
        self,
        provider_id: UUID,
        name: str,
        display_name: str,
        capability_type: CapabilityType,
        description: str | None = None,
        icon: str | None = None,
        category: ToolCategory = ToolCategory.TOOLS,
        config_schema: dict | None = None,
        default_config: dict | None = None,
        api_config: dict | None = None,
        is_preview: bool = False,
        is_beta: bool = False,
        is_always_on: bool = False,
        supported_model_patterns: list[str] | None = None,
        excluded_model_patterns: list[str] | None = None,
        docs_url: str | None = None,
        sort_order: int = 0,
    ) -> BuiltinTool:
        """Create a new built-in tool for a provider."""
        tool = BuiltinTool(
            provider_id=str(provider_id),
            name=name,
            display_name=display_name,
            capability_type=capability_type,
            description=description,
            icon=icon,
            category=category,
            config_schema=config_schema or {},
            default_config=default_config or {},
            api_config=api_config or {},
            is_preview=is_preview,
            is_beta=is_beta,
            is_always_on=is_always_on,
            supported_model_patterns=supported_model_patterns or [],
            excluded_model_patterns=excluded_model_patterns or [],
            docs_url=docs_url,
            sort_order=sort_order,
        )
        self.db.add(tool)
        await self.db.commit()
        await self.db.refresh(tool)

        # Auto-populate model-tool support rows
        from src.services.model_tool_support_service import ModelToolSupportService
        mts_service = ModelToolSupportService(self.db)
        await mts_service.populate_for_tool(tool)
        await self.db.commit()

        return tool

    async def update_builtin_tool(
        self,
        tool_id: UUID,
        updates: dict[str, Any],
    ) -> BuiltinTool:
        """Update a built-in tool."""
        result = await self.db.execute(
            select(BuiltinTool).where(BuiltinTool.id == str(tool_id))
        )
        tool = result.scalar_one_or_none()

        if not tool:
            raise ValueError(f"Built-in tool {tool_id} not found")

        # Allowed fields to update
        allowed_fields = {
            "display_name", "description", "icon", "category",
            "config_schema", "default_config", "api_config",
            "is_active", "is_preview", "is_beta", "is_deprecated", "is_always_on",
            "supported_model_patterns", "excluded_model_patterns",
            "docs_url", "examples", "sort_order",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(tool, field, value)

        tool.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(tool)
        return tool

    async def delete_builtin_tool(self, tool_id: UUID) -> bool:
        """Delete a built-in tool."""
        result = await self.db.execute(
            select(BuiltinTool).where(BuiltinTool.id == str(tool_id))
        )
        tool = result.scalar_one_or_none()

        if not tool:
            return False

        await self.db.delete(tool)
        await self.db.commit()
        return True

    async def get_builtin_tool(self, tool_id: UUID) -> BuiltinTool | None:
        """Get a built-in tool by ID."""
        result = await self.db.execute(
            select(BuiltinTool).where(BuiltinTool.id == str(tool_id))
        )
        return result.scalar_one_or_none()

    async def list_builtin_tools(
        self,
        provider_id: UUID | None = None,
        capability_type: CapabilityType | None = None,
        category: ToolCategory | None = None,
        include_inactive: bool = False,
        include_deprecated: bool = False,
    ) -> list[BuiltinTool]:
        """List built-in tools with optional filters."""
        query = select(BuiltinTool)

        if provider_id:
            query = query.where(BuiltinTool.provider_id == str(provider_id))
        if capability_type:
            query = query.where(BuiltinTool.capability_type == capability_type)
        if category:
            query = query.where(BuiltinTool.category == category)
        if not include_inactive:
            query = query.where(BuiltinTool.is_active == True)
        if not include_deprecated:
            query = query.where(BuiltinTool.is_deprecated == False)

        query = query.order_by(BuiltinTool.sort_order, BuiltinTool.display_name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ==================== Tool Availability for Models ====================

    async def get_available_tools_for_model(
        self,
        model_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get all available built-in tools for a specific model.

        Uses the model_tool_support join table instead of fnmatch patterns.
        Returns only tools that are:
        1. Marked as supported in model_tool_support
        2. Active and not deprecated
        3. Have capabilities the model supports
        """
        from src.services.model_tool_support_service import ModelToolSupportService

        # Get model with provider for vendor name
        result = await self.db.execute(
            select(AIModel).options(
                selectinload(AIModel.provider)
            ).where(AIModel.id == str(model_id))
        )
        model = result.scalar_one_or_none()
        if not model:
            return []

        # Get model's capabilities
        result = await self.db.execute(
            select(ModelCapability).where(
                ModelCapability.model_id == str(model_id),
                ModelCapability.is_enabled == True,
            )
        )
        model_capabilities = {cap.capability_type for cap in result.scalars().all()}

        # Use JOIN-based lookup
        mts_service = ModelToolSupportService(self.db)
        tools = await mts_service.get_supported_tools(model_id)

        # Filter by capability and add vendor name
        available = []
        for tool_data in tools:
            cap_type_str = tool_data.get("capability_type")
            if cap_type_str:
                try:
                    cap_type = CapabilityType(cap_type_str)
                    if cap_type not in model_capabilities:
                        continue
                except ValueError:
                    pass

            tool_data["vendor"] = model.provider.name if model.provider else "unknown"
            available.append(tool_data)

        return available

    # ==================== Provider Tool Management ====================

    async def get_tools_by_provider(
        self,
        provider_id: UUID,
    ) -> list[BuiltinTool]:
        """Get all built-in tools for a provider."""
        return await self.list_builtin_tools(provider_id=provider_id)

    async def get_tools_by_provider_name(
        self,
        provider_name: str,
    ) -> list[BuiltinTool]:
        """Get all built-in tools by provider name."""
        result = await self.db.execute(
            select(AIProvider).where(AIProvider.name == provider_name)
        )
        provider = result.scalar_one_or_none()

        if not provider:
            return []

        return await self.list_builtin_tools(provider_id=UUID(provider.id))

    # ==================== Model Overrides ====================

    async def create_model_override(
        self,
        builtin_tool_id: UUID,
        model_pattern: str,
        is_enabled: bool = True,
        config_overrides: dict | None = None,
        api_config_overrides: dict | None = None,
    ) -> BuiltinToolModelOverride:
        """Create a model-specific override for a built-in tool."""
        override = BuiltinToolModelOverride(
            builtin_tool_id=str(builtin_tool_id),
            model_pattern=model_pattern,
            is_enabled=is_enabled,
            config_overrides=config_overrides or {},
            api_config_overrides=api_config_overrides or {},
        )
        self.db.add(override)
        await self.db.commit()
        await self.db.refresh(override)
        return override

    async def update_model_override(
        self,
        override_id: UUID,
        updates: dict[str, Any],
    ) -> BuiltinToolModelOverride:
        """Update a model override."""
        result = await self.db.execute(
            select(BuiltinToolModelOverride).where(
                BuiltinToolModelOverride.id == str(override_id)
            )
        )
        override = result.scalar_one_or_none()

        if not override:
            raise ValueError(f"Override {override_id} not found")

        for field in ["is_enabled", "config_overrides", "api_config_overrides"]:
            if field in updates:
                setattr(override, field, updates[field])

        override.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(override)
        return override

    async def delete_model_override(self, override_id: UUID) -> bool:
        """Delete a model override."""
        result = await self.db.execute(
            select(BuiltinToolModelOverride).where(
                BuiltinToolModelOverride.id == str(override_id)
            )
        )
        override = result.scalar_one_or_none()

        if not override:
            return False

        await self.db.delete(override)
        await self.db.commit()
        return True

    # ==================== Bulk Operations ====================

    async def bulk_create_tools(
        self,
        tools: list[dict[str, Any]],
    ) -> list[BuiltinTool]:
        """Bulk create built-in tools."""
        created = []
        for tool_data in tools:
            tool = await self.create_builtin_tool(**tool_data)
            created.append(tool)
        return created

    async def import_tools_for_provider(
        self,
        provider_id: UUID,
        tools_config: list[dict[str, Any]],
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        """Import tools configuration for a provider.

        Args:
            provider_id: The provider ID
            tools_config: List of tool configurations
            replace_existing: If True, delete existing tools first

        Returns:
            Summary of import operation
        """
        if replace_existing:
            # Delete existing tools for this provider
            result = await self.db.execute(
                select(BuiltinTool).where(BuiltinTool.provider_id == str(provider_id))
            )
            existing = list(result.scalars().all())
            for tool in existing:
                await self.db.delete(tool)
            await self.db.commit()

        created = []
        updated = []
        errors = []

        for tool_config in tools_config:
            try:
                # Check if tool already exists
                result = await self.db.execute(
                    select(BuiltinTool).where(
                        BuiltinTool.provider_id == str(provider_id),
                        BuiltinTool.name == tool_config["name"],
                    )
                )
                existing_tool = result.scalar_one_or_none()

                if existing_tool:
                    # Update existing
                    await self.update_builtin_tool(UUID(existing_tool.id), tool_config)
                    updated.append(tool_config["name"])
                else:
                    # Create new
                    tool_config["provider_id"] = provider_id
                    if "capability_type" in tool_config and isinstance(tool_config["capability_type"], str):
                        tool_config["capability_type"] = CapabilityType(tool_config["capability_type"])
                    if "category" in tool_config and isinstance(tool_config["category"], str):
                        tool_config["category"] = ToolCategory(tool_config["category"])

                    await self.create_builtin_tool(**tool_config)
                    created.append(tool_config["name"])

            except Exception as e:
                errors.append({"name": tool_config.get("name", "unknown"), "error": str(e)})

        return {
            "created": created,
            "updated": updated,
            "errors": errors,
            "total_created": len(created),
            "total_updated": len(updated),
            "total_errors": len(errors),
        }
