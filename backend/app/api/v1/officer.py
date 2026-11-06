"""
Officer Tactical Command API Endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import DBSession, RequireOfficer
from app.services.officer_service import OfficerService

router = APIRouter(prefix="/officer", tags=["Officer Tactical Command"])


class AssignRequest(BaseModel):
    officer_id: str = Field(..., description="Target officer UUID")
    reason: Optional[str] = Field(None, description="Reason for assignment / forced reassignment")
    force_override: bool = Field(False, description="Whether this is a forced reassignment due to neglected duty / SLA breach")
    notes: Optional[str] = Field(None, description="Administrative directive or instructions for the new officer")


class CrewDispatchRequest(BaseModel):
    crew_id: str = Field(..., description="Field crew code or identifier")
    department_code: str = Field(..., description="e.g. ROADS, WATER, ELECTRICITY")
    priority: str = Field("HIGH", description="Work order priority")
    instructions: str = Field("", description="Field instructions for crew")


@router.get("/roster")
async def get_officer_roster(
    officer: RequireOfficer = None,
    db: DBSession = None,
):
    """
    Retrieve active municipal officer roster with departments for duty assignment.
    """
    return await OfficerService.get_officer_roster(session=db)


@router.get("/queue")
async def get_officer_queue(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    department_id: Optional[str] = Query(None, description="Filter by department UUID or 'all'"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    officer: RequireOfficer = None,
    db: DBSession = None,
):
    """
    Retrieve live tactical case queue for the logged-in officer and department.
    """
    if department_id == "all":
        target_dept_id = "all"
        filter_officer_id = None
    elif department_id:
        target_dept_id = department_id
        filter_officer_id = None
    else:
        target_dept_id = str(officer.department_id) if officer.department_id else None
        filter_officer_id = str(officer.id)

    return await OfficerService.get_officer_queue(
        session=db,
        officer_id=filter_officer_id,
        department_id=target_dept_id,
        status_filter=status,
        priority_filter=priority,
        limit=limit,
        offset=offset,
    )


@router.get("/stats")
async def get_officer_stats(
    officer: RequireOfficer = None,
    db: DBSession = None,
):
    """
    Retrieve personal and departmental caseload, SLA compliance, and breach counts.
    """
    dept_id = str(officer.department_id) if officer.department_id else None
    return await OfficerService.get_officer_workload_stats(
        session=db,
        officer_id=str(officer.id),
        department_id=dept_id,
    )


@router.post("/assign/{complaint_id}")
async def assign_complaint(
    complaint_id: str,
    body: AssignRequest,
    officer: RequireOfficer = None,
    db: DBSession = None,
):
    """
    Assign a civic incident to an officer.
    """
    try:
        return await OfficerService.assign_complaint(
            session=db,
            complaint_id=complaint_id,
            officer_id=body.officer_id,
            reason=body.reason,
            force_override=body.force_override,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/dispatch-crew/{complaint_id}")
async def dispatch_crew(
    complaint_id: str,
    body: CrewDispatchRequest,
    officer: RequireOfficer = None,
    db: DBSession = None,
):
    """
    Directly dispatch a field crew via Model Context Protocol (MCP).
    """
    try:
        return await OfficerService.quick_crew_dispatch(
            session=db,
            complaint_id=complaint_id,
            crew_id=body.crew_id,
            department_code=body.department_code,
            priority=body.priority,
            instructions=body.instructions,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
