"""
Namma Civic — API Dependencies
FastAPI Depends() helpers for DB, authentication, and RBAC.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.models.complaint import Complaint
from app.models.user import User, UserRole
from app.services.user_service import UserNotFoundError, UserService

logger = get_logger(__name__)

# ── HTTP Bearer ───────────────────────────────────────────────
_bearer = HTTPBearer(auto_error=False)


# ── Typed DB dependency ───────────────────────────────────────
DBSession = Annotated[AsyncSession, Depends(get_db)]


# ── Current User ──────────────────────────────────────────────

async def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User:
    """
    Decode JWT and return the authenticated User.
    Raises HTTP 401 on any failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    try:
        payload = decode_access_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    svc = UserService(db)
    try:
        user = await svc.get_by_id(user_id)
    except UserNotFoundError:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    return user


# ── Optional current user (for public endpoints) ─────────────

async def get_current_user_optional(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> User | None:
    """Return current user or None if not authenticated."""
    if not credentials:
        return None
    try:
        return await get_current_user(db, credentials)
    except HTTPException:
        return None


# ── Typed current user dependency ─────────────────────────────
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


async def require_complaint_access(db: AsyncSession, complaint_id: str, user: User) -> Complaint:
    """Return a report only to its citizen or municipal staff; conceal foreign IDs."""
    complaint = await db.scalar(select(Complaint).where(Complaint.id == complaint_id))
    if complaint is None or (
        complaint.citizen_id != user.id and user.role not in (UserRole.officer, UserRole.admin)
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")
    return complaint


# ── RBAC helpers ──────────────────────────────────────────────

def require_role(*roles: UserRole):
    """
    Returns a FastAPI dependency that enforces role-based access.

    Usage:
        @router.get("/admin-only")
        async def admin_only(user: CurrentUser = Depends(require_role(UserRole.admin))):
            ...
    """
    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in roles]}",
            )
        return user
    return _check


# ── Convenience typed deps ────────────────────────────────────
RequireCitizen = Annotated[User, Depends(require_role(UserRole.citizen, UserRole.officer, UserRole.admin))]
RequireOfficer = Annotated[User, Depends(require_role(UserRole.officer, UserRole.admin))]
RequireAdmin = Annotated[User, Depends(require_role(UserRole.admin))]
