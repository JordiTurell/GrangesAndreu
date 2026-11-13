"""Unitarios de roles (contrato auth-completo §7.1: RL-03, RL-06 a RL-10; ADR-007).

Solo usan BD temporales (fixtures `engine` y `db_session`); nunca ``api/data/app.db``. RL-06 y RL-07 montan
la ruta de prueba P-1 (§7) porque la épica no añade ningún endpoint solo-admin.
"""

from __future__ import annotations

import enum
from collections.abc import Iterator

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_db
from app.core.security import create_access_token, decode_token, require_role
from app.modules.auth.entities import User, UserRole
from app.modules.auth.routes import router as auth_router
from app.modules.auth.schemas import UserCreate, UserRead
from app.shared.exceptions import PermissionDeniedError, register_exception_handlers

MENSAJE_403 = "No tienes permisos para realizar esta acción"


def _crear_usuario(db: Session, username: str, role: str, *, is_active: bool = True) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password="no-se-usa",  # sin bcrypt: estos tests no hacen login
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _cabecera(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def cliente_p1(engine: Engine) -> Iterator[TestClient]:
    """Patrón P-1: app propia con una ruta solo-admin y `get_db` sobre la BD del test."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth_router, prefix="/api")
    app.add_api_route(
        "/solo-admin", lambda: {"ok": True}, dependencies=[Depends(require_role(UserRole.ADMIN))]
    )
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


# --- Esquemas y enum -------------------------------------------------------------------------


def test_rl_10_user_role_es_strenum_con_admin_y_user() -> None:
    assert issubclass(UserRole, enum.StrEnum)
    assert {rol.name: rol.value for rol in UserRole} == {"ADMIN": "admin", "USER": "user"}


def test_rl_03_user_create_no_admite_rol_ni_is_active() -> None:
    assert "role" not in UserCreate.model_fields
    assert "is_active" not in UserCreate.model_fields
    # Un role en el payload se ignora (EP-02-D2): no llega al modelo.
    payload = UserCreate.model_validate(
        {"username": "ana", "email": "ana@example.com", "password": "secreto-123", "role": "admin"}
    )
    assert not hasattr(payload, "role")


def test_user_read_incluye_role_y_no_datos_internos() -> None:
    assert "role" in UserRead.model_fields
    assert "token_version" not in UserRead.model_fields
    assert "hashed_password" not in UserRead.model_fields


# --- require_role ----------------------------------------------------------------------------


def test_rl_08_require_role_sin_roles_lanza_value_error() -> None:
    with pytest.raises(ValueError):
        require_role()


def test_rl_06_sin_token_401_con_www_authenticate(cliente_p1: TestClient) -> None:
    respuesta = cliente_p1.get("/solo-admin")

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "unauthorized"
    assert respuesta.headers["WWW-Authenticate"] == "Bearer"


def test_rl_06_token_invalido_401(cliente_p1: TestClient) -> None:
    respuesta = cliente_p1.get("/solo-admin", headers={"Authorization": "Bearer no-es-un-jwt"})

    assert respuesta.status_code == 401


def test_rl_06_user_recibe_403_forbidden_sin_www_authenticate(
    cliente_p1: TestClient, db_session: Session
) -> None:
    user = _crear_usuario(db_session, "ana", "user")

    respuesta = cliente_p1.get("/solo-admin", headers=_cabecera(user))

    assert respuesta.status_code == 403
    assert respuesta.json() == {"error": {"code": "forbidden", "message": MENSAJE_403}}
    assert "WWW-Authenticate" not in respuesta.headers


def test_rl_06_admin_recibe_200(cliente_p1: TestClient, db_session: Session) -> None:
    admin = _crear_usuario(db_session, "root", "admin")

    respuesta = cliente_p1.get("/solo-admin", headers=_cabecera(admin))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}


def test_rl_06_admin_inactivo_recibe_401(cliente_p1: TestClient, db_session: Session) -> None:
    admin = _crear_usuario(db_session, "root", "admin", is_active=False)

    respuesta = cliente_p1.get("/solo-admin", headers=_cabecera(admin))

    assert respuesta.status_code == 401


def test_rl_07_el_rol_se_lee_de_la_bd_y_no_va_en_el_jwt(
    cliente_p1: TestClient, db_session: Session
) -> None:
    user = _crear_usuario(db_session, "ana", "user")
    cabecera = _cabecera(user)
    assert cliente_p1.get("/solo-admin", headers=cabecera).status_code == 403

    user.role = UserRole.ADMIN.value
    db_session.commit()

    # Mismo access token: pasa de 403 a 200 porque el rol no está en sus claims.
    assert cliente_p1.get("/solo-admin", headers=cabecera).status_code == 200
    assert "role" not in decode_token(cabecera["Authorization"].split()[1], "access")


def test_require_role_admite_varios_roles_sin_jerarquia(db_session: Session) -> None:
    dependencia = require_role(UserRole.ADMIN, UserRole.USER)

    assert dependencia(_crear_usuario(db_session, "ana", "user")).username == "ana"
    assert dependencia(_crear_usuario(db_session, "root", "admin")).username == "root"


def test_require_role_solo_user_rechaza_al_admin(db_session: Session) -> None:
    admin = _crear_usuario(db_session, "root", "admin")

    with pytest.raises(PermissionDeniedError, match=MENSAJE_403):
        require_role(UserRole.USER)(admin)


# --- CHECK y valores por defecto de la entidad -----------------------------------------------


def test_rl_09_check_rechaza_roles_desconocidos(engine: Engine) -> None:
    with pytest.raises(IntegrityError):
        with engine.begin() as conexion:
            conexion.execute(
                text(
                    "INSERT INTO users (username, email, hashed_password, is_active, created_at, role) "
                    "VALUES ('x', 'x@example.com', 'h', 1, '2026-01-01 00:00:00', 'root')"
                )
            )

    with engine.begin() as conexion:
        conexion.execute(
            text(
                "INSERT INTO users (username, email, hashed_password, is_active, created_at) "
                "VALUES ('y', 'y@example.com', 'h', 1, '2026-01-01 00:00:00')"
            )
        )
    with pytest.raises(IntegrityError):
        with engine.begin() as conexion:
            conexion.execute(text("UPDATE users SET role = 'root' WHERE username = 'y'"))


def test_rl_09_sin_role_en_sql_crudo_queda_user_y_token_version_cero(engine: Engine) -> None:
    with engine.begin() as conexion:
        conexion.execute(
            text(
                "INSERT INTO users (username, email, hashed_password, is_active, created_at) "
                "VALUES ('z', 'z@example.com', 'h', 1, '2026-01-01 00:00:00')"
            )
        )
        fila = conexion.execute(text("SELECT role, token_version FROM users")).one()

    assert tuple(fila) == ("user", 0)


def test_entidad_declara_los_defaults_y_el_check_de_op003(engine: Engine) -> None:
    columnas = {c.name: c for c in User.__table__.columns}

    assert str(columnas["role"].server_default.arg) == "'user'"
    assert str(columnas["token_version"].server_default.arg) == "0"
    assert columnas["role"].nullable is False
    assert columnas["token_version"].nullable is False
    assert "ck_users_role" in {c.name for c in User.__table__.constraints}


def test_usuario_nuevo_por_orm_es_user_con_token_version_cero(db_session: Session) -> None:
    user = User(username="ana", email="ana@example.com", hashed_password="h")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.role == "user"
    assert user.token_version == 0
