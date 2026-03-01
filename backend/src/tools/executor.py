"""Tool executor for running tools."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ToolExecutionError
from src.models.tool import Tool, ToolExecution
from src.tools.registry import get_registry, BaseTool


class ToolExecutor:
    """Execute tools and log results."""

    def __init__(self, tool: Tool, db: AsyncSession) -> None:
        self.tool = tool
        self.db = db
        self.registry = get_registry()

    async def execute(
        self,
        response_item_id: UUID | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute a tool and log the result.

        Args:
            response_item_id: Optional response item ID for audit
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        start_time = time.time()

        # Create execution log
        execution = ToolExecution(
            tool_id=self.tool.id,
            response_item_id=response_item_id,
            input=kwargs,
            status="pending",
        )
        self.db.add(execution)
        await self.db.flush()

        try:
            # Get handler from registry or use custom logic
            result = await self._execute_handler(kwargs)

            # Update execution log
            execution.status = "success"
            execution.output = {"result": result}
            execution.execution_time_ms = int((time.time() - start_time) * 1000)

            await self.db.flush()

            return result

        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.execution_time_ms = int((time.time() - start_time) * 1000)

            await self.db.flush()

            raise ToolExecutionError(
                message=f"Tool execution failed: {str(e)}",
                tool_name=self.tool.name,
                details={"input": kwargs, "error": str(e)},
            )

    async def _execute_handler(self, kwargs: dict[str, Any]) -> Any:
        """Execute the tool handler."""
        # Check if tool type has a registered handler
        tool_meta = self.registry.get(self.tool.type)

        if tool_meta:
            # Use registered handler
            handler_class = tool_meta.handler
            if isinstance(handler_class, type) and issubclass(handler_class, BaseTool):
                handler = handler_class(config=self.tool.implementation)
                return await handler.execute(**kwargs)
            elif callable(handler_class):
                return await handler_class(**kwargs)

        # Fall back to implementation-based handling
        handler_type = (self.tool.implementation or {}).get("handler", self.tool.type)

        if handler_type == "http":
            return await self._execute_http(kwargs)
        elif handler_type == "database":
            return await self._execute_database(kwargs)
        elif handler_type == "mcp":
            return await self._execute_mcp(kwargs)
        elif handler_type == "code":
            return await self._execute_code(kwargs)
        else:
            raise ToolExecutionError(
                message=f"Unknown tool handler type: {handler_type}",
                tool_name=self.tool.name,
            )

    async def _execute_http(self, kwargs: dict[str, Any]) -> Any:
        """Execute HTTP tool."""
        import httpx

        impl = self.tool.implementation or {}
        method = impl.get("method", "GET")
        url = impl.get("url", "")
        headers = impl.get("headers", {})
        auth_type = impl.get("auth_type")

        if not url:
            raise ToolExecutionError(
                message="HTTP tool URL not configured",
                tool_name=self.tool.name,
            )

        # Replace placeholders in URL
        for key, value in kwargs.items():
            url = url.replace(f"{{{key}}}", str(value))

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                json=kwargs if method in ("POST", "PUT", "PATCH") else None,
                params=kwargs if method == "GET" else None,
            )
            response.raise_for_status()

            return response.json()

    async def _execute_database(self, kwargs: dict[str, Any]) -> Any:
        """Execute database tool (read-only)."""
        raise NotImplementedError("Database tool not yet implemented")

    async def _execute_mcp(self, kwargs: dict[str, Any]) -> Any:
        """Execute MCP tool via JSON-RPC over HTTP transport."""
        import httpx

        mcp_config = self.tool.mcp_config or {}
        server_url = mcp_config.get("server_url")
        transport = mcp_config.get("transport", "http")

        if not server_url:
            raise ToolExecutionError(
                message="MCP server URL not configured",
                tool_name=self.tool.name,
            )

        if transport != "http":
            raise ToolExecutionError(
                message=f"MCP transport '{transport}' not supported (only 'http' is supported)",
                tool_name=self.tool.name,
            )

        # JSON-RPC 2.0 request to MCP server
        jsonrpc_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": self.tool.name,
                "arguments": kwargs,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                server_url,
                json=jsonrpc_request,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

            result = response.json()

            if "error" in result:
                raise ToolExecutionError(
                    message=f"MCP error: {result['error'].get('message', 'Unknown error')}",
                    tool_name=self.tool.name,
                    details=result["error"],
                )

            return result.get("result", {})

    async def _execute_code(self, kwargs: dict[str, Any]) -> Any:
        """Execute Python code tool in a restricted sandbox."""
        impl = self.tool.implementation or {}
        code = impl.get("code", "")

        if not code:
            raise ToolExecutionError(
                message="No code provided for code tool",
                tool_name=self.tool.name,
            )

        # Execute in restricted namespace
        namespace: dict[str, Any] = {"params": kwargs, "result": None}
        safe_builtins = {
            "len": len, "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "sorted": sorted, "enumerate": enumerate, "zip": zip, "range": range,
            "isinstance": isinstance, "type": type, "None": None, "True": True, "False": False,
        }
        namespace["__builtins__"] = safe_builtins

        try:
            exec(code, namespace)
            return namespace.get("result", None)
        except Exception as e:
            raise ToolExecutionError(
                message=f"Code execution failed: {str(e)}",
                tool_name=self.tool.name,
                details={"error": str(e)},
            )


class BuiltInTools:
    """Collection of built-in tools."""

    @staticmethod
    def get_current_time() -> dict[str, Any]:
        """Get current time."""
        from datetime import datetime

        now = datetime.utcnow()
        return {
            "utc": now.isoformat(),
            "timestamp": now.timestamp(),
        }

    @staticmethod
    def calculate(expression: str) -> dict[str, Any]:
        """Safely evaluate a mathematical expression."""
        import ast
        import operator

        operators = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Pow: operator.pow,
            ast.USub: operator.neg,
        }

        def eval_expr(node: ast.expr) -> float:
            if isinstance(node, ast.Num):
                return node.n
            elif isinstance(node, ast.BinOp):
                return operators[type(node.op)](
                    eval_expr(node.left), eval_expr(node.right)
                )
            elif isinstance(node, ast.UnaryOp):
                return operators[type(node.op)](eval_expr(node.operand))
            else:
                raise ValueError(f"Unsupported operation: {type(node)}")

        try:
            tree = ast.parse(expression, mode="eval")
            result = eval_expr(tree.body)
            return {"expression": expression, "result": result}
        except Exception as e:
            return {"expression": expression, "error": str(e)}
