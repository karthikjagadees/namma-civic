"""
Namma Civic — User Service
Business logic for user CRUD operations.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest

logger = get_logger(__name__)


class UserAlreadyExistsError(Exception):
    """Raised when registering with an already-used email."""


class UserNotFoundError(Exception):
    """Raised when a user lookup by ID or email fails."""


class InvalidCredentialsError(Exception):
    """Raised when email/password combo is wrong."""


class UserInactiveError(Exception):
    """Raised when an inactive user tries to log in."""


class UserService:

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Registration ──────────────────────────────────────────

    async def register(
        self,
        data: RegisterRequest,
        role: UserRole = UserRole.citizen,
    ) -> User:
        """Create a new user. Raises UserAlreadyExistsError if email taken."""
        existing = await self._get_by_email(data.email)
        if existing:
            raise UserAlreadyExistsError(f"Email already registered: {data.email}")

        user = User(
            email=data.email.lower().strip(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name.strip(),
            phone=data.phone,
            role=role,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.flush()  # get ID without committing

        logger.info("User registered", user_id=user.id, email=user.email, role=role)
        return user

    # ── Authentication ────────────────────────────────────────

    async def authenticate(self, email: str, password: str) -> User:
        """
        Verify email + password.

        Raises:
            InvalidCredentialsError: Wrong email or password.
            UserInactiveError:       Account deactivated.
        """
        user = await self._get_by_email(email.lower().strip())
        if not user or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError("Invalid email or password")
        if not user.is_active:
            raise UserInactiveError("Account is deactivated")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)
        await self.db.flush()

        logger.info("User authenticated", user_id=user.id, email=user.email)
        return user

    # ── Lookups ───────────────────────────────────────────────

    async def get_by_id(self, user_id: str) -> User:
        """Return user by ID. Raises UserNotFoundError if not found."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise UserNotFoundError(f"User not found: {user_id}")
        return user

    async def _get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    # ── Update ────────────────────────────────────────────────

    async def update_profile(
        self,
        user_id: str,
        full_name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> User:
        user = await self.get_by_id(user_id)
        if full_name is not None:
            user.full_name = full_name.strip()
        if phone is not None:
            user.phone = phone
        await self.db.flush()
        return user

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        user = await self.get_by_id(user_id)
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")
        user.hashed_password = hash_password(new_password)
        await self.db.flush()
        logger.info("Password changed", user_id=user_id)

    # ── Admin ─────────────────────────────────────────────────

    async def set_active(self, user_id: str, active: bool) -> User:
        user = await self.get_by_id(user_id)
        user.is_active = active
        await self.db.flush()
        return user

    async def set_role(self, user_id: str, role: UserRole) -> User:
        user = await self.get_by_id(user_id)
        user.role = role
        await self.db.flush()
        logger.info("Role changed", user_id=user_id, new_role=role)
        return user
