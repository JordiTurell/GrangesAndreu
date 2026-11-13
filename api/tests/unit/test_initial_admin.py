"""Unitarios de `ensure_initial_admin` (contrato auth-completo §4.5 y §7.3: AD-01 a AD-11).

Solo usan BD temporales (fixtures `engine` y `db_session`); nunca ``api/data/app.db``.
"""

from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.security import hash_password, verify_password
from app.modules.auth.entities import User, UserRole
from app.modules.auth.services import ensure_initial_admin

EMAIL = "admin@example.com"
USERNAME = "administrador"
PASSWORD = "Clave-Secreta-123"


def _contar(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User))


def _sembrar(
    db: Session,
    *,
    username: str = "ana",
    email: str = "ana@example.com",
    role: str = "user",
    is_active: bool = True,
    password: str = "contrasena-previa",
) -> User:
    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _llamar(db: Session, **cambios: str) -> str:
    valores = {"email": EMAIL, "username": USERNAME, "password": PASSWORD, **cambios}
    return ensure_initial_admin(db, **valores)


def test_ad_01_variables_vacias_no_hacen_nada_ni_acceden_a_la_bd(db_session: Session) -> None:
    class _SesionProhibida:
        def __getattr__(self, nombre: str) -> None:
            raise AssertionError("no debe acceder a la BD")

    assert _llamar(_SesionProhibida(), email="", username="  ", password="") == "unchanged"  # type: ignore[arg-type]
    assert _contar(db_session) == 0


@pytest.mark.parametrize(
    ("valores", "faltan"),
    [
        pytest.param({"username": "", "password": ""}, ["INITIAL_ADMIN_USERNAME", "INITIAL_ADMIN_PASSWORD"], id="solo-email"),
        pytest.param({"password": ""}, ["INITIAL_ADMIN_PASSWORD"], id="sin-contrasena"),
        pytest.param({"email": " "}, ["INITIAL_ADMIN_EMAIL"], id="email-en-blanco"),
    ],
)
def test_ad_02_variables_parciales_abortan_con_los_nombres_que_faltan(
    db_session: Session, valores: dict[str, str], faltan: list[str]
) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        _llamar(db_session, **valores)

    mensaje = str(excinfo.value)
    assert "deben definirse juntas" in mensaje
    assert mensaje.endswith(f"(faltan: {', '.join(faltan)})")
    assert PASSWORD not in mensaje
    assert _contar(db_session) == 0


@pytest.mark.parametrize(
    ("valores", "variable", "tipo"),
    [
        pytest.param({"password": "corta12"}, "INITIAL_ADMIN_PASSWORD", "string_too_short", id="7-caracteres"),
        pytest.param({"password": "a" * 71 + "ñ"}, "INITIAL_ADMIN_PASSWORD", "password_too_long", id="73-bytes"),
        pytest.param({"email": "no-es-un-email"}, "INITIAL_ADMIN_EMAIL", "value_error", id="email-invalido"),
        pytest.param({"username": "ab"}, "INITIAL_ADMIN_USERNAME", "string_too_short", id="usuario-2-caracteres"),
    ],
)
def test_ad_03_valor_invalido_da_runtime_error_sin_el_valor(
    db_session: Session, valores: dict[str, str], variable: str, tipo: str
) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        _llamar(db_session, **valores)

    mensaje = str(excinfo.value)
    assert variable in mensaje
    assert tipo in mensaje
    for valor in valores.values():
        assert valor not in mensaje
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True
    assert _contar(db_session) == 0


def test_ad_04_crea_el_admin_activo_con_email_en_minusculas(db_session: Session) -> None:
    assert _llamar(db_session, email="Admin@Example.COM") == "created"

    admin = db_session.scalar(select(User))
    assert admin.role == UserRole.ADMIN
    assert admin.is_active is True
    assert admin.email == "admin@example.com"
    assert admin.username == USERNAME
    assert admin.hashed_password != PASSWORD
    assert verify_password(PASSWORD, admin.hashed_password)


