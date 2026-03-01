"""Model-Tool Support Service — manages explicit model/tool compatibility."""

from __future__ import annotations

import fnmatch
from typing import Any
from uuid import UUID

from sqlalchemy import select, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.ai_model import AIModel
from src.models.builtin_tool import BuiltinTool
from src.models.model_tool_support import ModelToolSupport


class ModelToolSupportService:
    """Service for managing model-tool support mappings."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def populate_for_model(self, model: AIModel) -> int:
        """Auto-create tool support rows when a new model is registered.

        Evaluates all active tools from the model's provider and creates
        rows based on their supported/excluded patterns.

        Returns:
            Number of rows created.
        """
        result = await self.db.execute(
            select(BuiltinTool).where(
                BuiltinTool.provider_id == str(model.provider_id),
                BuiltinTool.is_active == True,
            )
        )
        tools = list(result.scalars().all())

        created = 0
        for tool in tools:
            # Check if already exists
            existing = await self.db.execute(
                select(ModelToolSupport).where(
                    and_(
                        ModelToolSupport.model_id == model.id,
                        ModelToolSupport.builtin_tool_id == tool.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            is_supported = self._evaluate_patterns(
                model.model_id,
                tool.supported_model_patterns or [],
                tool.excluded_model_patterns or [],
            )

            row = ModelToolSupport(
                model_id=model.id,
                builtin_tool_id=tool.id,
                is_supported=is_supported,
                source="auto",
            )
            self.db.add(row)
            created += 1

        await self.db.flush()
        return created

    async def populate_for_tool(self, tool: BuiltinTool) -> int:
        """Auto-create model support rows when a new tool is registered.

        Returns:
            Number of rows created.
        """
        result = await self.db.execute(
            select(AIModel).where(AIModel.provider_id == tool.provider_id)
        )
        models = list(result.scalars().all())

        created = 0
        for model in models:
            existing = await self.db.execute(
                select(ModelToolSupport).where(
                    and_(
                        ModelToolSupport.model_id == model.id,
                        ModelToolSupport.builtin_tool_id == tool.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            is_supported = self._evaluate_patterns(
                model.model_id,
                tool.supported_model_patterns or [],
                tool.excluded_model_patterns or [],
            )

            row = ModelToolSupport(
                model_id=model.id,
                builtin_tool_id=tool.id,
                is_supported=is_supported,
                source="auto",
            )
            self.db.add(row)
            created += 1

        await self.db.flush()
        return created

    async def get_supported_tools(
        self,
        model_id: UUID,
    ) -> list[dict[str, Any]]:
        """Get all supported tools for a model via JOIN.

        Returns tool dicts with merged config overrides.
        """
        result = await self.db.execute(
            select(ModelToolSupport)
            .options(selectinload(ModelToolSupport.builtin_tool))
            .where(
                and_(
                    ModelToolSupport.model_id == model_id,
                    ModelToolSupport.is_supported == True,
                )
            )
        )
        entries = list(result.scalars().all())

        tools = []
        for entry in entries:
            bt = entry.builtin_tool
            if not bt or not bt.is_active or bt.is_deprecated:
                continue

            tool_data = bt.to_dict()
            tool_data["is_available"] = True

            # Merge config overrides
            if entry.config_overrides:
                tool_data["default_config"] = {
                    **tool_data.get("default_config", {}),
                    **entry.config_overrides,
                }
            if entry.api_config_overrides:
                tool_data["api_config"] = {
                    **tool_data.get("api_config", {}),
                    **entry.api_config_overrides,
                }

            tools.append(tool_data)

        return tools

    async def get_supported_models(
        self,
        tool_id: str,
    ) -> list[dict[str, Any]]:
        """Get all models that support a given tool."""
        result = await self.db.execute(
            select(ModelToolSupport)
            .options(selectinload(ModelToolSupport.model))
            .where(
                and_(
                    ModelToolSupport.builtin_tool_id == tool_id,
                    ModelToolSupport.is_supported == True,
                )
            )
        )
        entries = list(result.scalars().all())

        return [
            {
                "model_id": str(entry.model.id),
                "model_name": entry.model.display_name,
                "model_identifier": entry.model.model_id,
                "is_supported": entry.is_supported,
                "config_overrides": entry.config_overrides,
            }
            for entry in entries
            if entry.model
        ]

    async def set_support(
        self,
        model_id: UUID,
        tool_id: str,
        is_supported: bool,
        config_overrides: dict | None = None,
        api_config_overrides: dict | None = None,
    ) -> ModelToolSupport:
        """Upsert a single model-tool support row."""
        result = await self.db.execute(
            select(ModelToolSupport).where(
                and_(
                    ModelToolSupport.model_id == model_id,
                    ModelToolSupport.builtin_tool_id == tool_id,
                )
            )
        )
        row = result.scalar_one_or_none()

        if row:
            row.is_supported = is_supported
            row.source = "api"
            if config_overrides is not None:
                row.config_overrides = config_overrides
            if api_config_overrides is not None:
                row.api_config_overrides = api_config_overrides
        else:
            row = ModelToolSupport(
                model_id=model_id,
                builtin_tool_id=tool_id,
                is_supported=is_supported,
                config_overrides=config_overrides or {},
                api_config_overrides=api_config_overrides or {},
                source="api",
            )
            self.db.add(row)

        await self.db.flush()
        return row

    async def bulk_set_support(
        self,
        model_id: UUID,
        tool_flags: dict[str, bool],
    ) -> int:
        """Bulk update support flags for a model.

        Args:
            model_id: The model UUID
            tool_flags: Mapping of tool_id -> is_supported

        Returns:
            Number of rows upserted.
        """
        count = 0
        for tool_id, is_supported in tool_flags.items():
            await self.set_support(model_id, tool_id, is_supported)
            count += 1
        return count

    async def rebuild_for_provider(self, provider_id: str) -> dict[str, int]:
        """Re-resolve all patterns for a provider.

        Deletes all 'seed'/'auto' rows for the provider's models and
        re-creates them from current pattern data.
        """
        # Get all models for this provider
        result = await self.db.execute(
            select(AIModel).where(AIModel.provider_id == provider_id)
        )
        models = list(result.scalars().all())
        model_ids = [m.id for m in models]

        if not model_ids:
            return {"deleted": 0, "created": 0}

        # Delete auto/seed rows for these models
        del_result = await self.db.execute(
            delete(ModelToolSupport).where(
                and_(
                    ModelToolSupport.model_id.in_(model_ids),
                    ModelToolSupport.source.in_(["seed", "auto"]),
                )
            )
        )
        deleted = del_result.rowcount

        # Re-create
        created = 0
        for model in models:
            created += await self.populate_for_model(model)

        return {"deleted": deleted, "created": created}

    @staticmethod
    def _evaluate_patterns(
        model_id: str,
        supported_patterns: list[str],
        excluded_patterns: list[str],
    ) -> bool:
        """Evaluate supported/excluded patterns."""
        if not supported_patterns:
            if excluded_patterns:
                return not any(
                    fnmatch.fnmatch(model_id, p) for p in excluded_patterns
                )
            return True

        matches = any(fnmatch.fnmatch(model_id, p) for p in supported_patterns)
        if not matches:
            return False

        if excluded_patterns:
            return not any(
                fnmatch.fnmatch(model_id, p) for p in excluded_patterns
            )

        return True
