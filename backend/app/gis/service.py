"""
Namma Civic — GIS & Geolocation Services
Real geocoding, reverse geocoding, autocomplete, and spatial distance calculations.
Supports OpenStreetMap Nominatim (Free, no API key required) and Google Maps Platform.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import settings

logger = logging.getLogger("namma-civic.gis")

# Standard OpenStreetMap Nominatim endpoints
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
GOOGLE_GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_PLACES_AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"

USER_AGENT = "Namma-Civic/1.0 (civic-governance-engine; contact: info@namma-civic.ai)"


# ── Distance Calculations ───────────────────────────────────────────────────

def haversine_distance_meters(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate the great-circle distance between two points on the Earth
    in meters using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def haversine_distance_km(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Return distance in kilometers."""
    return haversine_distance_meters(lat1, lon1, lat2, lon2) / 1000.0


def is_within_radius(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    radius_meters: float = 50.0,
) -> bool:
    """Check if point 2 is within radius_meters of point 1."""
    return haversine_distance_meters(lat1, lon1, lat2, lon2) <= radius_meters


# ── Geocoding & Address Services ────────────────────────────────────────────

class GeocodingService:
    """
    Smart Geocoding Service supporting OpenStreetMap Nominatim and Google Maps.
    """

    @classmethod
    def _should_use_google(cls) -> bool:
        provider = (settings.geocoding_provider or "auto").lower()
        has_key = bool(settings.maps_api_key and settings.maps_api_key.strip())
        if provider == "google" and has_key:
            return True
        if provider == "auto" and has_key:
            return True
        return False

    @classmethod
    async def geocode_address(cls, address: str) -> Optional[Dict[str, Any]]:
        """
        Forward geocode: Street address / landmark string -> Latitude, Longitude, and formatted address.
        """
        if not address or not address.strip():
            return None

        clean_address = address.strip()

        # 1. Try Google Maps if configured
        if cls._should_use_google():
            try:
                res = await cls._geocode_google(clean_address)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Google Maps geocoding failed: {e}. Falling back to Nominatim.")

        # 2. Use OpenStreetMap Nominatim (Free, real-world data)
        return await cls._geocode_nominatim(clean_address)

    @classmethod
    async def reverse_geocode_coordinates(
        cls, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        """
        Reverse geocode: Coordinates (lat, lon) -> Formatted street address and details.
        """
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return None

        # 1. Try Google Maps if configured
        if cls._should_use_google():
            try:
                res = await cls._reverse_geocode_google(lat, lon)
                if res:
                    return res
            except Exception as e:
                logger.warning(f"Google Maps reverse geocoding failed: {e}. Falling back to Nominatim.")

        # 2. Use OpenStreetMap Nominatim
        return await cls._reverse_geocode_nominatim(lat, lon)

    @classmethod
    async def autocomplete_address(cls, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Autocomplete search query -> list of suggested places and locations.
        """
        if not query or len(query.strip()) < 2:
            return []

        clean_query = query.strip()

        if cls._should_use_google():
            try:
                results = await cls._autocomplete_google(clean_query, limit=limit)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Google Places autocomplete failed: {e}. Falling back to Nominatim.")

        return await cls._autocomplete_nominatim(clean_query, limit=limit)

    # ── Nominatim (OpenStreetMap) Provider ──────────────────────────────────

    @classmethod
    async def _geocode_nominatim(cls, address: str) -> Optional[Dict[str, Any]]:
        params = {
            "q": address,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
        }
        headers = {"User-Agent": USER_AGENT}

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NOMINATIM_SEARCH_URL, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Nominatim geocode returned HTTP {resp.status_code}")
                return None

            data = resp.json()
            if not data or not isinstance(data, list) or len(data) == 0:
                return None

            top = data[0]
            lat = float(top.get("lat"))
            lon = float(top.get("lon"))
            addr_details = top.get("address", {})

            # Extract human-readable street / road / neighborhood
            road = addr_details.get("road") or addr_details.get("pedestrian") or addr_details.get("suburb") or ""
            neighbourhood = addr_details.get("neighbourhood") or addr_details.get("suburb") or ""
            city = (
                addr_details.get("city")
                or addr_details.get("town")
                or addr_details.get("county")
                or addr_details.get("state_district")
                or ""
            )
            state = addr_details.get("state") or ""
            postcode = addr_details.get("postcode") or ""
            display_name = top.get("display_name", address)

            return {
                "latitude": lat,
                "longitude": lon,
                "formatted_address": display_name,
                "street": road,
                "neighborhood": neighbourhood,
                "city": city,
                "state": state,
                "postal_code": postcode,
                "confidence": 0.95,
                "provider": "openstreetmap_nominatim",
            }

    @classmethod
    async def _reverse_geocode_nominatim(
        cls, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        params = {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
            "zoom": 18,
        }
        headers = {"User-Agent": USER_AGENT}

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NOMINATIM_REVERSE_URL, params=params, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Nominatim reverse geocode returned HTTP {resp.status_code}")
                return None

            data = resp.json()
            if not data or "error" in data:
                return None

            addr = data.get("address", {})
            display_name = data.get("display_name", "")

            # Build readable short address
            road = addr.get("road") or addr.get("pedestrian") or addr.get("house_number") or ""
            neighbourhood = addr.get("neighbourhood") or addr.get("suburb") or addr.get("residential") or ""
            city = (
                addr.get("city")
                or addr.get("town")
                or addr.get("county")
                or addr.get("state_district")
                or ""
            )
            state = addr.get("state") or ""
            postcode = addr.get("postcode") or ""

            short_parts = [p for p in [road, neighbourhood, city] if p]
            short_address = ", ".join(short_parts) if short_parts else display_name

            return {
                "latitude": lat,
                "longitude": lon,
                "address": short_address,
                "formatted_address": display_name,
                "street": road,
                "neighborhood": neighbourhood,
                "city": city,
                "state": state,
                "postal_code": postcode,
                "provider": "openstreetmap_nominatim",
            }

    @classmethod
    async def _autocomplete_nominatim(
        cls, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        params = {
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "limit": limit,
        }
        headers = {"User-Agent": USER_AGENT}

        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(NOMINATIM_SEARCH_URL, params=params, headers=headers)
            if resp.status_code != 200:
                return []

            items = resp.json()
            results = []
            for item in items:
                lat = float(item.get("lat"))
                lon = float(item.get("lon"))
                addr = item.get("address", {})
                results.append({
                    "title": item.get("name") or item.get("display_name", "").split(",")[0],
                    "formatted_address": item.get("display_name", ""),
                    "latitude": lat,
                    "longitude": lon,
                    "city": addr.get("city") or addr.get("town") or addr.get("state") or "",
                    "provider": "openstreetmap_nominatim",
                })
            return results

    # ── Google Maps Provider ────────────────────────────────────────────────

    @classmethod
    async def _geocode_google(cls, address: str) -> Optional[Dict[str, Any]]:
        params = {
            "address": address,
            "key": settings.maps_api_key,
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GOOGLE_GEOCODE_URL, params=params)
            data = resp.json()
            if data.get("status") != "OK" or not data.get("results"):
                return None

            top = data["results"][0]
            loc = top["geometry"]["location"]
            lat = loc["lat"]
            lon = loc["lng"]

            return {
                "latitude": lat,
                "longitude": lon,
                "formatted_address": top.get("formatted_address", address),
                "confidence": 0.98,
                "provider": "google_maps",
            }

    @classmethod
    async def _reverse_geocode_google(
        cls, lat: float, lon: float
    ) -> Optional[Dict[str, Any]]:
        params = {
            "latlng": f"{lat},{lon}",
            "key": settings.maps_api_key,
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GOOGLE_GEOCODE_URL, params=params)
            data = resp.json()
            if data.get("status") != "OK" or not data.get("results"):
                return None

            top = data["results"][0]
            return {
                "latitude": lat,
                "longitude": lon,
                "address": top.get("formatted_address", ""),
                "formatted_address": top.get("formatted_address", ""),
                "provider": "google_maps",
            }

    @classmethod
    async def _autocomplete_google(
        cls, query: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        params = {
            "input": query,
            "key": settings.maps_api_key,
        }
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(GOOGLE_PLACES_AUTOCOMPLETE_URL, params=params)
            data = resp.json()
            if data.get("status") != "OK" or not data.get("predictions"):
                return []

            results = []
            for pred in data["predictions"][:limit]:
                results.append({
                    "title": pred.get("structured_formatting", {}).get("main_text", pred.get("description")),
                    "formatted_address": pred.get("description"),
                    "place_id": pred.get("place_id"),
                    "provider": "google_places",
                })
            return results


# Module-level convenience functions
async def geocode_address(address: str) -> Optional[Dict[str, Any]]:
    return await GeocodingService.geocode_address(address)


async def reverse_geocode_coordinates(lat: float, lon: float) -> Optional[Dict[str, Any]]:
    return await GeocodingService.reverse_geocode_coordinates(lat, lon)


async def autocomplete_address(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    return await GeocodingService.autocomplete_address(query, limit=limit)
