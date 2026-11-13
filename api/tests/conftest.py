"""Fixtures de la API: entorno temporal y BD SQLite por test (contrato base-tests-password §4.2)."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

# F-1: settings y engine se crean al importar app.*; el entorno debe fijarse antes.
SESSION_DIR = Path(tempfile.mkdtemp(prefix="granjas-tests-"))
SESSION_DATABASE_URL = f"sqlite:///{(SESSION_DIR / 'session.db').as_posix()}"
TEST_SECRET_KEY = "clave-solo-para-tests-0123456789abcdef"

# Asignación directa (no setdefault): los valores del shell no deben colarse.
os.environ["DEBUG"] = "true"
os.environ["SECRET_KEY"] = TEST_SECRET_KEY
os.environ["DATABASE_URL"] = SESSION_DATABASE_URL
# §4.1: ni el shell ni api/.env deben colar un primer administrador en la suite.
os.environ["INITIAL_ADMIN_EMAIL"] = ""
os.environ["INITIAL_ADMIN_USERNAME"] = ""
os.environ["INITIAL_ADMIN_PASSWORD"] = ""


@pytest.fixture(scope="session", autouse=True)
def _guarda_entorno() -> None:
    """F-2: aborta la sesión si el engine global no apunta a la BD temporal."""
    from app.core.config import settings

    if settings.database_url != SESSION_DATABASE_URL:
        pytest.exit(
            "Los tests no pueden ejecutarse: settings.database_url no es la BD temporal de sesión "
            "(¿se importó app.* antes de cargar tests/conftest.py?). Se aborta para no tocar api/data/.",
            returncode=2,
        )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """F-7: libera el engine global (WAL bloquea el borrado en Windows) y borra el directorio temporal."""
    database = sys.modules.get("app.core.database")
    if database is not None:
        database.engine.dispose()
    shutil.rmtree(SESSION_DIR, ignore_errors=True)


def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    """F-3: engine SQLite propio de cada test, con las tablas creadas."""
    # Importar app.core.database registra también el listener de pragmas (foreign_keys, WAL).
    from app.core.database import Base
    from app.modules.auth import entities  # noqa: F401  (registra modelos)

    test_engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=test_engine)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """F-4: sesión sobre la BD del test, para comprobar su estado desde el test."""
    session = _session_factory(engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    """F-5 y F-6: TestClient de la app con get_db apuntando a la BD del test."""
    import main  # lanza bootstrap.ensure_dependencies(): requirements.txt debe estar instalado

    # Import perezoso: los tests que no usan `client` no necesitan el cliente HTTP.
    from fastapi.testclient import TestClient

    from app.core.database import get_db

    factory = _session_factory(engine)

    def override_get_db() -> Iterator[Session]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    try:
        # raise_server_exceptions=False: un 500 se ve como status_code == 500 (EP-01-D2).
        with TestClient(main.app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.pop(get_db, None)
