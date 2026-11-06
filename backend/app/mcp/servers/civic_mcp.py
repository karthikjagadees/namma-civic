"""
Civic Operations & Municipal Infrastructure MCP Tool Server
Exposes municipal equipment inventory, repair crew status, and work order tools.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict
from app.mcp.protocol import MCPToolSchema


CIVIC_TOOLS = [
    MCPToolSchema(
        name="civic_inventory_query",
        description="Check municipal inventory stock for repair materials (asphalt, pipes, lights, pumps, gravel).",
        category="civic",
        parameters={
            "type": "object",
            "properties": {
                "department_code": {"type": "string", "description": "e.g. ROADS, WATER, ELECTRICITY, SANITATION"},
                "item_category": {"type": "string", "description": "e.g. asphalt, valve, lamp, bitumen, chlorine"}
            },
            "required": ["department_code"]
        },
        returns={
            "type": "object",
            "properties": {
                "in_stock": {"type": "boolean"},
                "available_units": {"type": "integer"},
                "depot_location": {"type": "string"},
                "lead_time_hours": {"type": "number"}
            }
        }
    ),
    MCPToolSchema(
        name="civic_crew_availability",
        description="Find active, available field maintenance crews for a specific municipal department.",
        category="civic",
        parameters={
            "type": "object",
            "properties": {
                "department_code": {"type": "string"},
                "zone": {"type": "string", "default": "Central"}
            },
            "required": ["department_code"]
        },
        returns={
            "type": "object",
            "properties": {
                "crews_available": {"type": "integer"},
                "active_crews": {"type": "array"},
                "next_available_slot": {"type": "string"}
            }
        }
    ),
    MCPToolSchema(
        name="civic_work_order_dispatch",
        description="Formally generate and dispatch a field work order to a municipal maintenance crew.",
        category="civic",
        parameters={
            "type": "object",
            "properties": {
                "complaint_id": {"type": "string"},
                "department_code": {"type": "string"},
                "crew_id": {"type": "string"},
                "action_type": {"type": "string"},
                "priority": {"type": "string"},
                "idempotency_key": {"type": "string", "description": "Stable local work-order key for safe retries"}
            },
            "required": ["complaint_id", "department_code"]
        },
        returns={
            "type": "object",
            "properties": {
                "work_order_id": {"type": "string"},
                "status": {"type": "string"},
                "dispatched_at": {"type": "string"},
                "assigned_crew": {"type": "string"},
                "target_eta_hours": {"type": "integer"}
            }
        }
    )
]


async def execute_civic_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Civic Maintenance MCP tool."""
    dept = str(args.get("department_code", "GENERAL")).upper()

    if name == "civic_inventory_query":
        item = str(args.get("item_category", "")).lower()
        stocks = {
            "ROADS": {"item": "Cold/Hot Asphalt Mix & Roller", "units": 420, "depot": "North Depot Yard #4", "lead_time": 1.5},
            "WATER": {"item": "Ductile Iron Pipe Sleeves & Gate Valves", "units": 85, "depot": "Water Works Station 2", "lead_time": 2.0},
            "ELECTRICITY": {"item": "LED Luminaire Modules & Underground Wire", "units": 130, "depot": "Power Grid Depot B", "lead_time": 1.0},
            "SANITATION": {"item": "Compactor Trucks & Biological Sanitizers", "units": 60, "depot": "Solid Waste Terminal 1", "lead_time": 1.0},
        }
        stock_info = stocks.get(dept, {"item": "Standard Municipal Toolset", "units": 50, "depot": "Central Depot", "lead_time": 2.0})
        return {
            "department_code": dept,
            "material_name": stock_info["item"],
            "in_stock": True,
            "available_units": stock_info["units"],
            "depot_location": stock_info["depot"],
            "lead_time_hours": stock_info["lead_time"],
            "requisition_status": "APPROVED_AUTO"
        }

    elif name == "civic_crew_availability":
        zone = args.get("zone", "Central")
        crew_catalog = {
            "ROADS": [
                {"crew_id": "ROAD-CREW-A1", "lead": "Supervisor Sharma", "status": "AVAILABLE", "current_load": 1},
                {"crew_id": "ROAD-CREW-B2", "lead": "Foreman Gupta", "status": "ON_PATROL", "current_load": 2}
            ],
            "WATER": [
                {"crew_id": "WATER-REPAIR-1", "lead": "Engineer Rajesh", "status": "AVAILABLE", "current_load": 0},
                {"crew_id": "WATER-EMERGENCY-2", "lead": "Foreman Khan", "status": "STANDBY", "current_load": 1}
            ],
            "ELECTRICITY": [
                {"crew_id": "POWER-VAN-03", "lead": "Lineman Verma", "status": "AVAILABLE", "current_load": 1}
            ]
        }
        dept_crews = crew_catalog.get(dept, [
            {"crew_id": f"{dept}-CREW-01", "lead": "Duty Officer", "status": "AVAILABLE", "current_load": 0}
        ])
        available = [c for c in dept_crews if c["status"] in ("AVAILABLE", "STANDBY")]
        return {
            "department_code": dept,
            "zone": zone,
            "crews_available": len(available),
            "active_crews": dept_crews,
            "recommended_crew": available[0]["crew_id"] if available else dept_crews[0]["crew_id"],
            "next_available_slot": "IMMEDIATE"
        }

    elif name == "civic_work_order_dispatch":
        cid = str(args.get("complaint_id", "GENERAL"))
        crew_id = args.get("crew_id") or f"{dept}-RAPID-1"
        priority = str(args.get("priority", "HIGH")).upper()
        idempotency_key = args.get("idempotency_key")
        wo_id = (
            f"WO-{str(idempotency_key).replace('-', '')[:8].upper()}"
            if idempotency_key
            else f"WO-{uuid.uuid4().hex[:8].upper()}"
        )
        eta = 4 if priority == "CRITICAL" else 12 if priority == "HIGH" else 24

        return {
            "work_order_id": wo_id,
            "complaint_id": cid,
            "department_code": dept,
            "assigned_crew": crew_id,
            "status": "DISPATCHED",
            "priority": priority,
            "target_eta_hours": eta,
            "dispatched_at": datetime.now(timezone.utc).isoformat(),
            "telemetry_channel": f"namma-civic.field.{wo_id.lower()}"
        }

    raise ValueError(f"Unknown Civic tool: {name}")
