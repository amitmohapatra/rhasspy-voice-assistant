"""Tool management routes."""

from __future__ import annotations

from uuid import UUID
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from src.api.deps import DbSession, CurrentUser
from src.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolResponse,
    ToolExecutionResponse,
    AdhocToolTestRequest,
)
from src.services.builtin_tool_service import BuiltinToolService

router = APIRouter()


# ========== Schemas for Built-in and Integration Tools ==========

class CustomToolCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    category: str = "custom"
    icon: str | None = None
    schema_definition: dict[str, Any]
    implementation: dict[str, Any]
    required_secrets: list[str] = []


# ========== Built-in Tools Catalog (DB-driven) ==========

@router.get("/catalog/builtin")
async def list_builtin_tools(
    db: DbSession,
    current_user: CurrentUser,
    provider_id: str | None = Query(None, description="Filter by provider ID"),
) -> list[dict]:
    """List all built-in tools available in the system (from database)."""
    service = BuiltinToolService(db)
    tools = await service.list_builtin_tools(
        provider_id=UUID(provider_id) if provider_id else None,
    )
    return [tool.to_dict() for tool in tools]


@router.get("/catalog/integrations")
async def list_integration_tools(
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict]:
    """List all integration tools (built-in tools with category=integration)."""
    from src.models.builtin_tool import ToolCategory
    service = BuiltinToolService(db)
    tools = await service.list_builtin_tools(category=ToolCategory.INTEGRATION)
    return [tool.to_dict() for tool in tools]


@router.get("/catalog/all")
async def list_all_catalog_tools(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, list]:
    """List all available tools grouped by type."""
    from src.models.builtin_tool import ToolCategory
    service = BuiltinToolService(db)

    all_tools = await service.list_builtin_tools()
    integration_tools = await service.list_builtin_tools(category=ToolCategory.INTEGRATION)

    builtin = [t.to_dict() for t in all_tools if t.category != ToolCategory.INTEGRATION]
    integrations = [t.to_dict() for t in integration_tools]

    return {
        "builtin": builtin,
        "integrations": integrations,
    }


# ========== Custom Tool Builder Endpoints ==========

