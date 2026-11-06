"""
Admin Enterprise Control Service
Handles user directory, RBAC elevation, department management, and system health metrics.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.mcp.client import mcp_client
from app.models.complaint import Complaint, ComplaintStatus, ComplaintTimeline
from app.models.department import Department
from app.models.user import User, UserRole


class AdminService:
    """Enterprise administrative management services."""

    @staticmethod
    async def list_users(
        session: AsyncSession,
        role_filter: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List and filter registered users with role and department info."""
        stmt = select(User).order_by(User.created_at.desc())
        conditions = []

        if role_filter:
            try:
                conditions.append(User.role == UserRole(role_filter))
            except ValueError:
                pass

        if is_active is not None:
            conditions.append(User.is_active == is_active)

        if search:
            search_pat = f"%{search.strip().lower()}%"
            conditions.append(
                (func.lower(User.email).like(search_pat)) | (func.lower(User.full_name).like(search_pat))
            )

        if conditions:
            stmt = stmt.where(*conditions)

        total_res = await session.execute(select(func.count()).select_from(stmt.subquery()))
        total_count = total_res.scalar_one()

        res = await session.execute(stmt.offset(skip).limit(limit))
        users = res.scalars().all()

        user_list = [
            {
                "id": str(u.id),
                "email": u.email,
                "full_name": u.full_name,
                "phone": u.phone,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "is_active": u.is_active,
                "is_verified": u.is_verified,
                "department_id": str(u.department_id) if u.department_id else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            }
            for u in users
        ]

        return {"total": total_count, "items": user_list, "skip": skip, "limit": limit}

    @staticmethod
    async def update_user(
        session: AsyncSession,
        user_id: str,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        department_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Modify user privileges, status, or assigned department."""
        stmt = select(User).where(User.id == user_id)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        if role:
            try:
                user.role = UserRole(role.lower())
            except ValueError:
                raise ValueError(f"Invalid role: {role}")

        if is_active is not None:
            user.is_active = is_active

        if department_id is not None:
            user.department_id = department_id if department_id != "" else None

        await session.commit()
        return {
            "id": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "is_active": user.is_active,
            "department_id": user.department_id,
        }

    @staticmethod
    async def list_departments_with_caseload(session: AsyncSession) -> List[Dict[str, Any]]:
        """List all departments and their live open complaint counts."""
        stmt_dept = select(Department).order_by(Department.name.asc())
        res_dept = await session.execute(stmt_dept)
        departments = res_dept.scalars().all()

        dept_list = []
        for d in departments:
            count_res = await session.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.department_id == d.id,
                    Complaint.status != ComplaintStatus.resolved,
                    Complaint.status != ComplaintStatus.rejected,
                )
            )
            active_count = count_res.scalar_one()

            dept_list.append({
                "id": str(d.id),
                "name": d.name,
                "code": d.code,
                "description": d.description,
                "head_name": getattr(d, "head_name", "Designated Chief Engineer"),
                "contact_email": getattr(d, "contact_email", getattr(d, "email", "dispatch@namma-civic.gov")),
                "active_caseload": active_count,
            })

        return dept_list

    @staticmethod
    async def create_department(
        session: AsyncSession,
        name: str,
        code: str,
        description: Optional[str] = None,
        head_name: Optional[str] = None,
        contact_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add new municipal department entity."""
        dept = Department(
            name=name,
            code=code.upper(),
            description=description,
            email=contact_email,
        )
        session.add(dept)
        await session.commit()
        return {
            "id": str(dept.id),
            "name": dept.name,
            "code": dept.code,
            "head_name": head_name or "Designated Chief Engineer",
            "contact_email": contact_email or "dispatch@namma-civic.gov",
        }

    @staticmethod
    async def get_system_health_metrics(session: AsyncSession) -> Dict[str, Any]:
        """Comprehensive operational status of AI, database, multi-agents, and MCP servers."""
        complaint_counts = await session.execute(
            select(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status)
        )
        status_map = {str(k.value if hasattr(k, "value") else k): v for k, v in complaint_counts.all()}

        user_counts = await session.execute(
            select(User.role, func.count(User.id)).group_by(User.role)
        )
        role_map = {str(k.value if hasattr(k, "value") else k): v for k, v in user_counts.all()}

        mcp_tools = mcp_client.list_tools()

        return {
            "system_name": "Namma Civic Autonomous Engine",
            "version": "2.5.0",
            "environment": str(settings.app_env.value if hasattr(settings.app_env, "value") else settings.app_env),
            "database_engine": "SQLite AsyncIO + WAL Mode",
            "ai_provider_active": "Mock Heuristic Provider (namma-civic-heuristic-v1)" if not settings.openai_api_key else "OpenAI GPT-4o",
            "langgraph_checkpointer": "MemorySaver In-Memory State Graph (Compiled)",
            "mcp_server_status": "ONLINE",
            "mcp_tools_active": len(mcp_tools),
            "telemetry_timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "complaints_by_status": status_map,
                "users_by_role": role_map,
            },
        }

    @staticmethod
    async def get_global_audit_logs(session: AsyncSession, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent city-wide timeline audit events."""
        stmt = (
            select(ComplaintTimeline)
            .order_by(ComplaintTimeline.created_at.desc())
            .limit(limit)
        )
        res = await session.execute(stmt)
        events = res.scalars().all()

        return [
            {
                "id": str(e.id),
                "complaint_id": str(e.complaint_id),
                "status": e.status.value if hasattr(e.status, "value") else str(e.status),
                "note": e.note,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ]
