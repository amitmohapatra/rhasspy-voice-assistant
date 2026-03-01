"""Tool Resolver - Resolves tool references to provider-native payloads.

Orchestrates the conversion of tool_ids (mix of builtin names and custom UUIDs)
into provider-native tool definitions using ToolAdapters and database queries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.llm.tool_adapters import CohereAdapter, ToolAdapterRegistry


@dataclass
class ToolResolverResult:
    """Result of tool resolution containing provider-native payloads."""

    tools: list[dict[str, Any]] = field(default_factory=list)
    connectors: list[dict[str, Any]] | None = None  # Cohere connectors (separate API param)


class ToolResolver:
    """Resolves tool references to provider-native format.

    Takes a list of tool refs (builtin names + custom UUIDs), queries the DB
    for their definitions, and converts each through the appropriate ToolAdapter.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.registry = ToolAdapterRegistry()

    async def resolve(
        self,
        tool_refs: list[str],
        provider: str,
        model: str,
    ) -> ToolResolverResult:
        """Resolve tool references to provider-native payloads.

        Args:
            tool_refs: List of builtin tool names and/or custom tool UUIDs
            provider: Provider name (e.g. "openai", "anthropic")
            model: Model identifier for compatibility filtering

        Returns:
            ToolResolverResult with provider-native tool payloads
        """
        # 1. Partition refs into builtin names vs custom UUIDs
        builtin_names: list[str] = []
        custom_ids: list[UUID] = []
        for ref in tool_refs:
            try:
                custom_ids.append(UUID(ref))
            except ValueError:
                builtin_names.append(ref)

        adapter = self.registry.get(provider)
        result = ToolResolverResult()

        # 2. Resolve builtin tools
        if builtin_names:
            await self._resolve_builtins(
                builtin_names, provider, model, adapter, result
            )

        # 3. Resolve custom tools
        if custom_ids:
            await self._resolve_customs(
                custom_ids, adapter, result
            )

        return result

    async def _resolve_builtins(
        self,
        names: list[str],
        provider: str,
        model: str,
        adapter: Any,
        result: ToolResolverResult,
    ) -> None:
        """Query builtin_tools via model_tool_support JOIN and convert through adapter."""
        from src.models.builtin_tool import BuiltinTool
        from src.models.ai_model import AIProvider, AIModel
        from src.models.model_tool_support import ModelToolSupport

        # Find the provider
        provider_row = (
            await self.db.execute(
                select(AIProvider).where(AIProvider.name == provider)
            )
        ).scalar_one_or_none()

        if not provider_row:
            return

        # Find the model UUID by model_id string
        model_row = (
            await self.db.execute(
                select(AIModel).where(
                    and_(
                        AIModel.provider_id == provider_row.id,
                        AIModel.model_id == model,
                    )
                )
            )
        ).scalar_one_or_none()

        if not model_row:
            # Fallback: query tools directly by name (no model_tool_support filtering)
            query = select(BuiltinTool).where(
                BuiltinTool.provider_id == str(provider_row.id),
                BuiltinTool.name.in_(names),
                BuiltinTool.is_active == True,
            )
            rows = (await self.db.execute(query)).scalars().all()
            for bt in rows:
                api_config = dict(bt.api_config) if bt.api_config else {}
                default_config = dict(bt.default_config) if bt.default_config else None
                converted = adapter.convert_builtin(bt.name, api_config, default_config)
                if converted is None:
                    continue
                if isinstance(adapter, CohereAdapter) and converted.get("__cohere_connector__"):
                    converted.pop("__cohere_connector__")
                    if result.connectors is None:
                        result.connectors = []
                    result.connectors.append(converted)
                else:
                    result.tools.append(converted)
            return

        # JOIN query: get tools that are supported for this model
        query = (
            select(BuiltinTool, ModelToolSupport)
            .join(
                ModelToolSupport,
                and_(
                    ModelToolSupport.builtin_tool_id == BuiltinTool.id,
                    ModelToolSupport.model_id == model_row.id,
                    ModelToolSupport.is_supported == True,
                ),
            )
            .where(
                BuiltinTool.provider_id == str(provider_row.id),
                BuiltinTool.name.in_(names),
                BuiltinTool.is_active == True,
            )
        )
        rows = (await self.db.execute(query)).all()

        for bt, mts in rows:
            api_config = dict(bt.api_config) if bt.api_config else {}
            default_config = dict(bt.default_config) if bt.default_config else None

            # Apply model-tool-specific overrides
            if mts.api_config_overrides:
                api_config.update(mts.api_config_overrides)

            converted = adapter.convert_builtin(bt.name, api_config, default_config)
            if converted is None:
                continue

            # Handle Cohere connectors (separate API parameter)
            if isinstance(adapter, CohereAdapter) and converted.get("__cohere_connector__"):
                converted.pop("__cohere_connector__")
                if result.connectors is None:
                    result.connectors = []
                result.connectors.append(converted)
            else:
                result.tools.append(converted)

    async def _resolve_customs(
        self,
        ids: list[UUID],
        adapter: Any,
        result: ToolResolverResult,
    ) -> None:
        """Query custom tools table and convert through adapter."""
        from src.models.tool import Tool

        query = select(Tool).where(
            Tool.id.in_(ids),
            Tool.is_active == True,
        )
        rows = (await self.db.execute(query)).scalars().all()

        for tool in rows:
            schema = tool.schema_definition or {}
            func = schema.get("function", schema)
            name = func.get("name", tool.name)
            description = func.get("description", tool.description or "")

            # Extract parameters — handles 3 storage formats:
            # 1. {"function": {"name":..., "parameters": {...}}} → nested OpenAI format
            # 2. {"name":..., "parameters": {...}} → flat with parameters key
            # 3. {"type": "object", "properties": {...}} → raw JSON Schema (IS the parameters)
            if "parameters" in func:
                parameters = func["parameters"]
            elif "properties" in func:
                parameters = func
            else:
                parameters = {"type": "object", "properties": {}}

            converted = adapter.convert_custom(name, description, parameters)
            result.tools.append(converted)
