"""Fixtures de integración (QA-001) sobre `client`, `engine` y `db_session` de tests/conftest.py."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.orm import Session

from tests.integration.helpers import ClienteApi

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from app.modules.auth.entities import User


@pytest.fixture
def api(client: TestClient) -> ClienteApi:
    return ClienteApi(client)


@pytest.fixture
def contar_usuarios(db_session: Session) -> Callable[[], int]:
    def contar() -> int:
        from sqlalchemy import func, select

        from app.modules.auth.entities import User

        db_session.rollback()  # descarta cualquier lectura previa: ve lo que escribió la API
        return db_session.scalar(select(func.count()).select_from(User))

    return contar


@pytest.fixture
def usuario_en_bd(db_session: Session) -> Callable[[str], User | None]:
    def buscar(email: str) -> User | None:
        from sqlalchemy import select

        from app.modules.auth.entities import User

        db_session.rollback()
        return db_session.scalar(select(User).where(User.email == email.lower()))

    return buscar
