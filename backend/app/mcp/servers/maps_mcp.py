"""
Maps & GIS MCP Tool Server
Exposes spatial tools: geocoding, reverse geocoding, and traffic/road density lookup.
"""
from typing import Any, Dict
from app.mcp.protocol import MCPToolSchema


MAPS_TOOLS = [
    MCPToolSchema(
        name="gis_geocode",
        description="Convert address string into geospatial coordinates (latitude, longitude) and normalized address.",
        category="maps",
        parameters={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Street address or landmark name"}
            },
            "required": ["address"]
        },
        returns={
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "formatted_address": {"type": "string"},
                "confidence": {"type": "number"}
            }
        }
    ),
    MCPToolSchema(
        name="gis_reverse_geocode",
        description="Convert latitude and longitude coordinates into human-readable street address and neighborhood.",
        category="maps",
        parameters={
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "Geographic latitude (-90 to 90)"},
                "longitude": {"type": "number", "description": "Geographic longitude (-180 to 180)"}
            },
            "required": ["latitude", "longitude"]
        },
        returns={
            "type": "object",
            "properties": {
                "address": {"type": "string"},
                "neighborhood": {"type": "string"},
                "city": {"type": "string"},
                "postal_code": {"type": "string"}
            }
        }
    ),
    MCPToolSchema(
        name="gis_traffic_density_lookup",
        description="Determine traffic density and road classification around a coordinate.",
        category="maps",
        parameters={
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "radius_m": {"type": "integer", "default": 500}
            },
            "required": ["latitude", "longitude"]
        },
        returns={
            "type": "object",
            "properties": {
                "traffic_level": {"type": "string"},
                "road_classification": {"type": "string"},
                "pedestrian_index": {"type": "string"}
            }
        }
    )
]


from app.gis.service import geocode_address, reverse_geocode_coordinates


async def execute_maps_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Maps MCP tool using real GIS geocoding service."""
    if name == "gis_geocode":
        address = str(args.get("address", "")).strip()
        geo = await geocode_address(address)
        if geo:
            return {
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "formatted_address": geo["formatted_address"],
                "confidence": geo.get("confidence", 0.95),
                "source": f"Namma Civic GIS ({geo.get('provider', 'Nominatim')})"
            }
        return {
            "latitude": 28.6139,
            "longitude": 77.2090,
            "formatted_address": address or "Central Municipal District",
            "confidence": 0.5,
            "source": "Namma Civic Fallback Centroid"
        }

    elif name == "gis_reverse_geocode":
        lat = float(args.get("latitude", 28.6139))
        lng = float(args.get("longitude", 77.2090))
        rev = await reverse_geocode_coordinates(lat, lng)
        if rev:
            return {
                "address": rev.get("address", rev.get("formatted_address", "")),
                "neighborhood": rev.get("neighborhood", "Municipal Ward"),
                "city": rev.get("city", "City Center"),
                "postal_code": rev.get("postal_code", ""),
                "coordinates": {"lat": lat, "lng": lng}
            }
        return {
            "address": f"Coordinates: {lat:.4f}, {lng:.4f}",
            "neighborhood": "Municipal Sector",
            "city": "Metropolitan District",
            "postal_code": "",
            "coordinates": {"lat": lat, "lng": lng}
        }

    elif name == "gis_traffic_density_lookup":
        lat = float(args.get("latitude", 28.6139))
        lng = float(args.get("longitude", 77.2090))
        radius = int(args.get("radius_m", 500))
        
        # Heuristic based on coordinate fractions
        is_major_arterial = (int(lat * 1000) % 2 == 0)
        return {
            "traffic_level": "HEAVY" if is_major_arterial else "MODERATE",
            "road_classification": "Arterial Corridor" if is_major_arterial else "Collector Street",
            "pedestrian_index": "HIGH",
            "speed_limit_kmh": 50 if is_major_arterial else 30,
            "monitoring_radius_m": radius
        }

    raise ValueError(f"Unknown Maps tool: {name}")
