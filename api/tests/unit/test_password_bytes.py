"""Unitarios del límite de contraseña en bytes UTF-8 (ADR-004; contrato base-tests-password §7.2 a §7.4)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core import security
from app.core.security import (
    MAX_PASSWORD_BYTES,
    exceeds_password_limit,
    hash_password,
    verify_password,
)
from app.modules.auth.schemas import LoginRequest, UserCreate

MENSAJE_LIMITE = "72 bytes"


def datos_registro(password: str) -> dict[str, Any]:
    return {"username": "usuario", "email": "usuario@example.com", "password": password}


@pytest.fixture(scope="module")
def hash_de_36_enes() -> str:
    """Un único hash bcrypt para todo el módulo: bcrypt es lento a propósito."""
    return hash_password("ñ" * 36)


# --- exceeds_password_limit (§7.4) ----------------------------------------------------------


def test_limite_es_72_bytes() -> None:
    assert MAX_PASSWORD_BYTES == 72


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("", id="vacia"),
        pytest.param("a" * 72, id="72-ascii"),
        pytest.param("ñ" * 36, id="72-bytes-con-36-enes"),
        pytest.param("😀" * 18, id="72-bytes-con-18-emojis"),
    ],
)
def test_exceeds_password_limit_acepta_hasta_72_bytes(password: str) -> None:
    assert exceeds_password_limit(password) is False


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("a" * 73, id="73-ascii"),
        pytest.param("ñ" * 37, id="74-bytes-con-37-enes"),
        pytest.param("😀" * 18 + "a", id="73-bytes-con-19-caracteres"),
    ],
)
def test_exceeds_password_limit_rechaza_mas_de_72_bytes(password: str) -> None:
    assert exceeds_password_limit(password) is True


def test_exceeds_password_limit_no_normaliza_unicode() -> None:
    # "ñ" precompuesta (2 bytes) frente a "n" + tilde combinante (3 bytes): se cuentan los bytes recibidos.
    nfc = "\u00f1" * 36
    nfd = "n\u0303" * 36
    assert exceeds_password_limit(nfc) is False
    assert exceeds_password_limit(nfd) is True


# --- hash_password / verify_password (§7.4 y L-07) ------------------------------------------


@pytest.mark.parametrize(
    "password",
    [pytest.param("a" * 73, id="73-ascii"), pytest.param("ñ" * 40, id="80-bytes-con-40-enes")],
)
def test_hash_password_lanza_value_error_si_supera_el_limite(
    password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_debe_llamarse(*args: object, **kwargs: object) -> bytes:
        raise AssertionError("hash_password no debe llamar a bcrypt si supera el límite")

    monkeypatch.setattr(security.bcrypt, "hashpw", no_debe_llamarse)

    with pytest.raises(ValueError, match="72 bytes"):
        hash_password(password)


def test_hash_password_de_72_bytes_se_verifica(hash_de_36_enes: str) -> None:
    assert hash_de_36_enes.startswith("$2")
    assert verify_password("ñ" * 36, hash_de_36_enes) is True


def test_hash_password_de_72_ascii_exactos() -> None:
    hashed = hash_password("a" * 72)

    assert verify_password("a" * 72, hashed) is True


def test_l_07_verify_password_con_mas_de_72_bytes_es_false(hash_de_36_enes: str) -> None:
    assert verify_password("ñ" * 40, hash_de_36_enes) is False


def test_l_07_verify_password_no_acepta_un_prefijo_de_72_bytes(hash_de_36_enes: str) -> None:
    assert verify_password("ñ" * 36 + "x", hash_de_36_enes) is False


def test_l_07_verify_password_con_hash_malformado_es_false() -> None:
    assert verify_password("x", "no-es-un-hash") is False


def test_verify_password_no_llama_a_bcrypt_si_supera_el_limite(
    hash_de_36_enes: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def no_debe_llamarse(*args: object, **kwargs: object) -> bool:
        raise AssertionError("verify_password no debe llamar a bcrypt si supera el límite")

    monkeypatch.setattr(security.bcrypt, "checkpw", no_debe_llamarse)

    assert verify_password("ñ" * 40, hash_de_36_enes) is False


def test_verify_password_con_texto_no_codificable_es_false(hash_de_36_enes: str) -> None:
    # Un sustituto aislado no se puede codificar en UTF-8 (UnicodeEncodeError es ValueError).
    assert verify_password("\ud800", hash_de_36_enes) is False


# --- UserCreate (R-01 a R-11) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("a" * 72, id="R-02"),
        pytest.param("ñ" * 36, id="R-04"),
        pytest.param("a" * 70 + "ñ", id="R-05"),
        pytest.param("😀" * 18, id="R-08"),
        pytest.param("ñ" * 8, id="R-10"),
    ],
)
def test_user_create_acepta_contrasenas_dentro_del_limite(password: str) -> None:
    assert UserCreate(**datos_registro(password)).password == password


@pytest.mark.parametrize(
    "password",
    [
        pytest.param("ñ" * 40, id="R-01"),
        pytest.param("a" * 73, id="R-03"),
        pytest.param("a" * 71 + "ñ", id="R-06"),
        pytest.param("ñ" * 37, id="R-07"),
        pytest.param("😀" * 18 + "a", id="R-09"),
    ],
)
def test_user_create_rechaza_mas_de_72_bytes(password: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(**datos_registro(password))

    errores = excinfo.value.errors()
    assert len(errores) == 1
    assert errores[0]["type"] == "password_too_long"
    assert errores[0]["loc"] == ("password",)
    assert MENSAJE_LIMITE in errores[0]["msg"]
    assert errores[0]["ctx"] == {"max_bytes": 72}


def test_user_create_mensaje_exacto_del_contrato() -> None:
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(**datos_registro("ñ" * 40))

    assert excinfo.value.errors()[0]["msg"] == "La contraseña no puede superar los 72 bytes en UTF-8"


def test_mas_de_72_caracteres_es_password_too_long_y_no_string_too_long() -> None:
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(**datos_registro("a" * 10000))

    assert [error["type"] for error in excinfo.value.errors()] == ["password_too_long"]


def test_r_11_menos_de_8_caracteres_es_string_too_short() -> None:
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(**datos_registro("a" * 7))

    errores = excinfo.value.errors()
    assert len(errores) == 1
    assert errores[0]["type"] == "string_too_short"
    assert errores[0]["loc"] == ("password",)


def test_user_create_el_minimo_cuenta_caracteres_y_no_bytes() -> None:
    # 4 "ñ" son 8 bytes pero solo 4 caracteres: no alcanzan el mínimo.
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(**datos_registro("ñ" * 4))

    assert excinfo.value.errors()[0]["type"] == "string_too_short"


# --- LoginRequest (L-08) --------------------------------------------------------------------


def test_l_08_login_request_no_valida_bytes() -> None:
    assert LoginRequest(email="usuario@example.com", password="ñ" * 40).password == "ñ" * 40


def test_l_08_login_request_mantiene_la_cota_de_72_caracteres() -> None:
    with pytest.raises(ValidationError) as excinfo:
        LoginRequest(email="usuario@example.com", password="a" * 73)

    errores = excinfo.value.errors()
    assert [error["type"] for error in errores] == ["string_too_long"]
    assert errores[0]["loc"] == ("password",)


def test_login_request_rechaza_password_vacia() -> None:
    with pytest.raises(ValidationError) as excinfo:
        LoginRequest(email="usuario@example.com", password="")

    assert excinfo.value.errors()[0]["type"] == "string_too_short"


# --- Esquema JSON (§5) ----------------------------------------------------------------------


def test_json_schema_de_user_create_password() -> None:
    password = UserCreate.model_json_schema()["properties"]["password"]

    assert password["type"] == "string"
    assert password["minLength"] == 8
    assert "maxLength" not in password
    assert MENSAJE_LIMITE in password["description"]


def test_json_schema_de_login_request_password_no_cambia() -> None:
    password = LoginRequest.model_json_schema()["properties"]["password"]

    assert password["minLength"] == 1
    assert password["maxLength"] == 72