def test_ad_05_segunda_llamada_no_cambia_nada(db_session: Session) -> None:
    assert _llamar(db_session) == "created"
    hash_inicial = db_session.scalar(select(User.hashed_password))

    assert _llamar(db_session) == "unchanged"

    db_session.expire_all()
    assert _contar(db_session) == 1
    assert db_session.scalar(select(User.hashed_password)) == hash_inicial


def test_ad_06_promueve_al_usuario_existente_cambiando_solo_el_rol(db_session: Session) -> None:
    previo = _sembrar(db_session, username="ana", email=EMAIL, is_active=True)
    hash_previo, creado = previo.hashed_password, previo.created_at

    assert _llamar(db_session) == "promoted"

    db_session.expire_all()
    user = db_session.scalar(select(User))
    assert _contar(db_session) == 1
    assert user.role == UserRole.ADMIN
    assert user.username == "ana"
    assert user.is_active is True
    assert user.hashed_password == hash_previo
    assert user.created_at == creado
    assert verify_password("contrasena-previa", user.hashed_password)
    assert not verify_password(PASSWORD, user.hashed_password)


def test_ad_06_promueve_a_un_inactivo_sin_activarlo_y_avisa(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    _sembrar(db_session, email=EMAIL, is_active=False)
    caplog.set_level(logging.DEBUG)

    assert _llamar(db_session) == "promoted"

    db_session.expire_all()
    user = db_session.scalar(select(User))
    assert user.role == UserRole.ADMIN
    assert user.is_active is False
    assert any(r.levelno == logging.WARNING for r in caplog.records)


def test_ad_07_con_otro_admin_no_promueve_a_nadie(db_session: Session) -> None:
    _sembrar(db_session, username="jefe", email="jefe@example.com", role="admin")
    _sembrar(db_session, username="ana", email=EMAIL, role="user")

    assert _llamar(db_session) == "unchanged"

    db_session.expire_all()
    roles = dict(db_session.execute(select(User.username, User.role)).all())
    assert roles == {"jefe": "admin", "ana": "user"}


def test_ad_08_username_de_otro_usuario_aborta_sin_cambios(db_session: Session) -> None:
    _sembrar(db_session, username=USERNAME, email="otro@example.com")

    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_USERNAME ya pertenece a otro usuario"):
        _llamar(db_session)

    db_session.expire_all()
    assert _contar(db_session) == 1
    assert db_session.scalar(select(User.role)) == "user"


def test_ad_09_email_con_mayusculas_es_la_misma_cuenta(db_session: Session) -> None:
    _sembrar(db_session, username="ana", email="admin@example.com")

    assert _llamar(db_session, email="ADMIN@Example.com") == "promoted"
    assert _contar(db_session) == 1


def test_ad_10_la_contrasena_no_sale_en_logs(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)

    _llamar(db_session)
    _llamar(db_session)

    assert caplog.records
    assert PASSWORD not in caplog.text
    assert db_session.scalar(select(User.hashed_password)) not in caplog.text


def test_ad_10_la_contrasena_no_sale_en_logs_al_promover(
    db_session: Session, caplog: pytest.LogCaptureFixture
) -> None:
    _sembrar(db_session, email=EMAIL)
    caplog.set_level(logging.DEBUG)

    _llamar(db_session)

    assert PASSWORD not in caplog.text


def test_ad_10_settings_no_expone_la_contrasena(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", PASSWORD)
    configuracion = Settings(_env_file=None, debug=True, secret_key="x" * 40)

    assert PASSWORD not in repr(configuracion)
    assert PASSWORD not in str(configuracion)
    assert configuracion.initial_admin_password.get_secret_value() == PASSWORD

    with pytest.raises(ValidationError) as excinfo:
        Settings(_env_file=None, debug=False, secret_key="", initial_admin_password=PASSWORD)
    assert PASSWORD not in str(excinfo.value)


def test_ad_11_la_suite_no_hereda_variables_del_primer_admin() -> None:
    assert settings.initial_admin_email == ""
    assert settings.initial_admin_username == ""
    assert settings.initial_admin_password.get_secret_value() == ""
