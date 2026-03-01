"""Seed model_tool_support rows from existing pattern data.

For each active BuiltinTool, find all AIModels from the same provider and
create a ModelToolSupport row based on supported/excluded model patterns.

Also migrates any existing builtin_tool_model_overrides rows into the new
table's config_overrides.
"""

from __future__ import annotations

import fnmatch
import logging

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.ai_model import AIModel
from src.models.builtin_tool import BuiltinTool, BuiltinToolModelOverride
from src.models.model_tool_support import ModelToolSupport

logger = logging.getLogger(__name__)


async def seed_model_tool_support(db: AsyncSession) -> dict:
    """Populate model_tool_support from pattern columns (idempotent).

    Returns:
        Summary dict with created/skipped counts.
    """
    created = 0
    skipped = 0

    # Get all active builtin tools
    result = await db.execute(
        select(BuiltinTool).where(BuiltinTool.is_active == True)
    )
    tools = list(result.scalars().all())

    for tool in tools:
        # Get all models from the same provider
        result = await db.execute(
            select(AIModel).where(AIModel.provider_id == tool.provider_id)
        )
        models = list(result.scalars().all())

        for model in models:
            # Check if row already exists
            result = await db.execute(
                select(ModelToolSupport).where(
                    and_(
                        ModelToolSupport.model_id == model.id,
                        ModelToolSupport.builtin_tool_id == tool.id,
                    )
                )
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue

            # Evaluate patterns
            is_supported = _evaluate_patterns(
                model.model_id,
                tool.supported_model_patterns or [],
                tool.excluded_model_patterns or [],
            )

            row = ModelToolSupport(
                model_id=model.id,
                builtin_tool_id=tool.id,
                is_supported=is_supported,
                source="seed",
            )
            db.add(row)
            created += 1

    # Migrate existing overrides into config_overrides
    migrated = await _migrate_overrides(db)

    await db.flush()

    return {
        "created": created,
        "skipped": skipped,
        "overrides_migrated": migrated,
    }


def _evaluate_patterns(
    model_id: str,
    supported_patterns: list[str],
    excluded_patterns: list[str],
) -> bool:
    """Evaluate supported/excluded patterns to determine support flag."""
    # No patterns = all models from provider supported
    if not supported_patterns:
        # Still check exclusions
        if excluded_patterns:
            excluded = any(
                fnmatch.fnmatch(model_id, p) for p in excluded_patterns
            )
            if excluded:
                return False
        return True

    # Must match at least one supported pattern
    matches = any(fnmatch.fnmatch(model_id, p) for p in supported_patterns)
    if not matches:
        return False

    # Check exclusions
    if excluded_patterns:
        excluded = any(
            fnmatch.fnmatch(model_id, p) for p in excluded_patterns
        )
        if excluded:
            return False

    return True


async def _migrate_overrides(db: AsyncSession) -> int:
    """Migrate builtin_tool_model_overrides into model_tool_support config_overrides."""
    migrated = 0

    result = await db.execute(select(BuiltinToolModelOverride))
    overrides = list(result.scalars().all())

    for override in overrides:
        # Find matching model_tool_support rows by pattern
        result = await db.execute(
            select(ModelToolSupport).where(
                ModelToolSupport.builtin_tool_id == override.builtin_tool_id
            )
        )
        mts_rows = list(result.scalars().all())

        for mts in mts_rows:
            # Load the model to get model_id string
            model = await db.get(AIModel, mts.model_id)
            if not model:
                continue

            if fnmatch.fnmatch(model.model_id, override.model_pattern):
                if override.config_overrides:
                    mts.config_overrides = {
                        **mts.config_overrides,
                        **override.config_overrides,
                    }
                if override.api_config_overrides:
                    mts.api_config_overrides = {
                        **mts.api_config_overrides,
                        **override.api_config_overrides,
                    }
                if not override.is_enabled:
                    mts.is_supported = False
                migrated += 1

    return migrated
