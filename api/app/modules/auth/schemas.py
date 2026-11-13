from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field
from pydantic_core import PydanticCustomError

from app.core.security import MAX_PASSWORD_BYTES, exceeds_password_limit

from .entities import UserRole


def _check_password_bytes(password: str) -> str:
    if exceeds_password_limit(password):
        raise PydanticCustomError(
            "password_too_long",
            "La contraseña no puede superar los {max_bytes} bytes en UTF-8",
            {"max_bytes": MAX_PASSWORD_BYTES},
        )
    return password


NewPassword = Annotated[
    str,
    # Field antes que AfterValidator: así el 422 conserva el tipo `string_too_short` (no `too_short`).
    Field(
        min_length=8,
        description="Mínimo 8 caracteres y máximo 72 bytes en UTF-8 (límite de bcrypt).",
    ),
    AfterValidator(_check_password_bytes),
]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: EmailStr
    password: NewPassword


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool
    role: UserRole
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=MAX_PASSWORD_BYTES)


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
