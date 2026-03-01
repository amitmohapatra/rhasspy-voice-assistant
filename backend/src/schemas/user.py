"""User schemas with comprehensive Swagger documentation."""

from datetime import datetime

from pydantic import EmailStr, Field

from src.schemas.base import BaseSchema, IDMixin, TimestampMixin
class UserCreate(BaseSchema):
    """Schema for user registration.

    Creates a new user account.
    """

    email: EmailStr = Field(
        ...,
        description="User's email address. Must be unique across the platform.",
        json_schema_extra={"example": "john.doe@example.com"}
    )
    password: str = Field(
        ...,
        min_length=8,
        description="Password for the account. Must be at least 8 characters.",
        json_schema_extra={"example": "SecureP@ssw0rd123"}
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="User's full name.",
        json_schema_extra={"example": "John Doe"}
    )


class UserUpdate(BaseSchema):
    """Schema for updating user profile.

    All fields are optional. Only provided fields will be updated.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="User's full name.",
        json_schema_extra={"example": "John Smith"}
    )
    settings: dict | None = Field(
        default=None,
        description="User preferences and settings as a JSON object.",
        json_schema_extra={
            "example": {
                "theme": "dark",
                "language": "en-US",
                "notifications_enabled": True
            }
        }
    )


class UserResponse(BaseSchema, IDMixin, TimestampMixin):
    """Schema for user data in API responses.

    Contains all user information except sensitive fields like password.
    """

    email: str = Field(
        ...,
        description="User's email address.",
        json_schema_extra={"example": "john.doe@example.com"}
    )
    name: str = Field(
        ...,
        description="User's full name.",
        json_schema_extra={"example": "John Doe"}
    )
    is_active: bool = Field(
        ...,
        description="Whether the user account is active.",
        json_schema_extra={"example": True}
    )
    is_verified: bool = Field(
        ...,
        description="Whether the user's email has been verified.",
        json_schema_extra={"example": False}
    )
    last_login_at: datetime | None = Field(
        default=None,
        description="Timestamp of the user's last login.",
        json_schema_extra={"example": "2024-01-15T10:30:00Z"}
    )
    settings: dict = Field(
        default_factory=dict,
        description="User preferences and settings.",
        json_schema_extra={
            "example": {
                "theme": "light",
                "language": "en-US"
            }
        }
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "email": "john.doe@example.com",
                "name": "John Doe",
                "is_active": True,
                "is_verified": True,
                "last_login_at": "2024-01-15T10:30:00Z",
                "settings": {"theme": "dark", "language": "en-US"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-15T10:30:00Z"
            }
        }
    }


class UserLogin(BaseSchema):
    """Schema for user login.

    Authenticates the user and returns JWT tokens.
    """

    email: EmailStr = Field(
        ...,
        description="User's email address.",
        json_schema_extra={"example": "john.doe@example.com"}
    )
    password: str = Field(
        ...,
        description="User's password.",
        json_schema_extra={"example": "SecureP@ssw0rd123"}
    )


class TokenResponse(BaseSchema):
    """Schema for authentication token response.

    Contains the JWT access token and refresh token.
    Use the access_token in the Authorization header as 'Bearer <token>'.
    """

    access_token: str = Field(
        ...,
        description="JWT access token. Include in Authorization header as 'Bearer <token>'.",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )
    refresh_token: str = Field(
        ...,
        description="Refresh token for obtaining new access tokens.",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )
    token_type: str = Field(
        default="bearer",
        description="Token type. Always 'bearer'.",
        json_schema_extra={"example": "bearer"}
    )
    expires_in: int = Field(
        ...,
        description="Access token expiration time in seconds.",
        json_schema_extra={"example": 1800}
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJlbWFpbCI6ImpvaG4uZG9lQGV4YW1wbGUuY29tIiwiZXhwIjoxNzA1MzE0MjAwfQ.xxxxx",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJ0eXBlIjoicmVmcmVzaCIsImV4cCI6MTcwNTkxNTgwMH0.xxxxx",
                "token_type": "bearer",
                "expires_in": 1800
            }
        }
    }


class RefreshTokenRequest(BaseSchema):
    """Schema for token refresh request."""

    refresh_token: str = Field(
        ...,
        description="The refresh token obtained from login.",
        json_schema_extra={"example": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."}
    )


class PasswordChangeRequest(BaseSchema):
    """Schema for changing user password."""

    current_password: str = Field(
        ...,
        description="Current password for verification.",
        json_schema_extra={"example": "OldP@ssw0rd123"}
    )
    new_password: str = Field(
        ...,
        min_length=8,
        description="New password. Must be at least 8 characters.",
        json_schema_extra={"example": "NewSecureP@ssw0rd456"}
    )
