"""User service for authentication and user management."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from src.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from src.models.user import User
from src.schemas.user import UserCreate, UserUpdate, TokenResponse


class UserService:
    """Service for user management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def register(self, data: UserCreate) -> User:
        """Register a new user.

        Args:
            data: User registration data

        Returns:
            Created user
        """
        # Check if email already exists
        existing = await self._get_by_email(data.email)
        if existing:
            raise ValidationError(
                message="Email already registered",
                details={"email": data.email},
            )

        # Create user
        user = User(
            email=data.email,
            hashed_password=hash_password(data.password),
            full_name=data.name,
            is_active=True,
            is_verified=False,
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def login(self, email: str, password: str) -> TokenResponse:
        """Authenticate user and return tokens.

        Args:
            email: User email
            password: User password

        Returns:
            Token response with access and refresh tokens
        """
        user = await self._get_by_email(email)

        if not user:
            raise AuthenticationError(message="Invalid email or password")

        if not verify_password(password, user.password_hash):
            raise AuthenticationError(message="Invalid email or password")

        if not user.is_active:
            raise AuthenticationError(message="Account is disabled")

        # Update last login
        user.last_login_at = datetime.utcnow()
        await self.db.flush()

        # Generate tokens
        token_data = {
            "sub": str(user.id),
            "email": user.email,
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=30 * 60,  # 30 minutes
        )

    async def get(self, user_id: UUID) -> User:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise NotFoundError(message="User not found", resource="user")

        return user

    async def update(self, user_id: UUID, data: UserUpdate) -> User:
        """Update user."""
        user = await self.get(user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)

        await self.db.flush()
        await self.db.refresh(user)

        return user

    async def list_users(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[User]:
        """List users."""
        query = (
            select(User)
            .offset(skip)
            .limit(limit)
            .order_by(User.created_at.desc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def _get_by_email(self, email: str) -> User | None:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()
