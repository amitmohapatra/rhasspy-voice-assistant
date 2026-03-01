"""Authentication routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import DbSession, CurrentUser
from src.core.exceptions import AuthenticationError, ValidationError
from src.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse
from src.services.user_service import UserService

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserCreate,
    db: DbSession,
) -> UserResponse:
    """Register a new user."""
    try:
        service = UserService(db)
        user = await service.register(data)
        return UserResponse.model_validate(user)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    db: DbSession,
) -> TokenResponse:
    """Login and get access tokens."""
    try:
        service = UserService(db)
        return await service.login(data.email, data.password)
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: DbSession,
) -> TokenResponse:
    """Refresh access token."""
    from src.core.security import verify_refresh_token, create_access_token, create_refresh_token
    from uuid import UUID

    try:
        payload = verify_refresh_token(refresh_token)
        user_id = UUID(payload["sub"])

        # Verify user still exists and is active
        from src.models.user import User
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Generate new tokens
        token_data = {
            "sub": str(user.id),
            "email": user.email,
        }

        return TokenResponse(
            access_token=create_access_token(token_data),
            refresh_token=create_refresh_token(token_data),
            expires_in=30 * 60,
        )

    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUser,
) -> UserResponse:
    """Get current user."""
    return UserResponse.model_validate(current_user)
