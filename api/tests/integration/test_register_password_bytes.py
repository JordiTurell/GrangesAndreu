"""Integración de POST /api/auth/register con contraseñas multibyte (contrato base-tests-password §7.2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from app.core.security import verify_password
from app.modules.auth.entities import User
from tests.integration.helpers import (
    EMAIL,
    PASSWORD_VALIDA,
    USUARIO,
    ClienteApi,
    comprobar_422_password,
)

CAMPOS_USER_READ = {"id", "username", "email", "is_active", "created_at"}

# 72 bytes exactos o menos: se aceptan (R-02, R-04, R-05, R-08 y R-10: el mínimo cuenta caracteres).
ACEPTADAS = [
    pytest.param("a" * 72, id="R-02-72-ascii"),
    pytest.param("ñ" * 36, id="R-04-72-bytes-con-36-enes"),
    pytest.param("a" * 70 + "ñ", id="R-05-72-bytes-con-71-caracteres"),
    pytest.param("😀" * 18, id="R-08-72-bytes-con-18-emojis"),
    pytest.param("ñ" * 8, id="R-10-16-bytes-con-8-enes"),
]

# Más de 72 bytes, con independencia del número de caracteres.
RECHAZADAS = [
    pytest.param("ñ" * 40, id="R-01-80-bytes-con-40-enes"),
    pytest.param("a" * 73, id="R-03-73-ascii"),
    pytest.param("a" * 71 + "ñ", id="R-06-73-bytes-con-72-caracteres"),
    pytest.param("ñ" * 37, id="R-07-74-bytes-con-37-enes"),
    pytest.param("😀" * 18 + "a", id="R-09-73-bytes-con-19-caracteres"),
    pytest.param("ñ" * 10000, id="R-12-20000-bytes-con-10000-enes"),
]


@pytest.mark.parametrize("password", ACEPTADAS)
def test_register_acepta_hasta_72_bytes(
    api: ClienteApi, usuario_en_bd: Callable[[str], User | None], password: str
) -> None:
    respuesta = api.registrar(password)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert set(cuerpo) == CAMPOS_USER_READ
    assert cuerpo["username"] == USUARIO
    assert cuerpo["email"] == EMAIL
    usuario = usuario_en_bd(EMAIL)
    assert usuario is not None
    # El hash guardado corresponde a la contraseña completa (sin truncar) y no es la contraseña.
    assert usuario.hashed_password.startswith("$2")
    assert usuario.hashed_password != password
    assert verify_password(password, usuario.hashed_password)


@pytest.mark.parametrize("password", RECHAZADAS)
def test_register_rechaza_mas_de_72_bytes_con_422(
    api: ClienteApi, contar_usuarios: Callable[[], int], password: str
) -> None:
    respuesta = api.registrar(password)

    comprobar_422_password(respuesta)
    assert contar_usuarios() == 0


def test_r_11_menos_de_8_caracteres_sigue_dando_string_too_short(api: ClienteApi) -> None:
    comprobar_422_password(api.registrar("a" * 7), tipo="string_too_short")


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("ñ" * 40, id="R-01"),
        pytest.param("a" * 73, id="R-03"),
        pytest.param("a" * 71 + "ñ", id="R-06"),
    ],
)
def test_r_13_la_contrasena_rechazada_no_deja_usuario(
    api: ClienteApi, contar_usuarios: Callable[[], int], password: str
) -> None:
    comprobar_422_password(api.registrar(password))
    assert contar_usuarios() == 0

    # Mismo email y usuario: si el 422 hubiera dejado una fila, esto sería un 409.
    respuesta = api.registrar(PASSWORD_VALIDA)

    assert respuesta.status_code == 201
    assert contar_usuarios() == 1


def test_r_14_password123_se_registra_y_el_duplicado_da_409(api: ClienteApi) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201

    duplicado = api.registrar(PASSWORD_VALIDA, username="otro-usuario")

    assert duplicado.status_code == 409
    error = duplicado.json()["error"]
    assert error["code"] == "conflict"
    assert error["message"]


@pytest.mark.parametrize(
    ("username", "email"),
    [
        pytest.param("otro-usuario", EMAIL.upper(), id="email-en-mayusculas"),
        pytest.param(USUARIO.upper(), "otro@example.com", id="usuario-en-mayusculas"),
    ],
)
def test_r_14_duplicados_sin_distinguir_mayusculas(
    api: ClienteApi, username: str, email: str
) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201

    duplicado = api.registrar(PASSWORD_VALIDA, username=username, email=email)

    assert duplicado.status_code == 409
    assert duplicado.json()["error"]["code"] == "conflict"


def test_contrasena_larga_con_email_existente_no_revela_la_cuenta(api: ClienteApi) -> None:
    assert api.registrar(PASSWORD_VALIDA).status_code == 201

    de_cuenta_existente = api.registrar("ñ" * 40)
    de_cuenta_nueva = api.registrar("ñ" * 40, username="nuevo", email="nuevo@example.com")

    # La validación del esquema va antes de consultar la BD: ambas respuestas son indistinguibles.
    comprobar_422_password(de_cuenta_existente)
    comprobar_422_password(de_cuenta_nueva)
    campos = ("type", "loc", "msg")
    assert [de_cuenta_existente.json()["detail"][0][c] for c in campos] == [
        de_cuenta_nueva.json()["detail"][0][c] for c in campos
    ]


def test_el_limite_cuenta_los_bytes_recibidos_sin_normalizar_unicode(api: ClienteApi) -> None:
    # "n" + tilde combinante ocupa 3 bytes: 24 repeticiones son 72 bytes (48 caracteres).
    nfd_72_bytes = "n\u0303" * 24

    assert api.registrar(nfd_72_bytes).status_code == 201
    comprobar_422_password(
        api.registrar(nfd_72_bytes + "a", username="otro-usuario", email="otro@example.com")
    )


@pytest.mark.parametrize(
    ("cuerpo", "tipo", "loc"),
    [
        pytest.param(
            {"username": "ab", "email": EMAIL, "password": PASSWORD_VALIDA},
            "string_too_short",
            ["body", "username"],
            id="usuario-corto",
        ),
        pytest.param(
            {"username": USUARIO, "email": "no-es-un-email", "password": PASSWORD_VALIDA},
            "value_error",
            ["body", "email"],
            id="email-invalido",
        ),
        pytest.param(
            {"username": USUARIO, "email": EMAIL},
            "missing",
            ["body", "password"],
            id="password-ausente",
        ),
        pytest.param(
            {"username": USUARIO, "email": EMAIL, "password": 12345678},
            "string_type",
            ["body", "password"],
            id="password-numerica",
        ),
    ],
)
def test_el_resto_de_validaciones_del_422_no_cambia(
    api: ClienteApi, cuerpo: dict[str, Any], tipo: str, loc: list[str]
) -> None:
    respuesta = api.enviar("POST", "/api/auth/register", json=cuerpo)

    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"][0]
    assert detalle["type"] == tipo
    assert detalle["loc"] == loc
