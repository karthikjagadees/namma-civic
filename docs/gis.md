# Namma Civic — Geospatial Intelligence

## Overview

Namma Civic is location-aware. Every complaint is geo-tagged, and the system uses spatial data for:

1. Nearby complaint search (duplicate detection)
2. Department jurisdiction matching
3. Civic hotspot detection
4. Map visualisation

## GeoService Abstraction

```python
# app/gis/base.py
class GeoService(ABC):
    @abstractmethod
    async def find_nearby(
        self,
        lat: float, lng: float,
        radius_meters: float,
        category: Optional[str] = None,
    ) -> List[NearbyComplaint]: ...

    @abstractmethod
    async def calculate_distance(
        self, lat1: float, lng1: float,
        lat2: float, lng2: float,
    ) -> float: ...

    @abstractmethod
    async def find_hotspots(
        self, category: Optional[str] = None,
        days: int = 30,
    ) -> List[Hotspot]: ...
```

### SQLiteGeoService (Development)

Uses Python Haversine formula:

```python
def haversine(lat1, lon1, lat2, lon2) -> float:
    """Returns distance in meters."""
    R = 6371000  # Earth radius in meters
    φ1, φ2 = radians(lat1), radians(lat2)
    Δφ = radians(lat2 - lat1)
    Δλ = radians(lon2 - lon1)
    a = sin(Δφ/2)**2 + cos(φ1) * cos(φ2) * sin(Δλ/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))
```

Nearby search: loads complaints from DB, filters by bounding box, then Haversine distance.

### PostGISGeoService (Production)

Uses native PostGIS spatial operations:

```sql
-- Find complaints within 500m
SELECT c.*, ST_Distance(c.location, ST_MakePoint(:lng, :lat)::geography) as distance
FROM complaints c
WHERE ST_DWithin(
    c.location::geography,
    ST_MakePoint(:lng, :lat)::geography,
    :radius_meters
)
ORDER BY distance;
```

Hotspot detection using `ST_ClusterDBSCAN`:

```sql
SELECT
    ST_Centroid(ST_Collect(location)) as cluster_center,
    COUNT(*) as complaint_count,
    category
FROM complaints
WHERE created_at > NOW() - INTERVAL '30 days'
GROUP BY ST_SnapToGrid(location, 0.01), category
HAVING COUNT(*) >= 3;
```

## Switching GeoService

The active service is injected via dependency:

```python
def get_geo_service() -> GeoService:
    if settings.is_postgresql:
        return PostGISGeoService(db)
    return SQLiteGeoService(db)
```

## Civic Hotspot Algorithm

1. Cluster complaints by location (grid snapping or DBSCAN)
2. Filter clusters with ≥ 5 complaints in 30 days
3. Calculate centroid
4. Rank by complaint density
5. Tag with dominant category
6. Store in `civic_hotspots` table

## Map Visualisation

Frontend uses **Leaflet** with:

- OpenStreetMap tiles (free, no API key)
- Complaint markers coloured by priority
- Hotspot heatmap overlay
- Department jurisdiction polygons (optional)
- Cluster markers for dense areas
