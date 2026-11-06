"""
Admin Enterprise Control API Endpoints
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.deps import DBSession, RequireAdmin
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Admin Enterprise Control"])


class UserUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, description="citizen, officer, or admin")
    is_active: Optional[bool] = None
    department_id: Optional[str] = None


class DepartmentCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    code: str = Field(..., min_length=2, max_length=20)
    description: Optional[str] = None
    head_name: Optional[str] = None
    contact_email: Optional[str] = None


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None, description="Filter by role: citizen, officer, admin"),
    search: Optional[str] = Query(None, description="Search by email or name"),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    admin: RequireAdmin = None,
    db: DBSession = None,
):
    """List all registered users across the platform."""
    return await AdminService.list_users(
        session=db,
        role_filter=role,
        search=search,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UserUpdateRequest,
    admin: RequireAdmin = None,
    db: DBSession = None,
):
    """Update user role, account activation status, or department."""
    try:
        return await AdminService.update_user(
            session=db,
            user_id=user_id,
            role=body.role,
            is_active=body.is_active,
            department_id=body.department_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/departments")
async def list_departments(
    admin: RequireAdmin = None,
    db: DBSession = None,
):
    """List departments and their live active caseloads."""
    return await AdminService.list_departments_with_caseload(session=db)


@router.post("/departments", status_code=status.HTTP_201_CREATED)
async def create_department(
    body: DepartmentCreateRequest,
    admin: RequireAdmin = None,
    db: DBSession = None,
):
    """Add a new municipal department."""
    return await AdminService.create_department(
        session=db,
        name=body.name,
        code=body.code,
        description=body.description,
        head_name=body.head_name,
        contact_email=body.contact_email,
    )


@router.get("/system/metrics")
async def get_system_health(
    admin: RequireAdmin = None,
    db: DBSession = None,
):
    """Inspect overall system health, AI provider state, and platform metrics."""
    return await AdminService.get_system_health_metrics(session=db)


@router.get("/audit-logs")
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    admin: RequireAdmin = None,
    db: DBSession = None,
):
    """Retrieve recent city-wide timeline audit logs."""
    return await AdminService.get_global_audit_logs(session=db, limit=limit)
