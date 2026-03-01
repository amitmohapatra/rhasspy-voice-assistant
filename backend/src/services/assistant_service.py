"""Assistant service for managing AI assistants."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ValidationError
from src.models.assistant import Assistant
from src.schemas.assistant import AssistantCreate, AssistantUpdate, AssistantResponse


class AssistantService:
    """Service for assistant CRUD operations."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        data: AssistantCreate,
        user_id: UUID | None = None,
    ) -> Assistant:
        """Create a new assistant.

        Args:
            data: Assistant creation data
            user_id: ID of the user creating the assistant

        Returns:
            Created assistant
        """
        # Validate knowledge base IDs exist
        if data.knowledge_base_ids:
            await self._validate_knowledge_bases(data.knowledge_base_ids)

        assistant = Assistant(
            name=data.name,
            description=data.description,
            provider=data.provider,
            model=data.model,
            system_prompt=data.system_prompt,
            temperature=data.temperature,
            max_tokens=data.max_tokens,
            top_p=data.top_p,
            tool_ids=data.tools,
            knowledge_base_ids=data.knowledge_base_ids,
            settings=data.settings,
            avatar_enabled=data.avatar_enabled,
            avatar_config=data.avatar_config,
            voice_enabled=data.voice_enabled,
            voice_config=data.voice_config,
            created_by=user_id,
        )

        self.db.add(assistant)
        await self.db.flush()
        await self.db.refresh(assistant)

        return assistant

    async def get(
        self,
        assistant_id: UUID,
    ) -> Assistant:
        """Get an assistant by ID.

        Args:
            assistant_id: Assistant ID

        Returns:
            Assistant if found

        Raises:
            NotFoundError: If assistant not found
        """
        query = select(Assistant).where(Assistant.id == assistant_id)

        result = await self.db.execute(query)
        assistant = result.scalar_one_or_none()

        if not assistant:
            raise NotFoundError(
                message="Assistant not found",
                resource="assistant",
                details={"assistant_id": str(assistant_id)},
            )

        return assistant

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
        search: str | None = None,
        user_id: UUID | None = None,
    ) -> tuple[list[Assistant], int]:
        """List assistants with total count.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            active_only: Only return active assistants
            search: Optional search term for name/description
            user_id: Filter by creator (only show user's own assistants)

        Returns:
            Tuple of (assistants list, total count)
        """
        base_query = select(Assistant)

        if user_id:
            base_query = base_query.where(Assistant.created_by == user_id)

        if active_only:
            base_query = base_query.where(Assistant.is_active == True)

        if search:
            search_filter = f"%{search}%"
            base_query = base_query.where(
                (Assistant.name.ilike(search_filter))
                | (Assistant.description.ilike(search_filter))
            )

        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Data query
        data_query = base_query.offset(skip).limit(limit).order_by(
            Assistant.created_at.desc()
        )
        result = await self.db.execute(data_query)

        return list(result.scalars().all()), total

    async def update(
        self,
        assistant_id: UUID,
        data: AssistantUpdate,
    ) -> Assistant:
        """Update an assistant.

        Args:
            assistant_id: Assistant ID
            data: Update data

        Returns:
            Updated assistant
        """
        assistant = await self.get(assistant_id)

        # Validate knowledge base IDs if being updated
        if data.knowledge_base_ids is not None:
            await self._validate_knowledge_bases(data.knowledge_base_ids)

        # Update fields (map schema 'tools' to model 'tool_ids')
        update_data = data.model_dump(exclude_unset=True)
        if "tools" in update_data:
            update_data["tool_ids"] = update_data.pop("tools")
        for field, value in update_data.items():
            setattr(assistant, field, value)

        await self.db.flush()
        await self.db.refresh(assistant)

        return assistant

    async def delete(
        self,
        assistant_id: UUID,
    ) -> bool:
        """Delete an assistant.

        Args:
            assistant_id: Assistant ID

        Returns:
            True if deleted
        """
        assistant = await self.get(assistant_id)
        await self.db.delete(assistant)
        await self.db.flush()
        return True

    async def _validate_knowledge_bases(
        self,
        knowledge_base_ids: list[UUID],
    ) -> None:
        """Validate that knowledge bases exist."""
        from src.models.knowledge_base import KnowledgeBase

        for kb_id in knowledge_base_ids:
            query = select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
            )
            result = await self.db.execute(query)
            if not result.scalar_one_or_none():
                raise ValidationError(
                    message="Invalid knowledge base ID",
                    details={"knowledge_base_id": str(kb_id)},
                )
