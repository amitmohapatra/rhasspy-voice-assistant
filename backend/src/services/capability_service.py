"""Capability Service - Business logic for capability management.

This service provides:
1. Capability validation before tool execution
2. Tool filtering based on model capabilities
3. Dynamic tool registration
4. Capability-to-model matching

Architecture:
- System manages: capability definitions, vendor mappings, model capabilities
- End users: just use tools - no configuration needed
"""

from __future__ import annotations

import fnmatch
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ValidationError, NotFoundError, AuthorizationError
from src.models.capability import (
    CapabilityDefinition,
    CapabilityType,
    ModelCapability,
    ToolCapabilityRequirement,
    VendorCapabilityMapping,
    DEFAULT_CAPABILITY_DEFINITIONS,
    DEFAULT_VENDOR_MAPPINGS,
)
from src.models.ai_model import AIModel, AIProvider
from src.models.tool import Tool


class CapabilityService:
    """Service for managing capabilities across the platform."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._cache: dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutes

    # ==================== Capability Definition Management ====================

    async def seed_default_capabilities(self) -> None:
        """Seed default capability definitions.

        Called during database initialization or migration.
        Only creates capabilities that don't exist.
        """
        for cap_def in DEFAULT_CAPABILITY_DEFINITIONS:
            existing = await self.db.execute(
                select(CapabilityDefinition).where(
                    CapabilityDefinition.capability_type == cap_def["capability_type"]
                )
            )
            if not existing.scalar_one_or_none():
                capability = CapabilityDefinition(**cap_def)
                self.db.add(capability)

        await self.db.commit()

    async def seed_vendor_mappings(self, provider_id: UUID, provider_name: str) -> None:
        """Seed vendor capability mappings for a provider.

        Args:
            provider_id: The provider's database ID
            provider_name: The provider's name (e.g., "openai", "anthropic")
        """
        mappings = DEFAULT_VENDOR_MAPPINGS.get(provider_name, {})

        for capability_type, mapping_data in mappings.items():
            existing = await self.db.execute(
                select(VendorCapabilityMapping).where(
                    VendorCapabilityMapping.provider_id == str(provider_id),
                    VendorCapabilityMapping.capability_type == capability_type,
                )
            )
            if not existing.scalar_one_or_none():
                mapping = VendorCapabilityMapping(
                    provider_id=str(provider_id),
                    capability_type=capability_type,
                    vendor_name=mapping_data.get("vendor_name", capability_type.value),
                    invocation_method=mapping_data.get("invocation_method", "parameter"),
                    api_config=mapping_data.get("api_config", {}),
                    default_params=mapping_data.get("default_params", {}),
                    supported_model_patterns=mapping_data.get("supported_model_patterns", ["*"]),
                    excluded_model_patterns=mapping_data.get("excluded_model_patterns", []),
                    notes=mapping_data.get("notes"),
                )
                self.db.add(mapping)

        await self.db.commit()

    async def list_capability_definitions(
        self,
        category: str | None = None,
        include_beta: bool = True,
        include_deprecated: bool = False,
    ) -> list[CapabilityDefinition]:
        """List all capability definitions.

        Args:
            category: Filter by category
            include_beta: Include beta capabilities
            include_deprecated: Include deprecated capabilities
        """
        query = select(CapabilityDefinition)

        if category:
            query = query.where(CapabilityDefinition.category == category)
        if not include_beta:
            query = query.where(CapabilityDefinition.is_beta == False)
        if not include_deprecated:
            query = query.where(CapabilityDefinition.is_deprecated == False)

        query = query.order_by(CapabilityDefinition.sort_order, CapabilityDefinition.display_name)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_capability_definition(
        self,
        capability_type: CapabilityType,
        updates: dict[str, Any],
    ) -> CapabilityDefinition:
        """Update a capability definition.

        Updates display info, config schema, vendor mappings, etc.
        but cannot change the capability_type itself.
        """
        result = await self.db.execute(
            select(CapabilityDefinition).where(
                CapabilityDefinition.capability_type == capability_type
            )
        )
        capability = result.scalar_one_or_none()

        if not capability:
            raise NotFoundError(f"Capability {capability_type} not found")

        # Allowed fields to update
        allowed_fields = {
            "display_name", "description", "icon", "category",
            "config_schema", "default_config", "vendor_mappings",
            "is_premium", "is_beta", "is_deprecated", "sort_order",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(capability, field, value)

        capability.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(capability)

        return capability

    # ==================== Model Capability Management ====================

    async def get_model_capabilities(self, model_id: UUID) -> list[ModelCapability]:
        """Get all capabilities for a model."""
        result = await self.db.execute(
            select(ModelCapability).where(
                ModelCapability.model_id == str(model_id)
            )
        )
        return list(result.scalars().all())

    async def set_model_capability(
        self,
        model_id: UUID,
        capability_type: CapabilityType,
        is_enabled: bool = True,
        config: dict | None = None,
        vendor_implementation: dict | None = None,
    ) -> ModelCapability:
        """Set a capability for a model.

        Configures which models support which capabilities.
        """
        # Check if capability already exists
        result = await self.db.execute(
            select(ModelCapability).where(
                ModelCapability.model_id == str(model_id),
                ModelCapability.capability_type == capability_type,
            )
        )
        capability = result.scalar_one_or_none()

        if capability:
            capability.is_enabled = is_enabled
            if config is not None:
                capability.config = config
            if vendor_implementation is not None:
                capability.vendor_implementation = vendor_implementation
            capability.updated_at = datetime.utcnow()
        else:
            capability = ModelCapability(
                model_id=str(model_id),
                capability_type=capability_type,
                is_enabled=is_enabled,
                config=config or {},
                vendor_implementation=vendor_implementation or {},
            )
            self.db.add(capability)

        await self.db.commit()
        await self.db.refresh(capability)

        # Clear cache
        self._clear_model_cache(model_id)

        return capability

    async def bulk_set_model_capabilities(
        self,
        model_id: UUID,
        capabilities: list[dict],
    ) -> list[ModelCapability]:
        """Set multiple capabilities for a model at once.

        Args:
            model_id: The model ID
            capabilities: List of dicts with capability_type, is_enabled, config
        """
        results = []
        for cap in capabilities:
            result = await self.set_model_capability(
                model_id=model_id,
                capability_type=cap["capability_type"],
                is_enabled=cap.get("is_enabled", True),
                config=cap.get("config"),
                vendor_implementation=cap.get("vendor_implementation"),
            )
            results.append(result)

        return results

    async def auto_detect_model_capabilities(
        self,
        model_id: UUID,
    ) -> list[ModelCapability]:
        """Auto-detect capabilities for a model based on vendor mappings.

        Uses pattern matching from vendor capability mappings to automatically
        set capabilities for a model.
        """
        # Get the model and its provider
        result = await self.db.execute(
            select(AIModel).options(
                selectinload(AIModel.provider)
            ).where(AIModel.id == str(model_id))
        )
        model = result.scalar_one_or_none()

        if not model:
            raise NotFoundError(f"Model {model_id} not found")

        # Get vendor mappings for this provider
        result = await self.db.execute(
            select(VendorCapabilityMapping).where(
                VendorCapabilityMapping.provider_id == str(model.provider_id)
            )
        )
        vendor_mappings = list(result.scalars().all())

        detected_capabilities = []

        for mapping in vendor_mappings:
            if not mapping.is_available:
                continue

            # Check if model matches supported patterns
            model_name = model.model_id
            matches_supported = any(
                fnmatch.fnmatch(model_name, pattern)
                for pattern in (mapping.supported_model_patterns or ["*"])
            )

            # Check if model is excluded
            is_excluded = any(
                fnmatch.fnmatch(model_name, pattern)
                for pattern in (mapping.excluded_model_patterns or [])
            )

            if matches_supported and not is_excluded:
                capability = await self.set_model_capability(
                    model_id=model_id,
                    capability_type=mapping.capability_type,
                    is_enabled=True,
                    vendor_implementation={
                        "vendor_name": mapping.vendor_name,
                        "invocation_method": mapping.invocation_method,
                        "api_config": mapping.api_config,
                    },
                )
                detected_capabilities.append(capability)

        return detected_capabilities

    # ==================== Capability Validation ====================

    async def model_supports_capability(
        self,
        model_id: UUID,
        capability_type: CapabilityType,
    ) -> bool:
        """Check if a model supports a specific capability."""
        cache_key = f"model_cap:{model_id}:{capability_type}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        result = await self.db.execute(
            select(ModelCapability).where(
                ModelCapability.model_id == str(model_id),
                ModelCapability.capability_type == capability_type,
                ModelCapability.is_enabled == True,
            )
        )
        supports = result.scalar_one_or_none() is not None

        self._cache[cache_key] = supports
        return supports

    async def validate_tool_for_model(
        self,
        tool_id: UUID,
        model_id: UUID,
    ) -> tuple[bool, list[str]]:
        """Validate if a tool can be used with a model.

        Returns:
            Tuple of (is_valid, list_of_missing_capabilities)
        """
        # Get tool's required capabilities
        result = await self.db.execute(
            select(ToolCapabilityRequirement).where(
                ToolCapabilityRequirement.tool_id == str(tool_id),
                ToolCapabilityRequirement.is_required == True,
            )
        )
        requirements = list(result.scalars().all())

        if not requirements:
            # No specific requirements - tool works with function_calling
            return await self.model_supports_capability(
                model_id, CapabilityType.FUNCTION_CALLING
            ), []

        # Check each required capability
        missing = []
        for req in requirements:
            if not await self.model_supports_capability(model_id, req.capability_type):
                missing.append(req.capability_type.value)

        return len(missing) == 0, missing

    async def get_compatible_tools(
        self,
        model_id: UUID,
        tool_ids: list[UUID] | None = None,
    ) -> list[Tool]:
        """Get tools that are compatible with a model.

        Args:
            model_id: The model to check compatibility for
            tool_ids: Optional specific tool IDs to check
        """
        # Get model's capabilities
        model_caps = await self.get_model_capabilities(model_id)
        model_cap_types = {cap.capability_type for cap in model_caps if cap.is_enabled}

        # Build tool query
        query = select(Tool).options(
            selectinload(Tool.capability_requirements)
        ).where(
            Tool.is_active == True,
        )

        if tool_ids:
            query = query.where(Tool.id.in_([str(t) for t in tool_ids]))

        result = await self.db.execute(query)
        tools = list(result.scalars().all())

        # Filter by capability requirements
        compatible_tools = []
        for tool in tools:
            required_caps = [
                req.capability_type
                for req in tool.capability_requirements
                if req.is_required
            ]

            # If no specific requirements, check for function_calling
            if not required_caps:
                if CapabilityType.FUNCTION_CALLING in model_cap_types:
                    compatible_tools.append(tool)
            elif all(cap in model_cap_types for cap in required_caps):
                compatible_tools.append(tool)

        return compatible_tools

    async def filter_tools_by_capabilities(
        self,
        tools: list[Tool],
        model_id: UUID,
    ) -> tuple[list[Tool], list[dict]]:
        """Filter tools and return both compatible and incompatible with reasons.

        Returns:
            Tuple of (compatible_tools, incompatible_tools_with_reasons)
        """
        model_caps = await self.get_model_capabilities(model_id)
        model_cap_types = {cap.capability_type for cap in model_caps if cap.is_enabled}

        compatible = []
        incompatible = []

        for tool in tools:
            is_valid, missing = await self.validate_tool_for_model(
                UUID(tool.id), model_id
            )

            if is_valid:
                compatible.append(tool)
            else:
                incompatible.append({
                    "tool": tool,
                    "missing_capabilities": missing,
                    "reason": f"Model doesn't support: {', '.join(missing)}",
                })

        return compatible, incompatible

    # ==================== Tool Capability Requirements ====================

    async def set_tool_capability_requirement(
        self,
        tool_id: UUID,
        capability_type: CapabilityType,
        is_required: bool = True,
        reason: str | None = None,
    ) -> ToolCapabilityRequirement:
        """Set a capability requirement for a tool."""
        result = await self.db.execute(
            select(ToolCapabilityRequirement).where(
                ToolCapabilityRequirement.tool_id == str(tool_id),
                ToolCapabilityRequirement.capability_type == capability_type,
            )
        )
        requirement = result.scalar_one_or_none()

        if requirement:
            requirement.is_required = is_required
            requirement.reason = reason
        else:
            requirement = ToolCapabilityRequirement(
                tool_id=str(tool_id),
                capability_type=capability_type,
                is_required=is_required,
                reason=reason,
            )
            self.db.add(requirement)

        await self.db.commit()
        await self.db.refresh(requirement)

        return requirement

    async def infer_tool_capabilities(self, tool: Tool) -> list[CapabilityType]:
        """Infer what capabilities a tool likely needs based on its definition.

        This is a helper for when tools are created to suggest capabilities.
        """
        inferred = [CapabilityType.FUNCTION_CALLING]  # All tools need this

        schema = tool.schema_definition or {}
        params = schema.get("parameters", {}).get("properties", {})
        description = (schema.get("description") or "").lower()

        # Infer based on parameter names and types
        for param_name, param_def in params.items():
            param_type = param_def.get("type", "")
            param_desc = (param_def.get("description") or "").lower()

            # Vision capability
            if any(kw in param_name.lower() or kw in param_desc for kw in
                   ["image", "screenshot", "photo", "picture", "visual"]):
                if CapabilityType.VISION not in inferred:
                    inferred.append(CapabilityType.VISION)

            # File handling
            if any(kw in param_name.lower() or kw in param_desc for kw in
                   ["file", "document", "pdf", "upload"]):
                if CapabilityType.FILE_SEARCH not in inferred:
                    inferred.append(CapabilityType.FILE_SEARCH)

            # Code execution
            if any(kw in param_name.lower() or kw in param_desc for kw in
                   ["code", "script", "execute", "run", "python"]):
                if CapabilityType.CODE_INTERPRETER not in inferred:
                    inferred.append(CapabilityType.CODE_INTERPRETER)

        # Infer from description
        if any(kw in description for kw in ["search the web", "internet search", "web search"]):
            if CapabilityType.WEB_SEARCH not in inferred:
                inferred.append(CapabilityType.WEB_SEARCH)

        return inferred

    # ==================== Vendor Mapping Management ====================

    async def get_vendor_capability_mapping(
        self,
        provider_id: UUID,
        capability_type: CapabilityType,
    ) -> VendorCapabilityMapping | None:
        """Get vendor-specific mapping for a capability."""
        result = await self.db.execute(
            select(VendorCapabilityMapping).where(
                VendorCapabilityMapping.provider_id == str(provider_id),
                VendorCapabilityMapping.capability_type == capability_type,
            )
        )
        return result.scalar_one_or_none()

    async def update_vendor_capability_mapping(
        self,
        provider_id: UUID,
        capability_type: CapabilityType,
        updates: dict[str, Any],
    ) -> VendorCapabilityMapping:
        """Update vendor-specific capability mapping."""
        mapping = await self.get_vendor_capability_mapping(provider_id, capability_type)

        if not mapping:
            raise NotFoundError(
                f"Vendor mapping for {capability_type} not found for provider {provider_id}"
            )

        allowed_fields = {
            "vendor_name", "api_config", "invocation_method", "default_params",
            "supported_model_patterns", "excluded_model_patterns", "is_available", "notes",
        }

        for field, value in updates.items():
            if field in allowed_fields:
                setattr(mapping, field, value)

        mapping.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(mapping)

        return mapping

    # ==================== Helper Methods ====================

    def _clear_model_cache(self, model_id: UUID) -> None:
        """Clear cache entries for a model."""
        prefix = f"model_cap:{model_id}:"
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for key in keys_to_delete:
            del self._cache[key]

    async def get_capability_summary(self, model_id: UUID) -> dict[str, Any]:
        """Get a summary of capabilities for a model.

        Returns a user-friendly summary of what a model can do.
        """
        capabilities = await self.get_model_capabilities(model_id)

        # Get capability definitions for display names
        definitions = await self.list_capability_definitions()
        def_map = {d.capability_type: d for d in definitions}

        enabled = []
        disabled = []

        for cap in capabilities:
            cap_def = def_map.get(cap.capability_type)
            cap_info = {
                "type": cap.capability_type.value,
                "display_name": cap_def.display_name if cap_def else cap.capability_type.value,
                "description": cap_def.description if cap_def else None,
                "icon": cap_def.icon if cap_def else None,
                "config": cap.config,
            }

            if cap.is_enabled:
                enabled.append(cap_info)
            else:
                disabled.append(cap_info)

        return {
            "model_id": str(model_id),
            "enabled_capabilities": enabled,
            "disabled_capabilities": disabled,
            "total_enabled": len(enabled),
            "total_disabled": len(disabled),
        }
