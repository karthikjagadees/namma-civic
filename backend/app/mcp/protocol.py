"""
Model Context Protocol (MCP) - Core Protocol Definitions
JSON-RPC 2.0 compatible schemas for Namma Civic Tool Server & Client.
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MCPToolParameter(BaseModel):
    name: str
    type: str = "string"
    description: str
    required: bool = True
    default: Optional[Any] = None


class MCPToolSchema(BaseModel):
    name: str
    description: str
    category: str = "general"
    parameters: Dict[str, Any] = Field(default_factory=dict)
    returns: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = "call-1"
    method: str = "tools/call"
    params: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[str] = "call-1"
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class MCPToolListResponse(BaseModel):
    jsonrpc: str = "2.0"
    tools: List[MCPToolSchema]
