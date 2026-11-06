"""
Civic Intelligence & Geospatial Hotspot Analytics Service
Computes spatial defect clusters, chronic corridors, department scorecards, and city health score.
"""
from datetime import datetime, timezone
import math
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.complaint import Complaint, ComplaintStatus, PriorityLevel
from app.models.department import Department
from app.services.sla_service import SLAService


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in meters."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


class AnalyticsService:
    """Civic intelligence analytics and geospatial hotspot clustering."""

    @staticmethod
    async def get_geospatial_hotspots(session: AsyncSession, cluster_radius_m: float = 500.0) -> List[Dict[str, Any]]:
        """
        Group complaints into spatial clusters within radius to detect chronic failure zones.
        """
        stmt = (
            select(Complaint)
            .where(Complaint.latitude.isnot(None), Complaint.longitude.isnot(None))
            .options(selectinload(Complaint.media), selectinload(Complaint.timeline))
        )
        res = await session.execute(stmt)
        complaints = res.scalars().all()

        clusters: List[Dict[str, Any]] = []
        visited = set()

        for i, c1 in enumerate(complaints):
            if c1.id in visited:
                continue

            cluster_members = [c1]
            visited.add(c1.id)

            for j, c2 in enumerate(complaints):
                if c2.id in visited:
                    continue

                dist = haversine_distance_m(c1.latitude, c1.longitude, c2.latitude, c2.longitude)
                if dist <= cluster_radius_m:
                    cluster_members.append(c2)
                    visited.add(c2.id)

            # Calculate centroid
            avg_lat = sum(m.latitude for m in cluster_members) / len(cluster_members)
            avg_lng = sum(m.longitude for m in cluster_members) / len(cluster_members)
            
            # Dominant category & severity
            categories = [m.category.value if hasattr(m.category, 'value') else str(m.category) for m in cluster_members]
            dom_cat = max(set(categories), key=categories.count)
            avg_severity = round(sum(m.severity for m in cluster_members) / len(cluster_members), 1)

            # Zone risk rating
            count = len(cluster_members)
            if count >= 3 or avg_severity >= 8:
                zone_type = "CRITICAL_CHRONIC_ZONE"
                risk_label = "HIGH ALERT"
            elif count >= 2:
                zone_type = "RECURRENT_DEFECT_CORRIDOR"
                risk_label = "ELEVATED"
            else:
                zone_type = "LOCALIZED_INCIDENT"
                risk_label = "ROUTINE"

            clusters.append({
                "cluster_id": f"ZONE-{len(clusters)+1:02d}",
                "centroid": {"latitude": round(avg_lat, 5), "longitude": round(avg_lng, 5)},
                "incident_count": count,
                "primary_category": dom_cat,
                "average_severity": avg_severity,
                "zone_type": zone_type,
                "risk_label": risk_label,
                "nearest_address": cluster_members[0].address or "Municipal Ward Alpha",
                "sample_incident_ids": [str(m.id)[:8].upper() for m in cluster_members[:4]]
            })

        # Sort clusters by incident count descending
        clusters.sort(key=lambda x: (x["incident_count"], x["average_severity"]), reverse=True)
        return clusters

    @staticmethod
    async def get_department_scorecard(session: AsyncSession) -> List[Dict[str, Any]]:
        """Department resolution efficiency and SLA compliance scorecard."""
        stmt_dept = select(Department)
        res_dept = await session.execute(stmt_dept)
        departments = res_dept.scalars().all()

        stmt_comp = select(Complaint).options(selectinload(Complaint.timeline))
        res_comp = await session.execute(stmt_comp)
        complaints = res_comp.scalars().all()

        scorecard = []
        for dept in departments:
            dept_complaints = [c for c in complaints if c.department_id == dept.id]
            total = len(dept_complaints)
            resolved = len([c for c in dept_complaints if c.status == ComplaintStatus.resolved])
            active = total - resolved
            
            # Breached count
            breached = 0
            for c in dept_complaints:
                sla = SLAService.calculate_sla(c)
                if sla["sla_status"] == "BREACHED":
                    breached += 1

            compliance_rate = round(((total - breached) / max(1, total)) * 100, 1)
            efficiency_score = min(100, max(40, int(compliance_rate * 0.7 + (resolved / max(1, total) * 30))))

            scorecard.append({
                "department_id": str(dept.id),
                "name": dept.name,
                "code": dept.code,
                "total_assigned": total,
                "active_cases": active,
                "resolved_cases": resolved,
                "breached_cases": breached,
                "sla_compliance_rate": compliance_rate,
                "efficiency_score": efficiency_score,
                "crew_readiness": "OPTIMAL" if compliance_rate > 80 else "MODERATE"
            })

        scorecard.sort(key=lambda d: d["efficiency_score"], reverse=True)
        return scorecard

    @staticmethod
    async def get_city_health_summary(session: AsyncSession) -> Dict[str, Any]:
        """Aggregate city civic health index (0-100) and high-level distribution."""
        stmt = select(Complaint).options(selectinload(Complaint.timeline))
        res = await session.execute(stmt)
        complaints = res.scalars().all()

        total = len(complaints)
        resolved = len([c for c in complaints if c.status == ComplaintStatus.resolved])
        pending = len([c for c in complaints if c.status in (ComplaintStatus.pending, ComplaintStatus.analyzing)])
        in_progress = len([c for c in complaints if c.status in (ComplaintStatus.assigned, ComplaintStatus.in_progress)])

        # Calculate Civic Health Index
        if total == 0:
            health_score = 95
        else:
            resolved_ratio = resolved / total
            penalty = sum(1 for c in complaints if SLAService.calculate_sla(c)["sla_status"] == "BREACHED") * 5
            health_score = max(35, min(99, int((resolved_ratio * 70 + 30) - penalty)))

        categories = {}
        for c in complaints:
            cat = c.category.value if hasattr(c.category, 'value') else str(c.category)
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "civic_health_index": health_score,
            "status_rating": "EXCELLENT" if health_score >= 85 else "GOOD" if health_score >= 70 else "ATTENTION_REQUIRED",
            "total_grievances": total,
            "resolved_count": resolved,
            "in_progress_count": in_progress,
            "pending_intake_count": pending,
            "resolution_rate": round((resolved / max(1, total)) * 100, 1),
            "category_distribution": categories,
            "telemetry_timestamp": datetime.now(timezone.utc).isoformat()
        }
