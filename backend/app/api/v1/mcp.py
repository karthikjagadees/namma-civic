"""
Model Context Protocol (MCP) API Endpoints
Provides tool discovery, schema inspection, and tool execution.
"""
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.mcp.client import mcp_client
from app.mcp.protocol import MCPToolCallRequest, MCPToolCallResponse, MCPToolListResponse

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])


class DirectInvokeRequest(BaseModel):
    arguments: Dict[str, Any] = Field(default_factory=dict)


@router.get("/tools", response_model=MCPToolListResponse)
async def list_mcp_tools(category: Optional[str] = Query(None, description="Filter by category (maps, civic, notifications)")):
    """Discover all available MCP tools registered on the server."""
    tools = mcp_client.list_tools(category=category)
    return MCPToolListResponse(jsonrpc="2.0", tools=tools)


@router.post("/call", response_model=MCPToolCallResponse)
async def call_mcp_tool_jsonrpc(payload: MCPToolCallRequest):
    """Execute tool via JSON-RPC 2.0 protocol format."""
    return await mcp_client.handle_jsonrpc(payload)


@router.post("/invoke/{tool_name}")
async def invoke_mcp_tool_direct(tool_name: str, payload: DirectInvokeRequest):
    """Convenience direct invocation endpoint for testing individual MCP tools."""
    tool = mcp_client.get_tool(tool_name)
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MCP Tool '{tool_name}' not found."
        )
    try:
        result = await mcp_client.call_tool(tool_name, payload.arguments)
        return {
            "tool": tool_name,
            "category": tool.category,
            "result": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tool execution failed: {str(e)}"
        )
