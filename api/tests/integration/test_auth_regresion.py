"""Regresión del módulo auth tras ADR-004: register, login, refresh y /me sin cambios de contrato."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.modules.auth.entities import User
from tests.integration.helpers import EMAIL, PASSWORD_VALIDA, USUARIO, ClienteApi


def comprobar_error(respuesta: Any, codigo: str, mensaje: str) -> None:
    assert respuesta.status_code == 401
    assert respuesta.json() == {"error": {"code": codigo, "message": mensaje}}


def test_flujo_register_login_me_refresh(
    api: ClienteApi, usuario_en_bd: Callable[[str], User | None]
) -> None:
    registro = api.registrar(PASSWORD_VALIDA)
    assert registro.status_code == 201
    usuario = registro.json()
    assert usuario["username"] == USUARIO
    assert usuario["email"] == EMAIL
    assert usuario["is_active"] is True
    assert isinstance(usuario["id"], int)
    guardado = usuario_en_bd(EMAIL)
    assert guardado is not None
    assert guardado.hashed_password.startswith("$2")

    login = api.login(PASSWORD_VALIDA)
    assert login.status_code == 200
    tokens = login.json()
    assert set(tokens) == {"access_token", "refresh_token", "token_type", "expires_in"}
    assert tokens["expires_in"] == settings.access_token_expire_minutes * 60

    me = api.me(tokens["access_token"])
    assert me.status_code == 200
    assert me.json() == usuario

    renovados = api.refresh(tokens["refresh_token"])
    assert renovados.status_code == 200
    assert api.me(renovados.json()["access_token"]).json() == usuario


def test_contrasena_correcta_con_otra_capitalizacion_da_401(api: ClienteApi) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201

    respuesta = api.login(PASSWORD_VALIDA.lower())

    comprobar_error(respuesta, "unauthorized", "Credenciales inválidas")


def test_los_tokens_de_tipo_incorrecto_se_rechazan(api: ClienteApi) -> None:
    api.registrar(PASSWORD_VALIDA)
    tokens = api.login(PASSWORD_VALIDA).json()

    comprobar_error(api.refresh(tokens["access_token"]), "unauthorized", "Tipo de token incorrecto")
    comprobar_error(api.me(tokens["refresh_token"]), "unauthorized", "Tipo de token incorrecto")


def test_me_sin_token_o_con_token_invalido_da_401(api: ClienteApi) -> None:
    comprobar_error(api.me(), "unauthorized", "Credenciales no proporcionadas")
    comprobar_error(api.me("no-es-un-jwt"), "unauthorized", "Token inválido")


def test_un_usuario_desactivado_no_entra_ni_renueva(api: ClienteApi, db_session: Session) -> None:
    api.registrar(PASSWORD_VALIDA)
    tokens = api.login(PASSWORD_VALIDA).json()
    usuario = db_session.scalars(select(User).where(User.email == EMAIL)).one()
    usuario.is_active = False
    db_session.commit()

    comprobar_error(api.login(PASSWORD_VALIDA), "unauthorized", "La cuenta está desactivada")
    comprobar_error(
        api.me(tokens["access_token"]), "unauthorized", "Usuario no válido o inactivo"
    )
    comprobar_error(
        api.refresh(tokens["refresh_token"]), "unauthorized", "Usuario no válido o inactivo"
    )


@pytest.mark.parametrize("repeticion", [1, 2], ids=["primer-test", "segundo-test"])
def test_cada_test_empieza_con_la_bd_limpia(api: ClienteApi, repeticion: int) -> None:
    # Si la BD no se aislara por test, la segunda ejecución daría 409 con el mismo email.
    assert api.registrar(PASSWORD_VALIDA).status_code == 201
