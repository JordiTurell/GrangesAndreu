"""Utilidades de los tests de integración (QA-001): constantes y cliente que vigila el contrato §7.5."""

from __future__ import annotations

import re
from typing import Any

USUARIO = "usuario1"
EMAIL = "usuario1@example.com"
PASSWORD_VALIDA = "Password123"
CUERPO_401 = {"error": {"code": "unauthorized", "message": "Credenciales inválidas"}}

_HASH_BCRYPT = re.compile(r"\$2[abxy]\$")


def comprobar_respuesta(respuesta: Any, etiqueta: str) -> None:
    """§7.5: ninguna respuesta es un 500 ni expone hashed_password ni un hash bcrypt."""
    assert respuesta.status_code != 500, f"{etiqueta} devolvió 500"
    assert "hashed_password" not in respuesta.text, f"{etiqueta} expone hashed_password"
    assert _HASH_BCRYPT.search(respuesta.text) is None, f"{etiqueta} expone un hash bcrypt"


def comprobar_422_password(respuesta: Any, tipo: str = "password_too_long") -> None:
    """422 sobre body.password; con password_too_long el mensaje menciona el límite de 72 bytes."""
    assert respuesta.status_code == 422
    detalle = respuesta.json()["detail"][0]
    assert detalle["loc"] == ["body", "password"]
    assert detalle["type"] == tipo
    if tipo == "password_too_long":
        assert "72 bytes" in detalle["msg"]


class ClienteApi:
    """Envuelve el TestClient: cada respuesta pasa por comprobar_respuesta y queda en `respuestas`."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.respuestas: list[Any] = []

    def enviar(self, metodo: str, ruta: str, **kwargs: Any) -> Any:
        respuesta = self._client.request(metodo, ruta, **kwargs)
        comprobar_respuesta(respuesta, f"{metodo} {ruta}")
        self.respuestas.append(respuesta)
        return respuesta

    def registrar(self, password: str, *, username: str = USUARIO, email: str = EMAIL) -> Any:
        cuerpo = {"username": username, "email": email, "password": password}
        return self.enviar("POST", "/api/auth/register", json=cuerpo)

    def login(self, password: str, *, email: str = EMAIL) -> Any:
        return self.enviar("POST", "/api/auth/login", json={"email": email, "password": password})

    def refresh(self, refresh_token: str) -> Any:
        return self.enviar("POST", "/api/auth/refresh", json={"refresh_token": refresh_token})

    def me(self, token: str | None = None) -> Any:
        cabeceras = {"Authorization": f"Bearer {token}"} if token is not None else {}
        return self.enviar("GET", "/api/auth/me", headers=cabeceras)

    def openapi(self) -> Any:
        return self.enviar("GET", "/openapi.json")
