"""
Unit and integration tests for Model Context Protocol (MCP) in Namma Civic.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.mcp.client import mcp_client
from app.mcp.protocol import MCPToolCallRequest


@pytest.mark.asyncio
async def test_mcp_client_tool_discovery():
    """Verify tool discovery across maps, civic, and notification modules."""
    tools = mcp_client.list_tools()
    assert len(tools) >= 8

    names = [t.name for t in tools]
    assert "gis_geocode" in names
    assert "gis_reverse_geocode" in names
    assert "gis_traffic_density_lookup" in names
    assert "civic_inventory_query" in names
    assert "civic_crew_availability" in names
    assert "civic_work_order_dispatch" in names
    assert "notify_citizen_sms" in names
    assert "notify_citizen_email" in names


@pytest.mark.asyncio
async def test_mcp_maps_execution():
    """Verify GIS maps tool executions."""
    # Test geocoding
    geo_res = await mcp_client.call_tool("gis_geocode", {"address": "Connaught Place Central Market"})
    assert "latitude" in geo_res
    assert "longitude" in geo_res
    assert geo_res["confidence"] > 0.8

    # Test reverse geocode
    rev_res = await mcp_client.call_tool("gis_reverse_geocode", {"latitude": 28.6139, "longitude": 77.2090})
    assert "address" in rev_res
    assert "neighborhood" in rev_res

    # Test traffic density
    traffic = await mcp_client.call_tool("gis_traffic_density_lookup", {"latitude": 28.6139, "longitude": 77.2090})
    assert "traffic_level" in traffic
    assert "road_classification" in traffic


@pytest.mark.asyncio
async def test_mcp_civic_and_notification_execution():
    """Verify civic inventory, work order dispatch, and SMS notification tools."""
    # Inventory
    inv = await mcp_client.call_tool("civic_inventory_query", {"department_code": "ROADS", "item_category": "asphalt"})
    assert inv["in_stock"] is True
    assert inv["available_units"] > 0

    # Work order dispatch
    wo = await mcp_client.call_tool("civic_work_order_dispatch", {
        "complaint_id": "test-uuid-1",
        "department_code": "WATER",
        "priority": "HIGH"
    })
    assert wo["work_order_id"].startswith("WO-")
    assert wo["status"] == "DISPATCHED"

    # SMS notification
    sms = await mcp_client.call_tool("notify_citizen_sms", {
        "phone_number": "+1-555-4321",
        "message": "Your pothole repair is on track."
    })
    assert sms["status"] == "DELIVERED"
    assert sms["delivery_id"].startswith("SMS-")


@pytest.mark.asyncio
async def test_mcp_api_endpoints():
    """Verify FastAPI /api/mcp/tools and /api/mcp/call endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # GET /api/mcp/tools
        r = await ac.get("/api/mcp/tools")
        assert r.status_code == 200
        data = r.json()
        assert "tools" in data
        assert len(data["tools"]) >= 8

        # POST /api/mcp/call with JSON-RPC 2.0 tools/call
        rpc_req = {
            "jsonrpc": "2.0",
            "id": "test-rpc-1",
            "method": "tools/call",
            "params": {
                "name": "gis_geocode",
                "arguments": {"address": "Ring Road Sector 4"}
            }
        }
        r_call = await ac.post("/api/mcp/call", json=rpc_req)
        assert r_call.status_code == 200
        call_data = r_call.json()
        assert call_data["id"] == "test-rpc-1"
        assert "result" in call_data
        assert "latitude" in call_data["result"]

        # POST /api/mcp/invoke/civic_inventory_query
        r_inv = await ac.post("/api/mcp/invoke/civic_inventory_query", json={
            "arguments": {"department_code": "ELECTRICITY"}
        })
        assert r_inv.status_code == 200
        assert r_inv.json()["result"]["in_stock"] is True
