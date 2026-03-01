"""Voice preset service for CRUD operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError
from src.models.voice_preset import VoicePreset
from src.schemas.voice_preset import VoicePresetCreate, VoicePresetUpdate


class VoicePresetService:
    """Service for voice preset CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, user_id: UUID, data: VoicePresetCreate) -> VoicePreset:
        """Create a new voice preset."""
        if data.is_default:
            await self._unset_default(user_id, data.type)

        preset = VoicePreset(
            user_id=user_id,
            type=data.type,
            name=data.name,
            config=data.config,
            is_default=data.is_default,
        )
        self.db.add(preset)
        await self.db.flush()
        await self.db.refresh(preset)
        return preset

    async def get(self, preset_id: UUID, user_id: UUID) -> VoicePreset:
        """Get a voice preset by ID."""
        result = await self.db.execute(
            select(VoicePreset).where(
                and_(VoicePreset.id == preset_id, VoicePreset.user_id == user_id)
            )
        )
        preset = result.scalar_one_or_none()
        if not preset:
            raise NotFoundError(
                message="Voice preset not found",
                resource="voice_preset",
                details={"preset_id": str(preset_id)},
            )
        return preset

    async def list(
        self,
        user_id: UUID,
        type_filter: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[VoicePreset], int]:
        """List voice presets with optional type filter and pagination."""
        conditions = [VoicePreset.user_id == user_id]
        if type_filter:
            conditions.append(VoicePreset.type == type_filter)

        where_clause = and_(*conditions)

        # Count
        count_result = await self.db.execute(
            select(func.count()).select_from(VoicePreset).where(where_clause)
        )
        total = count_result.scalar() or 0

        # Items
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(VoicePreset)
            .where(where_clause)
            .order_by(VoicePreset.is_default.desc(), VoicePreset.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(result.scalars().all())

        return items, total

    async def update(
        self, preset_id: UUID, user_id: UUID, data: VoicePresetUpdate
    ) -> VoicePreset:
        """Update a voice preset."""
        preset = await self.get(preset_id, user_id)

        if data.is_default is True:
            await self._unset_default(user_id, preset.type)

        if data.name is not None:
            preset.name = data.name
        if data.config is not None:
            preset.config = data.config
        if data.is_default is not None:
            preset.is_default = data.is_default

        await self.db.flush()
        await self.db.refresh(preset)
        return preset

    async def delete(self, preset_id: UUID, user_id: UUID) -> None:
        """Delete a voice preset."""
        preset = await self.get(preset_id, user_id)
        await self.db.delete(preset)
        await self.db.flush()

    async def _unset_default(self, user_id: UUID, preset_type: str) -> None:
        """Unset the current default preset for a user+type."""
        result = await self.db.execute(
            select(VoicePreset).where(
                and_(
                    VoicePreset.user_id == user_id,
                    VoicePreset.type == preset_type,
                    VoicePreset.is_default.is_(True),
                )
            )
        )
        for preset in result.scalars().all():
            preset.is_default = False
