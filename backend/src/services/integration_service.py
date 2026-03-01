"""Integration service for managing third-party integrations.

Handles:
- Integration catalog CRUD
- User integration management (enable/disable/credentials)
- Connection testing via HTTP
"""

from __future__ import annotations

import time
from uuid import UUID

import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import NotFoundError, ValidationError
from src.models.integration import IntegrationCatalog, UserIntegration


class IntegrationService:
    """Service for integration catalog and user integration management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ==================== Catalog CRUD ====================

    async def list_catalog(
        self,
        category: str | None = None,
        active_only: bool = True,
    ) -> list[IntegrationCatalog]:
        """List all available integrations from the catalog."""
        query = select(IntegrationCatalog)
        if active_only:
            query = query.where(IntegrationCatalog.is_active == True)
        if category:
            query = query.where(IntegrationCatalog.category == category)
        query = query.order_by(IntegrationCatalog.sort_order, IntegrationCatalog.display_name)
        return list((await self.db.execute(query)).scalars().all())

    async def get_catalog_entry(self, integration_id: UUID) -> IntegrationCatalog:
        """Get a single catalog entry by ID."""
        result = await self.db.execute(
            select(IntegrationCatalog).where(IntegrationCatalog.id == integration_id)
        )
        entry = result.scalar_one_or_none()
        if not entry:
            raise NotFoundError(message="Integration not found", resource="integration")
        return entry

    async def create_catalog_entry(self, data: dict) -> IntegrationCatalog:
        """Create a new catalog entry."""
        existing = await self.db.execute(
            select(IntegrationCatalog).where(IntegrationCatalog.name == data["name"])
        )
        if existing.scalar_one_or_none():
            raise ValidationError(
                message=f"Integration '{data['name']}' already exists",
                details={"name": data["name"]},
            )

        entry = IntegrationCatalog(**data)
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def update_catalog_entry(
        self, integration_id: UUID, data: dict
    ) -> IntegrationCatalog:
        """Update an existing catalog entry."""
        entry = await self.get_catalog_entry(integration_id)
        for field, value in data.items():
            if hasattr(entry, field):
                setattr(entry, field, value)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def delete_catalog_entry(self, integration_id: UUID) -> bool:
        """Delete a catalog entry."""
        entry = await self.get_catalog_entry(integration_id)
        await self.db.delete(entry)
        await self.db.flush()
        return True

    # ==================== User Integrations ====================

    async def list_user_integrations(
        self,
        user_id: UUID,
        enabled_only: bool = False,
    ) -> list[UserIntegration]:
        """List integrations enabled for a user."""
        query = (
            select(UserIntegration)
            .options(selectinload(UserIntegration.catalog_entry))
            .where(UserIntegration.user_id == user_id)
        )
        if enabled_only:
            query = query.where(UserIntegration.is_enabled == True)
        return list((await self.db.execute(query)).scalars().all())

    async def get_user_integration(
        self,
        integration_id: UUID,
        user_id: UUID,
    ) -> UserIntegration:
        """Get a user integration by ID."""
        result = await self.db.execute(
            select(UserIntegration)
            .options(selectinload(UserIntegration.catalog_entry))
            .where(
                UserIntegration.id == integration_id,
                UserIntegration.user_id == user_id,
            )
        )
        ui = result.scalar_one_or_none()
        if not ui:
            raise NotFoundError(
                message="User integration not found", resource="user_integration"
            )
        return ui

    async def enable_integration(
        self,
        user_id: UUID,
        catalog_id: UUID,
        credentials: dict,
        config: dict | None = None,
    ) -> UserIntegration:
        """Enable an integration for a user."""
        # Validate catalog entry exists
        await self.get_catalog_entry(catalog_id)

        # Check if already enabled
        existing = await self.db.execute(
            select(UserIntegration).where(
                UserIntegration.user_id == user_id,
                UserIntegration.integration_id == catalog_id,
            )
        )
        if ui := existing.scalar_one_or_none():
            # Update existing
            ui.credentials = credentials
            ui.config = config or {}
            ui.is_verified = False
            ui.test_error = None
            await self.db.flush()
            await self.db.refresh(ui)
            return ui

        ui = UserIntegration(
            user_id=user_id,
            integration_id=catalog_id,
            credentials=credentials,
            config=config or {},
        )
        self.db.add(ui)
        await self.db.flush()
        await self.db.refresh(ui)
        return ui

    async def update_user_integration(
        self,
        integration_id: UUID,
        user_id: UUID,
        data: dict,
    ) -> UserIntegration:
        """Update credentials, config, or enabled status."""
        ui = await self.get_user_integration(integration_id, user_id)

        if "credentials" in data and data["credentials"] is not None:
            ui.credentials = data["credentials"]
            ui.is_verified = False  # Re-verify after credential change
        if "config" in data and data["config"] is not None:
            ui.config = data["config"]
        if "is_enabled" in data and data["is_enabled"] is not None:
            ui.is_enabled = data["is_enabled"]

        await self.db.flush()
        await self.db.refresh(ui)
        return ui

    async def delete_user_integration(
        self,
        integration_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Remove an integration from a user."""
        ui = await self.get_user_integration(integration_id, user_id)
        await self.db.delete(ui)
        await self.db.flush()
        return True

    # ==================== Connection Testing ====================

    async def test_connection(
        self,
        catalog_id: UUID,
        credentials: dict,
    ) -> dict:
        """Test an integration connection using the catalog's test endpoint.

        Returns:
            Dict with success, message, status_code, duration_ms
        """
        catalog = await self.get_catalog_entry(catalog_id)

        if not catalog.test_endpoint:
            return {
                "success": False,
                "message": "No test endpoint configured for this integration",
                "status_code": None,
                "duration_ms": 0,
            }

        # Build headers from auth schema
        headers = dict(catalog.test_headers or {})
        headers.update(self._build_auth_headers(catalog.auth_type, credentials))

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                method = (catalog.test_method or "GET").upper()
                response = await client.request(
                    method=method,
                    url=catalog.test_endpoint,
                    headers=headers,
                )
            duration_ms = (time.time() - start) * 1000
            success = 200 <= response.status_code < 300
            return {
                "success": success,
                "message": "Connected successfully" if success else f"HTTP {response.status_code}",
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 1),
            }
        except httpx.TimeoutException:
            return {
                "success": False,
                "message": "Connection timed out",
                "status_code": None,
                "duration_ms": round((time.time() - start) * 1000, 1),
            }
        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "status_code": None,
                "duration_ms": round((time.time() - start) * 1000, 1),
            }

    async def test_and_verify(
        self,
        integration_id: UUID,
        user_id: UUID,
    ) -> dict:
        """Test a user integration and update verification status."""
        ui = await self.get_user_integration(integration_id, user_id)
        catalog = await self.get_catalog_entry(ui.integration_id)

        result = await self.test_connection(catalog.id, ui.credentials)

        from datetime import datetime, timezone

        ui.is_verified = result["success"]
        ui.last_tested_at = datetime.now(timezone.utc).isoformat()
        ui.test_error = None if result["success"] else result["message"]

        if result["success"]:
            ui.is_enabled = True

        await self.db.flush()
        await self.db.refresh(ui)

        return result

    @staticmethod
    def _build_auth_headers(auth_type: str, credentials: dict) -> dict:
        """Build HTTP auth headers based on auth type."""
        if auth_type == "api_key":
            key = credentials.get("api_key", "")
            header_name = credentials.get("header_name", "Authorization")
            prefix = credentials.get("prefix", "Bearer")
            return {header_name: f"{prefix} {key}" if prefix else key}
        if auth_type == "bearer_token":
            return {"Authorization": f"Bearer {credentials.get('token', '')}"}
        if auth_type == "webhook":
            return {}  # Webhooks don't need auth headers for test
        return {}

    # ==================== Tool Schemas ====================

    async def get_integration_tools(
        self,
        user_id: UUID,
    ) -> list[dict]:
        """Get all tool schemas from enabled integrations for a user."""
        integrations = await self.list_user_integrations(
            user_id, enabled_only=True
        )
        tools = []
        for ui in integrations:
            if not ui.is_verified or not ui.catalog_entry:
                continue
            for tool_schema in ui.catalog_entry.tool_schemas or []:
                tools.append({
                    **tool_schema,
                    "integration_id": str(ui.integration_id),
                    "integration_name": ui.catalog_entry.name,
                })
        return tools
