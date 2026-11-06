"""
Namma Civic — Complaint Service
Business logic for complaint creation, retrieval, updates, and timeline tracking.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.tracking import generate_tracking_id
from app.deduplication.images import compute_phash_for_url
from app.models.complaint import (
    Complaint,
    ComplaintCategory,
    ComplaintMedia,
    ComplaintStatus,
    ComplaintTimeline,
    PriorityLevel,
)
from app.models.user import User, UserRole
from app.services.incident_service import create_initial_incident_for_report
from app.schemas.complaint import (
    ComplaintCreateRequest,
    ComplaintUpdateRequest,
)

logger = get_logger(__name__)


class ComplaintNotFoundError(Exception):
    """Raised when a complaint lookup fails."""


class UnauthorizedComplaintActionError(Exception):
    """Raised when a user lacks permission to modify a complaint."""


class ComplaintService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _new_tracking_id(self) -> str:
        """Return a tracking ID not used by any stored complaint.

        The unique index is the real guarantee; this pre-check just avoids a
        failed insert in the (1 in ~10^12) event of a random collision.
        """
        for _ in range(10):
            candidate = generate_tracking_id()
            taken = await self.db.scalar(
                select(Complaint.id).where(Complaint.tracking_id == candidate)
            )
            if taken is None:
                return candidate
        raise RuntimeError("Could not allocate a unique tracking ID")

    async def create_complaint(
        self,
        data: ComplaintCreateRequest,
        citizen_id: str,
        idempotency_key: str | None = None,
    ) -> Complaint:
        """
        Create a new civic complaint with media attachments and initial timeline entry.
        """
        complaint = Complaint(
            tracking_id=await self._new_tracking_id(),
            citizen_id=citizen_id,
            title=data.title.strip(),
            description=data.description.strip(),
            idempotency_key=idempotency_key,
            category=data.category,
            status=ComplaintStatus.pending,
            priority=PriorityLevel.medium,
            severity=5,
            latitude=data.latitude,
            longitude=data.longitude,
            address=data.address.strip() if data.address else None,
            landmark=data.landmark.strip() if data.landmark else None,
            location_confidence=data.location_confidence,
            location_accuracy_m=data.location_accuracy_m,
            source=data.source,
        )
        self.db.add(complaint)
        await self.db.flush()
        await create_initial_incident_for_report(self.db, complaint)

        # Add media attachments if provided
        if data.media:
            for item in data.media:
                media = ComplaintMedia(
                    complaint_id=complaint.id,
                    media_type=item.media_type,
                    file_url=item.file_url,
                    file_name=item.file_name,
                    file_size=item.file_size,
                    mime_type=item.mime_type,
                    caption=item.caption,
                    perceptual_hash=(
                        compute_phash_for_url(item.file_url)
                        if item.media_type.value == "image"
                        else None
                    ),
                )
                self.db.add(media)

        # Initial timeline entry
        timeline = ComplaintTimeline(
            complaint_id=complaint.id,
            status=ComplaintStatus.pending,
            changed_by_id=citizen_id,
            note="Complaint submitted by citizen. Awaiting AI triage.",
        )
        self.db.add(timeline)
        await self.db.flush()

        logger.info(
            "Complaint created",
            complaint_id=complaint.id,
            citizen_id=citizen_id,
            category=complaint.category.value,
        )

        # Trigger citizen email confirmation
        try:
            import asyncio
            from app.models.user import User
            from app.services.email_service import EmailService
            user_res = await self.db.execute(select(User).where(User.id == citizen_id))
            citizen = user_res.scalar_one_or_none()
            if citizen and citizen.email:
                asyncio.create_task(
                    EmailService.send_complaint_confirmation(
                        complaint=complaint,
                        citizen_email=citizen.email,
                        citizen_name=citizen.full_name
                    )
                )
        except Exception as e:
            logger.warning(f"Failed triggering confirmation email: {e}")

        return await self.get_by_id(complaint.id)

    async def get_by_id(self, complaint_id: str) -> Complaint:
        """
        Retrieve complaint by ID with loaded media, timeline, and AI analysis relationships.
        """
        query = (
            select(Complaint)
            .options(
                selectinload(Complaint.media),
                selectinload(Complaint.timeline),
                selectinload(Complaint.ai_analysis),
            )
            .where(Complaint.id == complaint_id)
        )
        result = await self.db.execute(query)
        complaint = result.scalar_one_or_none()
        if not complaint:
            raise ComplaintNotFoundError(f"Complaint not found: {complaint_id}")
        return complaint

    async def list_complaints(
        self,
        citizen_id: Optional[str] = None,
        category: Optional[ComplaintCategory] = None,
        status: Optional[ComplaintStatus] = None,
        priority: Optional[PriorityLevel] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Tuple[List[Complaint], int, int]:
        """
        List complaints with filtering and pagination.
        Returns: (items, total_count, total_pages)
        """
        base_query = select(Complaint)

        if citizen_id:
            base_query = base_query.where(Complaint.citizen_id == citizen_id)
        if category:
            base_query = base_query.where(Complaint.category == category)
        if status:
            base_query = base_query.where(Complaint.status == status)
        if priority:
            base_query = base_query.where(Complaint.priority == priority)

        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        total_count = (await self.db.execute(count_query)).scalar() or 0

        # Pagination & sorting
        offset = (page - 1) * limit
        paginated_query = (
            base_query.options(
                selectinload(Complaint.media),
                selectinload(Complaint.timeline),
            )
            .order_by(Complaint.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.db.execute(paginated_query)
        items = list(result.scalars().all())
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

        return items, total_count, total_pages

    async def get_citizen_summary(self, citizen_id: str) -> Dict[str, int]:
        """
        Get aggregated counts for a citizen's complaints dashboard:
        - total
        - active (pending, analyzing, verified, assigned, in_progress)
        - resolved
        - critical (priority is critical)
        """
        result = await self.db.execute(
            select(Complaint.status, Complaint.priority, func.count(Complaint.id))
            .where(Complaint.citizen_id == citizen_id)
            .group_by(Complaint.status, Complaint.priority)
        )
        rows = result.all()

        total = 0
        active = 0
        resolved = 0
        critical = 0

        active_statuses = {
            ComplaintStatus.pending,
            ComplaintStatus.analyzing,
            ComplaintStatus.verified,
            ComplaintStatus.assigned,
            ComplaintStatus.in_progress,
        }

        for st, pr, cnt in rows:
            total += cnt
            if st in active_statuses:
                active += cnt
            elif st == ComplaintStatus.resolved:
                resolved += cnt
            if pr == PriorityLevel.critical:
                critical += cnt

        return {
            "total": total,
            "active": active,
            "resolved": resolved,
            "critical": critical,
        }

    async def update_complaint(
        self,
        complaint_id: str,
        data: ComplaintUpdateRequest,
        user: User,
    ) -> Complaint:
        """
        Update complaint fields. If status is updated, add a timeline audit event.
        Citizens can only update their own complaints if still 'pending'.
        Officers and admins can update any complaint.
        """
        complaint = await self.get_by_id(complaint_id)

        if any(value is not None for value in (data.title, data.description, data.category)):
            raise UnauthorizedComplaintActionError(
                "Submitted report title, description, and category are immutable evidence. Add a follow-up note instead."
            )

        # Check permissions
        is_owner = complaint.citizen_id == user.id
        is_staff = user.role in (UserRole.officer, UserRole.admin)

        if not is_staff and not (is_owner and complaint.status == ComplaintStatus.pending):
            raise UnauthorizedComplaintActionError(
                "You do not have permission to modify this complaint."
            )

        status_changed = False
        old_status = complaint.status

        if data.title is not None:
            complaint.title = data.title.strip()
        if data.description is not None:
            complaint.description = data.description.strip()
        if data.category is not None:
            complaint.category = data.category
        if data.priority is not None and is_staff:
            complaint.priority = data.priority
        if data.severity is not None and is_staff:
            complaint.severity = data.severity
        if data.department_id is not None and is_staff:
            complaint.department_id = data.department_id
        if data.assigned_officer_id is not None and is_staff:
            complaint.assigned_officer_id = data.assigned_officer_id

        if data.status is not None and data.status != old_status and is_staff:
            complaint.status = data.status
            status_changed = True
            if data.status == ComplaintStatus.resolved:
                complaint.resolved_at = datetime.now(timezone.utc)

        if status_changed or data.note:
            timeline_note = data.note or f"Status changed from {old_status.value} to {complaint.status.value}"
            timeline = ComplaintTimeline(
                complaint_id=complaint.id,
                status=complaint.status,
                changed_by_id=user.id,
                note=timeline_note,
            )
            complaint.timeline.append(timeline)

        await self.db.flush()
        await self.db.refresh(complaint, attribute_names=["updated_at", "resolved_at"])
        logger.info("Complaint updated", complaint_id=complaint.id, updated_by=user.id)
        return complaint
