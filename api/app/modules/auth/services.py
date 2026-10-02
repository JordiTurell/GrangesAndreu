"""Lógica de negocio de autenticación."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.shared.exceptions import AuthenticationError, ConflictError

from .entities import User
from .schemas import TokenResponse, UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(func.lower(User.email) == email.lower())
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_username(db: Session, username: str) -> User | None:
    stmt = select(User).where(func.lower(User.username) == username.lower())
    return db.execute(stmt).scalar_one_or_none()


def register_user(db: Session, payload: UserCreate) -> User:
    if get_user_by_email(db, payload.email):
        raise ConflictError("El email ya está registrado")
    if get_user_by_username(db, payload.username):
        raise ConflictError("El nombre de usuario ya está registrado")

    user = User(
        username=payload.username,
        email=str(payload.email).lower(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    # Mismo mensaje para usuario inexistente o contraseña errónea: evita enumeración de cuentas.
    if user is None or not verify_password(password, user.hashed_password):
        raise AuthenticationError("Credenciales inválidas")
    if not user.is_active:
        raise AuthenticationError("La cuenta está desactivada")
    return user


def build_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def refresh_tokens(db: Session, refresh_token: str) -> TokenResponse:
    payload = decode_token(refresh_token, "refresh")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("Usuario no válido o inactivo")
    return build_tokens(user)