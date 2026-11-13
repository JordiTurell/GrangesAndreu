"""Lógica de negocio de autenticación."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import ValidationError
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

from .entities import User, UserRole
from .schemas import TokenResponse, UserCreate

logger = logging.getLogger(__name__)

_ADMIN_VARIABLES = {
    "email": "INITIAL_ADMIN_EMAIL",
    "username": "INITIAL_ADMIN_USERNAME",
    "password": "INITIAL_ADMIN_PASSWORD",
}


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
        role=UserRole.USER.value,
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


def ensure_initial_admin(
    db: Session, *, email: str, username: str, password: str
) -> Literal["created", "promoted", "unchanged"]:
    """Crea o promueve al primer administrador (contrato §4.5); idempotente y sin filtrar la contraseña."""
    values = {"email": email, "username": username, "password": password}
    missing = [_ADMIN_VARIABLES[name] for name, value in values.items() if not value.strip()]
    if len(missing) == len(values):
        return "unchanged"
    if missing:
        raise RuntimeError(
            "INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_USERNAME e INITIAL_ADMIN_PASSWORD deben "
            f"definirse juntas (faltan: {', '.join(missing)})"
        )

    try:
        payload = UserCreate(username=username, email=email, password=password)
    except ValidationError as exc:
        # Solo nombres de variable y tipos de error: el texto original incluye la entrada.
        details = ", ".join(
            f"{_ADMIN_VARIABLES.get(str(error['loc'][0]), 'INITIAL_ADMIN_*')} no es válida ({error['type']})"
            for error in exc.errors(include_input=False, include_url=False)
        )
        raise RuntimeError(details) from None

    already_admin = db.execute(
        select(User.id).where(User.role == UserRole.ADMIN.value).limit(1)
    ).first()
    if already_admin is not None:
        logger.info("Primer administrador: ya existe un admin; se ignoran INITIAL_ADMIN_*")
        return "unchanged"

    existing = get_user_by_email(db, str(payload.email))
    if existing is not None:
        existing.role = UserRole.ADMIN.value
        db.commit()
        if not existing.is_active:
            logger.warning(
                "Primer administrador: el usuario id=%s está inactivo y no podrá iniciar sesión",
                existing.id,
            )
        logger.info(
            "Primer administrador promovido: id=%s username=%s", existing.id, existing.username
        )
        return "promoted"

    if get_user_by_username(db, payload.username) is not None:
        raise RuntimeError("INITIAL_ADMIN_USERNAME ya pertenece a otro usuario")

    admin = User(
        username=payload.username,
        email=str(payload.email).lower(),
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    logger.info("Primer administrador creado: id=%s username=%s", admin.id, admin.username)
    return "created"