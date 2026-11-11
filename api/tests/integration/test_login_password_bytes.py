"""Integración de POST /api/auth/login con contraseñas multibyte (contrato base-tests-password §7.3)."""

from __future__ import annotations

from typing import Any

import bcrypt
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.entities import User
from tests.integration.helpers import (
    CUERPO_401,
    EMAIL,
    PASSWORD_VALIDA,
    ClienteApi,
    comprobar_422_password,
)

BYTES_BCRYPT = 72


@pytest.fixture
def bcrypt_que_trunca(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simula bcrypt 4.x (riesgo R-04): corta a 72 bytes en silencio en lugar de lanzar ValueError."""
    hashpw, checkpw = bcrypt.hashpw, bcrypt.checkpw
    monkeypatch.setattr(bcrypt, "hashpw", lambda pw, salt: hashpw(pw[:BYTES_BCRYPT], salt))
    monkeypatch.setattr(bcrypt, "checkpw", lambda pw, h: checkpw(pw[:BYTES_BCRYPT], h))


def comprobar_401(respuesta: Any) -> None:
    assert respuesta.status_code == 401
    assert respuesta.json() == CUERPO_401


def test_l_01_registra_con_72_bytes_y_entra_con_la_misma(api: ClienteApi) -> None:
    password = "ñ" * 36
    assert api.registrar(password).status_code == 201

    respuesta = api.login(password)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["access_token"]
    assert cuerpo["refresh_token"]
    assert cuerpo["token_type"] == "bearer"
    me = api.me(cuerpo["access_token"])
    assert me.status_code == 200
    assert me.json()["email"] == EMAIL


def test_l_02_cuenta_existente_con_contrasena_de_80_bytes_da_401(api: ClienteApi) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201

    comprobar_401(api.login("ñ" * 40))


def test_l_03_email_inexistente_con_contrasena_de_80_bytes_da_401(api: ClienteApi) -> None:
    comprobar_401(api.login("ñ" * 40, email="nadie@example.com"))


def test_l_02_l_03_los_401_son_indistinguibles(api: ClienteApi) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201
    respuestas = [
        api.login("ñ" * 40),
        api.login("ñ" * 40, email="nadie@example.com"),
        api.login("OtraClave123"),
        api.login("OtraClave123", email="nadie@example.com"),
    ]

    firmas = {
        (
            r.status_code,
            r.text,
            r.headers.get("www-authenticate"),
            r.headers.get("content-type"),
        )
        for r in respuestas
    }

    assert len(firmas) == 1
    assert respuestas[0].headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("modo", ["bcrypt-real", "bcrypt-que-trunca"])
@pytest.mark.parametrize(
    "intento",
    [
        pytest.param("ñ" * 36 + "x", id="L-04-73-bytes-con-37-caracteres"),
        pytest.param("ñ" * 40, id="prefijo-de-72-bytes-en-80"),
    ],
)
def test_l_04_no_se_acepta_un_prefijo_de_72_bytes(
    api: ClienteApi, request: pytest.FixtureRequest, modo: str, intento: str
) -> None:
    if modo == "bcrypt-que-trunca":
        request.getfixturevalue("bcrypt_que_trunca")
    assert api.registrar("ñ" * 36).status_code == 201
    assert api.login("ñ" * 36).status_code == 200  # control: la contraseña completa sí entra

    comprobar_401(api.login(intento))


def test_l_05_emojis_por_encima_de_72_bytes_dan_401_sin_romper_los_validos(
    api: ClienteApi,
) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201
    comprobar_401(api.login("😀" * 20))  # 80 bytes, 20 caracteres

    assert api.registrar("😀" * 18, username="emojis", email="emojis@example.com").status_code == 201
    assert api.login("😀" * 18, email="emojis@example.com").status_code == 200
    comprobar_401(api.login("😀" * 18 + "a", email="emojis@example.com"))


def test_l_06_mas_de_73_caracteres_dan_422_string_too_long(api: ClienteApi) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201

    comprobar_422_password(api.login("a" * 73), tipo="string_too_long")


@pytest.mark.parametrize(
    "hash_corrupto",
    [
        pytest.param("no-es-un-hash", id="texto-cualquiera"),
        pytest.param("$2b$12$corto", id="prefijo-bcrypt-truncado"),
        pytest.param("", id="vacio"),
    ],
)
def test_login_con_hash_corrupto_en_la_bd_da_401_sin_500(
    api: ClienteApi, db_session: Session, hash_corrupto: str
) -> None:
    # L-07 a nivel HTTP: bcrypt lanza ValueError ante un hash inválido y verify_password lo captura.
    assert api.registrar(PASSWORD_VALIDA).status_code == 201
    usuario = db_session.scalars(select(User).where(User.email == EMAIL)).one()
    usuario.hashed_password = hash_corrupto
    db_session.commit()

    comprobar_401(api.login(PASSWORD_VALIDA))


@pytest.mark.parametrize(
    ("password", "esperado"),
    [
        pytest.param("ñ" * 72, 401, id="72-caracteres-144-bytes"),
        pytest.param("ñ" * 73, 422, id="73-caracteres"),
        pytest.param("", 422, id="vacia"),
    ],
)
def test_login_la_cota_de_caracteres_sigue_vigente(
    api: ClienteApi, password: str, esperado: int
) -> None:
    respuesta = api.login(password)

    assert respuesta.status_code == esperado
    if esperado == 422:
        tipo = "string_too_short" if password == "" else "string_too_long"
        comprobar_422_password(respuesta, tipo=tipo)
    else:
        assert respuesta.json() == CUERPO_401
