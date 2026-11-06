"""
Namma Civic — Authentication API Router
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/me
PUT  /api/auth/me
POST /api/auth/change-password
"""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, DBSession
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import UserRole
from app.schemas.auth import (
    LoginRequest,
    PasswordChangeRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserUpdateRequest,
)
from app.services.user_service import (
    InvalidCredentialsError,
    UserAlreadyExistsError,
    UserInactiveError,
    UserService,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Register ─────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen account",
)
async def register(body: RegisterRequest, db: DBSession) -> TokenResponse:
    """
    Register a new user (citizen role by default).
    Returns JWT access token immediately so the user is logged in.
    """
    svc = UserService(db)
    try:
        user = await svc.register(body, role=UserRole.citizen)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


# ── Login ─────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and receive a JWT access token",
)
async def login(body: LoginRequest, db: DBSession) -> TokenResponse:
    """
    Authenticate with email + password.
    Returns JWT access token.
    """
    svc = UserService(db)
    try:
        user = await svc.authenticate(body.email, body.password)
    except (InvalidCredentialsError, UserInactiveError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(
        subject=user.id,
        role=user.role.value,
        expires_delta=timedelta(minutes=settings.jwt_expire_minutes),
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_expire_minutes * 60,
        user=UserOut.model_validate(user),
    )


# ── Me ────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)


@router.put(
    "/me",
    response_model=UserOut,
    summary="Update current user profile",
)
async def update_me(
    body: UserUpdateRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> UserOut:
    svc = UserService(db)
    user = await svc.update_profile(
        user_id=current_user.id,
        full_name=body.full_name,
        phone=body.phone,
    )
    return UserOut.model_validate(user)


# ── Password Change ───────────────────────────────────────────

@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change password for current user",
)
async def change_password(
    body: PasswordChangeRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> Response:
    svc = UserService(db)
    try:
        await svc.change_password(
            user_id=current_user.id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
