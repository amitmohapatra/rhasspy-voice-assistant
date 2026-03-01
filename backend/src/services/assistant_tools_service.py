"""Assistant Tools Service - Get available tools for assistant creation.

This service provides the logic for:
1. Getting all available tools for a specific model
2. Separating built-in (vendor) tools from custom tools
3. Filtering based on model capabilities
4. Returning UI-ready tool configurations

All built-in tools are now DB-driven via BuiltinToolService.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_model import AIModel
from src.models.capability import (
    CapabilityType,
    ModelCapability,
    ToolCapabilityRequirement,
)
from src.models.tool import Tool
from src.services.builtin_tool_service import BuiltinToolService
from src.services.capability_service import CapabilityService


class AssistantToolsService:
    """Service to get available tools for assistant creation."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.capability_service = CapabilityService(db)
        self.builtin_tool_service = BuiltinToolService(db)

    async def get_available_tools_for_model(
        self,
        model_id: UUID,
    ) -> dict[str, Any]:
        """Get all available tools for a model during assistant creation.

        This is the main method called when a user selects a model.
        It returns:
        - Built-in tools (vendor-provided) that the model supports
        - Custom tools (user-created) that are compatible with the model

        Args:
            model_id: The selected AI model

        Returns:
            Dict with builtin_tools, custom_tools, and model_capabilities
        """
        # Get model info
        result = await self.db.execute(
            select(AIModel).options(
                selectinload(AIModel.provider)
            ).where(AIModel.id == str(model_id))
        )
        model = result.scalar_one_or_none()

        if not model:
            return {
                "builtin_tools": [],
                "custom_tools": [],
                "model_capabilities": [],
                "error": "Model not found"
            }

        # Get model's capabilities
        model_capabilities = await self.capability_service.get_model_capabilities(model_id)
        enabled_capabilities = {
            cap.capability_type for cap in model_capabilities if cap.is_enabled
        }

        # Get vendor name
        vendor_name = model.provider.name if model.provider else "unknown"

        # 1. Get Built-in Tools from DB
        builtin_tools = await self._get_builtin_tools_for_model(model_id)

        # 2. Get Custom Tools (filtered by compatibility)
        custom_tools = await self._get_compatible_custom_tools(
            model_id=model_id,
            enabled_capabilities=enabled_capabilities,
        )

        # 3. Format capabilities for UI
        capabilities_info = [
            {
                "type": cap.capability_type.value,
                "is_enabled": cap.is_enabled,
                "config": cap.config,
            }
            for cap in model_capabilities
        ]

        return {
            "model_id": str(model_id),
            "model_name": model.display_name or model.name,
            "vendor": vendor_name,
            "builtin_tools": builtin_tools,
            "custom_tools": custom_tools,
            "model_capabilities": capabilities_info,
            "total_available_tools": len(builtin_tools) + len(custom_tools),
        }

    async def _get_builtin_tools_for_model(
        self,
        model_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get vendor built-in tools from DB based on model capabilities."""
        return await self.builtin_tool_service.get_available_tools_for_model(model_id)

    async def _get_compatible_custom_tools(
        self,
        model_id: UUID,
        enabled_capabilities: set[CapabilityType],
    ) -> list[dict[str, Any]]:
        """Get custom tools that are compatible with the model."""
        # Get all active custom tools
        result = await self.db.execute(
            select(Tool).options(
                selectinload(Tool.capability_requirements)
            ).where(
                Tool.is_active == True,
            )
        )
        all_tools = list(result.scalars().all())

        compatible_tools = []
        incompatible_tools = []

        for tool in all_tools:
            # Get required capabilities for this tool
            required_caps = [
                req.capability_type
                for req in (tool.capability_requirements or [])
                if req.is_required
            ]

            # If no specific requirements, tool just needs function_calling
            if not required_caps:
                required_caps = [CapabilityType.FUNCTION_CALLING]

            # Check if model has all required capabilities
            missing_caps = [
                cap for cap in required_caps
                if cap not in enabled_capabilities
            ]

            tool_info = {
                "id": str(tool.id),
                "name": tool.name,
                "display_name": tool.display_name,
                "description": tool.description,
                "icon": tool.icon,
                "category": tool.category,
                "type": tool.type,
                "is_builtin": False,
                "schema_definition": tool.schema_definition,
                "required_capabilities": [cap.value for cap in required_caps],
            }

            if not missing_caps:
                tool_info["is_available"] = True
                compatible_tools.append(tool_info)
            else:
                tool_info["is_available"] = False
                tool_info["missing_capabilities"] = [cap.value for cap in missing_caps]
                tool_info["unavailable_reason"] = f"Model doesn't support: {', '.join(cap.value for cap in missing_caps)}"
                incompatible_tools.append(tool_info)

        # Return compatible tools first, then incompatible (for UI to show why)
        return compatible_tools + incompatible_tools

    async def get_tools_for_assistant(
        self,
        assistant_id: UUID,
    ) -> dict[str, Any]:
        """Get the tools configured for an existing assistant.

        Used when viewing/editing an assistant.
        """
        from src.models.assistant import Assistant

        result = await self.db.execute(
            select(Assistant).where(Assistant.id == str(assistant_id))
        )
        assistant = result.scalar_one_or_none()

        if not assistant:
            return {"error": "Assistant not found"}

        # Get the model's available tools
        available = await self.get_available_tools_for_model(
            model_id=UUID(assistant.model_id) if assistant.model_id else None,
        )

        # Mark which tools are enabled for this assistant
        enabled_tool_ids = set(assistant.tool_ids or [])
        enabled_builtin = set(assistant.settings.get("builtin_tools", []))

        for tool in available["builtin_tools"]:
            tool["is_enabled"] = tool["name"] in enabled_builtin

        for tool in available["custom_tools"]:
            tool["is_enabled"] = tool["id"] in enabled_tool_ids

        return {
            **available,
            "assistant_id": str(assistant_id),
            "assistant_name": assistant.name,
        }

    async def validate_tools_for_model(
        self,
        model_id: UUID,
        builtin_tool_names: list[str],
        custom_tool_ids: list[str],
    ) -> dict[str, Any]:
        """Validate that selected tools are compatible with the model.

        Called before saving an assistant to ensure valid configuration.
        """
        result = await self.db.execute(
            select(AIModel).options(
                selectinload(AIModel.provider)
            ).where(AIModel.id == str(model_id))
        )
        model = result.scalar_one_or_none()

        if not model:
            return {"valid": False, "error": "Model not found"}

        # Get model capabilities
        model_capabilities = await self.capability_service.get_model_capabilities(model_id)
        enabled_caps = {cap.capability_type for cap in model_capabilities if cap.is_enabled}

        errors = []

        # Validate built-in tools via DB
        available_builtin = await self.builtin_tool_service.get_available_tools_for_model(model_id)
        available_names = {t["name"] for t in available_builtin}

        for tool_name in builtin_tool_names:
            if tool_name not in available_names:
                # Check if the tool exists at all for this provider
                provider_tools = await self.builtin_tool_service.get_tools_by_provider_name(
                    model.provider.name if model.provider else "unknown"
                )
                tool_exists = any(t.name == tool_name for t in provider_tools)

                if tool_exists:
                    errors.append({
                        "tool": tool_name,
                        "type": "builtin",
                        "error": f"Tool '{tool_name}' is not compatible with this model",
                    })
                else:
                    errors.append({
                        "tool": tool_name,
                        "type": "builtin",
                        "error": f"Tool '{tool_name}' not available for provider",
                    })

        # Validate custom tools
        for tool_id in custom_tool_ids:
            is_valid, missing = await self.capability_service.validate_tool_for_model(
                tool_id=UUID(tool_id),
                model_id=model_id,
            )
            if not is_valid:
                errors.append({
                    "tool": tool_id,
                    "type": "custom",
                    "error": f"Missing capabilities: {', '.join(missing)}",
                })

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "validated_builtin_tools": [t for t in builtin_tool_names if not any(e["tool"] == t for e in errors)],
            "validated_custom_tools": [t for t in custom_tool_ids if not any(e["tool"] == t for e in errors)],
        }
