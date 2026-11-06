"""
Model Context Protocol (MCP) Unified Client
Discovers tools, validates inputs, and delegates invocations to registered MCP servers.
"""
from typing import Any, Dict, List, Optional
from app.mcp.protocol import MCPToolSchema, MCPToolCallRequest, MCPToolCallResponse
from app.mcp.servers import (
    MAPS_TOOLS,
    CIVIC_TOOLS,
    NOTIFICATION_TOOLS,
    execute_maps_tool,
    execute_civic_tool,
    execute_notification_tool,
)


class MCPClient:
    """Unified MCP Client for Namma Civic."""

    def __init__(self):
        self._tools: Dict[str, MCPToolSchema] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        for tool in MAPS_TOOLS + CIVIC_TOOLS + NOTIFICATION_TOOLS:
            self._tools[tool.name] = tool

    def list_tools(self, category: Optional[str] = None) -> List[MCPToolSchema]:
        """Return list of available MCP tool schemas."""
        tools = list(self._tools.values())
        if category:
            return [t for t in tools if t.category.lower() == category.lower()]
        return tools

    def get_tool(self, name: str) -> Optional[MCPToolSchema]:
        """Look up tool by name."""
        return self._tools.get(name)

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool by name with arguments.
        Dispatches to the appropriate domain server.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered in Namma Civic MCP Client.")

        tool = self._tools[name]
        category = tool.category

        if category == "maps":
            return await execute_maps_tool(name, arguments)
        elif category == "civic":
            return await execute_civic_tool(name, arguments)
        elif category == "notifications":
            return await execute_notification_tool(name, arguments)
        else:
            raise NotImplementedError(f"Category '{category}' has no handler attached.")

    async def handle_jsonrpc(self, request: MCPToolCallRequest) -> MCPToolCallResponse:
        """Process standard JSON-RPC 2.0 tools/call request."""
        method = request.method
        if method == "tools/list":
            return MCPToolCallResponse(
                jsonrpc="2.0",
                id=request.id,
                result={"tools": [t.model_dump() for t in self.list_tools()]}
            )
        elif method == "tools/call":
            params = request.params
            name = params.get("name")
            arguments = params.get("arguments", {})
            if not name:
                return MCPToolCallResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    error={"code": -32602, "message": "Missing required parameter 'name'"}
                )
            try:
                result = await self.call_tool(name, arguments)
                return MCPToolCallResponse(jsonrpc="2.0", id=request.id, result=result)
            except Exception as e:
                return MCPToolCallResponse(
                    jsonrpc="2.0",
                    id=request.id,
                    error={"code": -32000, "message": str(e)}
                )
        else:
            return MCPToolCallResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32601, "message": f"Method '{method}' not found"}
            )


# Global singleton client
mcp_client = MCPClient()
