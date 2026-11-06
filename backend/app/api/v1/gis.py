"""
Namma Civic — GIS & Geocoding API Router
Endpoints for forward geocoding, reverse geocoding, and address autocomplete.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.config import settings
from app.gis.service import (
    GeocodingService,
    autocomplete_address,
    geocode_address,
    reverse_geocode_coordinates,
)

router = APIRouter(prefix="/gis", tags=["GIS & Geocoding"])


class GeocodeResponse(BaseModel):
    latitude: float
    longitude: float
    formatted_address: str
    street: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    confidence: float = 1.0
    provider: str


class ReverseGeocodeResponse(BaseModel):
    latitude: float
    longitude: float
    address: str
    formatted_address: str
    street: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    provider: str


class AutocompleteItem(BaseModel):
    title: str
    formatted_address: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    city: Optional[str] = None
    provider: str


class GISStatusResponse(BaseModel):
    active_provider: str
    google_maps_configured: bool
    nominatim_enabled: bool


@router.get("/status", response_model=GISStatusResponse)
async def get_gis_status() -> GISStatusResponse:
    """Check active geocoding provider and availability."""
    has_google = bool(settings.maps_api_key and settings.maps_api_key.strip())
    active = "google_maps" if GeocodingService._should_use_google() else "openstreetmap_nominatim"
    return GISStatusResponse(
        active_provider=active,
        google_maps_configured=has_google,
        nominatim_enabled=True,
    )


@router.get("/geocode", response_model=GeocodeResponse)
async def geocode(
    address: str = Query(..., min_length=2, description="Address or landmark to geocode")
) -> GeocodeResponse:
    """
    Forward geocode an address or landmark to geographic coordinates (lat, lng).
    """
    result = await geocode_address(address)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Unable to locate coordinates for address: '{address}'",
        )
    return GeocodeResponse(**result)


@router.get("/reverse-geocode", response_model=ReverseGeocodeResponse)
async def reverse_geocode(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude"),
    lng: float = Query(..., ge=-180.0, le=180.0, description="Longitude"),
) -> ReverseGeocodeResponse:
    """
    Reverse geocode geographic coordinates to a human-readable street address.
    """
    result = await reverse_geocode_coordinates(lat, lng)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Unable to find human-readable address for coordinates ({lat}, {lng})",
        )
    return ReverseGeocodeResponse(**result)


@router.get("/autocomplete", response_model=List[AutocompleteItem])
async def autocomplete(
    query: str = Query(..., min_length=2, description="Search query string"),
    limit: int = Query(5, ge=1, le=10, description="Max suggestions to return"),
) -> List[AutocompleteItem]:
    """
    Instant search suggestions as the user types an address or landmark.
    """
    results = await autocomplete_address(query, limit=limit)
    return [AutocompleteItem(**item) for item in results]
