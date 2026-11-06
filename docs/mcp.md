# Namma Civic — Model Context Protocol (MCP) Architecture

## Overview

Namma Civic uses **MCP (Model Context Protocol)** to give LangGraph agents standardised, structured access to external tools and data sources.

LangGraph agents do NOT directly call databases or external APIs. Instead, they call **MCP tools** which are exposed by **MCP Servers**.

## Architecture

```
LangGraph Agents
      │
   MCP Client (app/mcp/client.py)
      │
      ├── Maps / GIS MCP Server       (port 8010)
      ├── Civic Database MCP Server   (port 8011)
      ├── Notification MCP Server     (port 8012)
      ├── Policy MCP Server           (port 8013)
      └── Analytics MCP Server        (port 8014)
```

## MCP Client

`app/mcp/client.py` — A thin async client that:

1. In `mock` mode: returns deterministic mock responses (no server needed)
2. In `local` mode: calls local MCP server processes via HTTP
3. In `remote` mode: calls deployed MCP server endpoints

```python
class MCPClient:
    async def call_tool(self, server: str, tool: str, args: dict) -> dict:
        ...
```

## MCP Servers

### Server 1: Maps / GIS (`mcp-servers/maps/`)

| Tool | Description |
|---|---|
| `geocode_address` | Convert address text to lat/lng |
| `reverse_geocode` | Convert lat/lng to address |
| `find_nearby_complaints` | Search complaints within N meters |
| `calculate_distance` | Haversine distance between two points |
| `find_hotspots` | Identify complaint clusters |
| `get_jurisdiction` | Find civic zone for coordinates |

### Server 2: Civic Database (`mcp-servers/civic/`)

| Tool | Description |
|---|---|
| `create_civic_task` | Create a new CivicTask record |
| `get_department` | Get department details by ID or category |
| `get_department_officers` | List available officers |
| `update_task_status` | Update task status |
| `get_sla_config` | Get SLA rules for priority level |
| `assign_officer` | Assign officer to task |

### Server 3: Notifications (`mcp-servers/notification/`)

| Tool | Description |
|---|---|
| `send_notification` | In-app push notification |
| `send_email` | Send email (real or mock) |
| `send_sms` | Send SMS (Twilio or mock) |
| `broadcast_to_department` | Notify all dept officers |

### Server 4: Policy (`mcp-servers/policy/`)

| Tool | Description |
|---|---|
| `get_routing_rules` | Category → department mapping rules |
| `get_sla_policy` | Priority → SLA hours |
| `get_priority_weights` | Scoring factor weights |
| `get_escalation_policy` | Escalation levels and timing |

### Server 5: Analytics (`mcp-servers/analytics/`)

| Tool | Description |
|---|---|
| `get_civic_statistics` | Summary stats |
| `get_hotspots` | Top hotspot locations |
| `get_category_trends` | Trend data by category |
| `get_department_kpis` | Department performance |

## Mock Mode

When `MCP_MODE=mock`, the MCP Client uses `MockMCPClient` which:

- Returns realistic fake data
- Simulates realistic latencies
- Logs all calls for debugging
- Works with no server infrastructure

This allows the full demo to run without any MCP servers.

## Protocol

All MCP tool calls follow the pattern:

**Request:**
```json
{
  "tool": "geocode_address",
  "arguments": {
    "address": "MG Road, Kolkata"
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "latitude": 22.5726,
    "longitude": 88.3639,
    "formatted_address": "MG Road, Kolkata, West Bengal 700007"
  }
}
```
