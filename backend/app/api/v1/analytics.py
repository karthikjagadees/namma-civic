"""
Civic Hotspots & Geospatial Intelligence API Endpoints
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import DBSession, RequireOfficer
from app.services.duplicate_review_service import DuplicateReviewService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Civic Hotspots & Geospatial Analytics"])


@router.get("/summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    """Retrieve city-wide Civic Health Index, resolution rate, and category distribution."""
    return await AnalyticsService.get_city_health_summary(db)


@router.get("/hotspots")
async def get_geospatial_hotspots(
    radius_m: float = Query(500.0, description="Spatial clustering radius in meters"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve clustered chronic defect zones detected across city coordinates."""
    return await AnalyticsService.get_geospatial_hotspots(db, cluster_radius_m=radius_m)


@router.get("/departments")
async def get_department_scorecard(db: AsyncSession = Depends(get_db)):
    """Retrieve departmental SLA performance, case throughput, and efficiency scores."""
    return await AnalyticsService.get_department_scorecard(db)


@router.get("/duplicate-operations")
async def get_duplicate_operations_analytics(officer: RequireOfficer, db: DBSession):
    """Return operational duplicate and review metrics to municipal staff."""
    return await DuplicateReviewService.analytics(db)
