"""
MCP Server package registry
"""
from app.mcp.servers.maps_mcp import MAPS_TOOLS, execute_maps_tool
from app.mcp.servers.civic_mcp import CIVIC_TOOLS, execute_civic_tool
from app.mcp.servers.notification_mcp import NOTIFICATION_TOOLS, execute_notification_tool

__all__ = [
    "MAPS_TOOLS",
    "CIVIC_TOOLS",
    "NOTIFICATION_TOOLS",
    "execute_maps_tool",
    "execute_civic_tool",
    "execute_notification_tool",
]