@router.post("/custom", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_tool(
    data: CustomToolCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolResponse:
    """Create a custom tool with HTTP/Code/MCP implementation."""
    from sqlalchemy import select
    from src.models.tool import Tool

    # Check if tool with same name exists for this user
    query = select(Tool).where(
        Tool.name == data.name,
        Tool.created_by == current_user.id,
    )
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool with name '{data.name}' already exists",
        )

    # Create tool
    tool = Tool(
        type="custom",
        category=data.category,
        name=data.name,
        display_name=data.display_name or data.name,
        description=data.description,
        icon=data.icon,
        schema_definition=data.schema_definition,
        implementation=data.implementation,
        required_secrets=data.required_secrets,
        is_system=False,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(tool)
    await db.flush()

    return ToolResponse.model_validate(tool)


@router.post("/test-adhoc")
async def test_adhoc_tool(
    data: AdhocToolTestRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Test a tool definition before creating it.

    Useful for validating HTTP endpoints, MCP servers, etc.
    without persisting the tool.
    """
    import httpx
    import time

    impl = data.implementation
    handler = impl.get("handler", "http")
    start_time = time.time()

    try:
        if handler == "http":
            method = impl.get("method", "GET")
            url = impl.get("url", "")
            headers = impl.get("headers", {})

            if not url:
                return {"success": False, "error": "URL is required for HTTP tools"}

            # Replace placeholders in URL
            for key, value in data.parameters.items():
                url = url.replace(f"{{{key}}}", str(value))

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data.parameters if method in ("POST", "PUT", "PATCH") else None,
                    params=data.parameters if method == "GET" else None,
                )

                duration_ms = int((time.time() - start_time) * 1000)
                return {
                    "success": response.is_success,
                    "status_code": response.status_code,
                    "result": response.json() if response.is_success else None,
                    "error": response.text if not response.is_success else None,
                    "duration_ms": duration_ms,
                }

        elif handler == "mcp":
            mcp_config = data.mcp_config or {}
            server_url = mcp_config.get("server_url")

            if not server_url:
                return {"success": False, "error": "MCP server URL is required"}

            # Test MCP server connectivity with a tools/list call
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    server_url,
                    json=jsonrpc_request,
                    headers={"Content-Type": "application/json"},
                )

                duration_ms = int((time.time() - start_time) * 1000)
                result = response.json()

                return {
                    "success": "error" not in result,
                    "result": result.get("result"),
                    "error": result.get("error", {}).get("message") if "error" in result else None,
                    "duration_ms": duration_ms,
                }

        elif handler == "code":
            code = impl.get("code", "")
            if not code:
                return {"success": False, "error": "Code is required for code tools"}

            # Test code execution in sandbox
            namespace: dict[str, Any] = {"params": data.parameters, "result": None}
            safe_builtins = {
                "len": len, "str": str, "int": int, "float": float, "bool": bool,
                "list": list, "dict": dict, "tuple": tuple, "set": set,
                "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
                "sorted": sorted, "enumerate": enumerate, "zip": zip, "range": range,
                "isinstance": isinstance, "type": type, "None": None, "True": True, "False": False,
            }
            namespace["__builtins__"] = safe_builtins

            exec(code, namespace)
            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "success": True,
                "result": namespace.get("result"),
                "duration_ms": duration_ms,
            }

        else:
            return {"success": False, "error": f"Unknown handler type: {handler}"}

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "success": False,
            "error": str(e),
            "duration_ms": duration_ms,
        }


@router.get("/available", response_model=list[dict])
async def list_available_tools(
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict]:
    """List all available built-in tools from the DB."""
    service = BuiltinToolService(db)
    tools = await service.list_builtin_tools()
    return [tool.to_dict() for tool in tools]


@router.get("", response_model=list[ToolResponse])
async def list_custom_tools(
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    active_only: bool = Query(True),
) -> list[ToolResponse]:
    """List custom tools created by the current user."""
    from sqlalchemy import select
    from src.models.tool import Tool

    query = select(Tool).where(Tool.created_by == current_user.id)

    if active_only:
        query = query.where(Tool.is_active == True)

    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    tools = result.scalars().all()

    return [ToolResponse.model_validate(t) for t in tools]


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolResponse:
    """Get a custom tool by ID."""
    from sqlalchemy import select
    from src.models.tool import Tool

    query = select(Tool).where(
        Tool.id == tool_id,
    )
    result = await db.execute(query)
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    return ToolResponse.model_validate(tool)


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    data: ToolUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> ToolResponse:
    """Update a custom tool."""
    from sqlalchemy import select
    from src.models.tool import Tool

    query = select(Tool).where(
        Tool.id == tool_id,
    )
    result = await db.execute(query)
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tool, field, value)

    await db.flush()
    await db.refresh(tool)

    return ToolResponse.model_validate(tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> None:
    """Delete a custom tool."""
    from sqlalchemy import select
    from src.models.tool import Tool

    query = select(Tool).where(
        Tool.id == tool_id,
    )
    result = await db.execute(query)
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    await db.delete(tool)
    await db.flush()


@router.get("/{tool_id}/executions", response_model=list[ToolExecutionResponse])
async def list_tool_executions(
    tool_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> list[ToolExecutionResponse]:
    """List execution history for a tool."""
    from sqlalchemy import select
    from src.models.tool import Tool, ToolExecution

    # Verify tool exists
    tool_query = select(Tool).where(
        Tool.id == tool_id,
    )
    result = await db.execute(tool_query)
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    # Get executions - use created_at (not executed_at which doesn't exist)
    exec_query = (
        select(ToolExecution)
        .where(ToolExecution.tool_id == tool_id)
        .order_by(ToolExecution.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(exec_query)
    executions = result.scalars().all()

    return [ToolExecutionResponse.model_validate(e) for e in executions]


@router.post("/{tool_id}/test", response_model=dict)
async def test_tool(
    tool_id: UUID,
    parameters: dict,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Test execute a tool with given parameters."""
    from sqlalchemy import select
    from src.models.tool import Tool
    from src.tools.executor import ToolExecutor

    # Verify tool exists
    query = select(Tool).where(
        Tool.id == tool_id,
    )
    result = await db.execute(query)
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool not found",
        )

    # Execute tool
    try:
        executor = ToolExecutor(tool, db)
        result = await executor.execute(**parameters)

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
