"""Seguridad y contrato OpenAPI del límite de contraseña (contrato base-tests-password §5 y §7.5)."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.helpers import (
    PASSWORD_VALIDA,
    ClienteApi,
    comprobar_respuesta,
)


class RespuestaFalsa:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text


@pytest.fixture
def openapi(api: ClienteApi) -> dict[str, Any]:
    respuesta = api.openapi()
    assert respuesta.status_code == 200
    return respuesta.json()


# --- §7.5: el vigilante detecta lo que dice detectar ----------------------------------------


@pytest.mark.parametrize(
    ("respuesta", "fragmento"),
    [
        pytest.param(RespuestaFalsa(500, "Internal Server Error"), "500", id="500"),
        pytest.param(RespuestaFalsa(200, '{"hashed_password": "x"}'), "hashed_password", id="campo"),
        pytest.param(RespuestaFalsa(200, '{"x": "$2b$12$abcdefgh"}'), "hash bcrypt", id="hash-2b"),
        pytest.param(RespuestaFalsa(200, '{"x": "$2a$10$abcdefgh"}'), "hash bcrypt", id="hash-2a"),
    ],
)
def test_el_vigilante_rechaza_500_y_fugas_de_hash(respuesta: RespuestaFalsa, fragmento: str) -> None:
    with pytest.raises(AssertionError, match=fragmento):
        comprobar_respuesta(respuesta, "prueba")


def test_el_vigilante_acepta_una_respuesta_limpia() -> None:
    comprobar_respuesta(RespuestaFalsa(422, '{"detail": []}'), "prueba")


# --- §7.5: ninguna respuesta expone el hash ni es un 500 --------------------------------------


def test_ninguna_respuesta_de_auth_expone_hash_ni_da_500(api: ClienteApi) -> None:
    # Cada llamada de `api` ya pasa por comprobar_respuesta; aquí se recorre cada tipo de respuesta.
    api.registrar(PASSWORD_VALIDA)  # 201
    api.registrar(PASSWORD_VALIDA)  # 409
    api.registrar("ñ" * 40, username="otro", email="otro@example.com")  # 422 password_too_long
    api.registrar("a" * 7, username="otro", email="otro@example.com")  # 422 string_too_short
    tokens = api.login(PASSWORD_VALIDA).json()  # 200
    api.login("ñ" * 40)  # 401
    api.login("a" * 73)  # 422
    api.me(tokens["access_token"])  # 200
    api.me(tokens["refresh_token"])  # 401
    api.me()  # 401
    api.refresh(tokens["refresh_token"])  # 200
    api.refresh(tokens["access_token"])  # 401

    estados = [r.status_code for r in api.respuestas]

    assert estados == [201, 409, 422, 422, 200, 401, 422, 200, 401, 401, 200, 401]


def test_la_contrasena_no_aparece_en_logs_ni_en_la_salida(
    api: ClienteApi, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    caplog.set_level("DEBUG")
    larga = "ñ" * 36 + "-marca-larga"
    valida = "ñ" * 36

    assert api.registrar(valida).status_code == 201
    assert api.registrar(larga, username="otro", email="otro@example.com").status_code == 422
    assert api.login(valida).status_code == 200
    assert api.login(larga).status_code == 401
    salida = capfd.readouterr()

    for texto in (caplog.text, salida.out, salida.err):
        assert valida not in texto
        assert "marca-larga" not in texto


# --- §5: /openapi.json ------------------------------------------------------------------------


def test_openapi_user_create_password_sin_max_length_y_con_el_limite_en_bytes(
    openapi: dict[str, Any],
) -> None:
    esquema = openapi["components"]["schemas"]["UserCreate"]

    assert set(esquema["required"]) == {"username", "email", "password"}
    password = esquema["properties"]["password"]
    assert password["type"] == "string"
    assert password["minLength"] == 8
    assert "maxLength" not in password
    assert "72 bytes" in password["description"]
    assert esquema["properties"]["username"]["minLength"] == 3
    assert esquema["properties"]["username"]["maxLength"] == 80
    assert esquema["properties"]["email"]["format"] == "email"


def test_openapi_login_request_password_sigue_en_1_a_72_caracteres(
    openapi: dict[str, Any],
) -> None:
    esquema = openapi["components"]["schemas"]["LoginRequest"]

    assert set(esquema["required"]) == {"email", "password"}
    password = esquema["properties"]["password"]
    assert password["type"] == "string"
    assert password["minLength"] == 1
    assert password["maxLength"] == 72
    assert esquema["properties"]["email"]["format"] == "email"


@pytest.mark.parametrize(
    ("ruta", "peticion", "exito", "respuesta_exito"),
    [
        pytest.param("/api/auth/register", "UserCreate", "201", "UserRead", id="register"),
        pytest.param("/api/auth/login", "LoginRequest", "200", "TokenResponse", id="login"),
    ],
)
def test_openapi_rutas_de_register_y_login(
    openapi: dict[str, Any], ruta: str, peticion: str, exito: str, respuesta_exito: str
) -> None:
    operacion = openapi["paths"][ruta]["post"]

    cuerpo = operacion["requestBody"]
    assert cuerpo["required"] is True
    assert cuerpo["content"]["application/json"]["schema"]["$ref"] == (
        f"#/components/schemas/{peticion}"
    )
    respuestas = operacion["responses"]
    assert respuestas[exito]["content"]["application/json"]["schema"]["$ref"] == (
        f"#/components/schemas/{respuesta_exito}"
    )
    assert respuestas["422"]["content"]["application/json"]["schema"]["$ref"] == (
        "#/components/schemas/HTTPValidationError"
    )


def test_openapi_user_read_no_expone_hashed_password(openapi: dict[str, Any]) -> None:
    propiedades = openapi["components"]["schemas"]["UserRead"]["properties"]

    assert set(propiedades) == {"id", "username", "email", "is_active", "created_at"}
