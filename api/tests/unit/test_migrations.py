"""Unitarios de las migraciones mínimas (ADR-005; contrato auth-completo §2.3 y §7.2, MG-01 a MG-06).

Valen antes y después de API-002: con la entidad ``User`` sin las columnas, ``create_all`` no las crea y la
migración las añade; con la entidad ya declarándolas, la migración no hace nada. En ambos casos el resultado
debe ser el mismo. Solo usan BD temporales (``tmp_path``); nunca ``api/data/app.db``.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core import database, migrations
from app.core.migrations import MIGRATIONS, run_migrations
from app.core.security import hash_password, verify_password

PASSWORD = "secreto-123"

# DDL congelado de `users` tal como lo emitió create_all con la entidad de EP-01 (contrato §2.3).
DDL_USERS_ANTERIOR = (
    """
    CREATE TABLE users (
        id INTEGER NOT NULL, username VARCHAR(80) NOT NULL, email VARCHAR(120) NOT NULL,
        hashed_password VARCHAR(255) NOT NULL, is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL,
        PRIMARY KEY (id)
    )
    """,
    "CREATE UNIQUE INDEX ix_users_username ON users (username)",
    "CREATE UNIQUE INDEX ix_users_email ON users (email)",
)

COLUMNAS_ANTIGUAS = "id, username, email, hashed_password, is_active, created_at"
COLUMNAS_NUEVAS = ("role", "token_version")


@pytest.fixture(scope="module")
def hash_conocido() -> str:
    """Un único hash bcrypt para todo el módulo: bcrypt es lento a propósito."""
    return hash_password(PASSWORD)


def _crear_bd_anterior(tmp_path: Path, hash_conocido: str, nombre: str = "anterior.db") -> Engine:
    """BD con el DDL congelado de `users` y dos usuarios sembrados con SQL crudo."""
    anterior = create_engine(
        f"sqlite:///{(tmp_path / nombre).as_posix()}",
        future=True,
        connect_args={"check_same_thread": False},
    )
    creado = datetime(2026, 11, 1, 10, 30, 0, tzinfo=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
    with anterior.begin() as connection:
        for sentencia in DDL_USERS_ANTERIOR:
            connection.execute(text(sentencia))
        connection.execute(
            text(
                "INSERT INTO users (id, username, email, hashed_password, is_active, created_at) "
                "VALUES (:id, :username, :email, :hashed_password, :is_active, :created_at)"
            ),
            [
                {
                    "id": 1,
                    "username": "ana",
                    "email": "ana@example.com",
                    "hashed_password": hash_conocido,
                    "is_active": 1,
                    "created_at": creado,
                },
                {
                    "id": 2,
                    "username": "beto",
                    "email": "beto@example.com",
                    "hashed_password": hash_conocido,
                    "is_active": 0,
                    "created_at": creado,
                },
            ],
        )
    return anterior


@pytest.fixture
def engine_anterior(tmp_path: Path, hash_conocido: str) -> Iterator[Engine]:
    anterior = _crear_bd_anterior(tmp_path, hash_conocido)
    try:
        yield anterior
    finally:
        anterior.dispose()


def _filas_antiguas(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as connection:
        return [
            tuple(fila)
            for fila in connection.execute(
                text(f"SELECT {COLUMNAS_ANTIGUAS} FROM users ORDER BY id")
            )
        ]


def _roles_y_versiones(engine: Engine) -> list[tuple[Any, ...]]:
    with engine.connect() as connection:
        return [
            tuple(fila)
            for fila in connection.execute(
                text("SELECT id, role, token_version FROM users ORDER BY id")
            )
        ]


def _columnas_nuevas(engine: Engine) -> dict[str, tuple[str, int, str | None]]:
    """`PRAGMA table_info(users)` de role y token_version: (tipo, notnull, dflt_value)."""
    with engine.connect() as connection:
        filas = connection.execute(text("PRAGMA table_info(users)")).mappings().all()
    return {
        fila["name"]: (str(fila["type"]).upper(), fila["notnull"], fila["dflt_value"])
        for fila in filas
        if fila["name"] in COLUMNAS_NUEVAS
    }


def _esquema(engine: Engine) -> list[tuple[str, str, str | None]]:
    with engine.connect() as connection:
        return [
            tuple(fila)
            for fila in connection.execute(
                text("SELECT type, name, sql FROM sqlite_master ORDER BY type, name")
            )
        ]


# --- MG-01 ----------------------------------------------------------------------------------


def test_mg01_migra_bd_anterior_conservando_usuarios(
    engine_anterior: Engine, hash_conocido: str
) -> None:
    antes = _filas_antiguas(engine_anterior)
    assert len(antes) == 2

    run_migrations(engine_anterior)

    assert _filas_antiguas(engine_anterior) == antes
    assert _roles_y_versiones(engine_anterior) == [(1, "user", 0), (2, "user", 0)]
    hashes = [fila[3] for fila in _filas_antiguas(engine_anterior)]
    assert hashes == [hash_conocido, hash_conocido]
    assert all(verify_password(PASSWORD, valor) for valor in hashes)


# --- MG-02 ----------------------------------------------------------------------------------


def test_mg02_es_idempotente(engine_anterior: Engine) -> None:
    run_migrations(engine_anterior)
    esquema = _esquema(engine_anterior)
    filas = _filas_antiguas(engine_anterior)
    extra = _roles_y_versiones(engine_anterior)

    run_migrations(engine_anterior)

    assert _esquema(engine_anterior) == esquema
    assert _filas_antiguas(engine_anterior) == filas
    assert _roles_y_versiones(engine_anterior) == extra


def test_mg02_cada_paso_es_idempotente_por_separado(engine_anterior: Engine) -> None:
    for paso in MIGRATIONS:
        with engine_anterior.begin() as connection:
            paso(connection)
        esquema = _esquema(engine_anterior)
        with engine_anterior.begin() as connection:
            paso(connection)
        assert _esquema(engine_anterior) == esquema


def test_pasos_de_ep02_en_orden() -> None:
    assert [paso.__name__ for paso in MIGRATIONS] == [
        "_add_users_role",
        "_add_users_token_version",
    ]


# --- MG-03 ----------------------------------------------------------------------------------


def test_mg03_bd_nueva_tiene_las_columnas_igual_que_la_migrada(
    engine: Engine, engine_anterior: Engine
) -> None:
    run_migrations(engine)
    run_migrations(engine_anterior)

    nueva = _columnas_nuevas(engine)
    migrada = _columnas_nuevas(engine_anterior)

    assert set(nueva) == set(COLUMNAS_NUEVAS)
    assert nueva == migrada
    assert migrada == {
        "role": ("VARCHAR(10)", 1, "'user'"),
        "token_version": ("INTEGER", 1, "0"),
    }


@pytest.mark.parametrize("motor", ["nueva", "anterior"])
def test_mg03_conserva_los_indices_unicos(
    motor: str, engine: Engine, engine_anterior: Engine
) -> None:
    elegido = engine if motor == "nueva" else engine_anterior
    run_migrations(elegido)

    unicos = {
        tuple(indice["column_names"])
        for indice in inspect(elegido).get_indexes("users")
        if indice["unique"]
    }
    assert ("username",) in unicos
    assert ("email",) in unicos


def test_bd_nueva_no_cambia_con_la_migracion(engine: Engine) -> None:
    """Con la entidad ya declarando las columnas (API-002) la migración no toca nada.

    Antes de API-002 la entidad no las declara y la migración las añade: solo se exige la idempotencia.
    """
    esquema = _esquema(engine)
    entidad_con_columnas = set(COLUMNAS_NUEVAS) <= set(_columnas_nuevas(engine))

    run_migrations(engine)

    if entidad_con_columnas:
        assert _esquema(engine) == esquema
    esquema_migrado = _esquema(engine)
    run_migrations(engine)
    assert _esquema(engine) == esquema_migrado


# --- MG-04 y RL-09 --------------------------------------------------------------------------


def test_mg04_check_de_role_tras_migrar(engine_anterior: Engine) -> None:
    run_migrations(engine_anterior)

    with pytest.raises(IntegrityError):
        with engine_anterior.begin() as connection:
            connection.execute(text("UPDATE users SET role = 'root'"))

    with engine_anterior.begin() as connection:
        connection.execute(text("UPDATE users SET role = 'admin' WHERE id = 1"))
    assert _roles_y_versiones(engine_anterior) == [(1, "admin", 0), (2, "user", 0)]


def test_check_de_role_en_bd_nueva(engine: Engine) -> None:
    run_migrations(engine)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (username, email, hashed_password, is_active, created_at, role) "
                    "VALUES ('x', 'x@example.com', 'h', 1, '2026-11-01 10:00:00', 'root')"
                )
            )


# --- MG-05 ----------------------------------------------------------------------------------


def test_mg05_sin_tabla_users_no_falla_ni_crea_nada(tmp_path: Path) -> None:
    vacio = create_engine(f"sqlite:///{(tmp_path / 'vacio.db').as_posix()}", future=True)
    try:
        run_migrations(vacio)
        run_migrations(vacio)
        assert inspect(vacio).get_table_names() == []
    finally:
        vacio.dispose()


# --- MG-06 ----------------------------------------------------------------------------------


def test_mg06_carrera_con_columna_ya_existente_se_ignora(
    engine_anterior: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Otro proceso añade `role` entre la inspección y el ALTER: el ALTER falla y se ignora."""
    with engine_anterior.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(10) NOT NULL DEFAULT 'user'"))

    real = migrations._column_names
    llamadas = {"n": 0}

    def inspeccion_obsoleta(connection: Any, table: str) -> set[str] | None:
        llamadas["n"] += 1
        columnas = real(connection, table)
        if llamadas["n"] == 1 and columnas is not None:
            return columnas - {"role"}  # la primera lectura aún no ve la columna
        return columnas

    monkeypatch.setattr(migrations, "_column_names", inspeccion_obsoleta)

    with engine_anterior.begin() as connection:
        migrations._add_users_role(connection)  # no debe lanzar

    assert llamadas["n"] == 2
    assert "role" in {columna["name"] for columna in inspect(engine_anterior).get_columns("users")}


def test_mg06_otra_causa_de_operational_error_se_relanza(tmp_path: Path) -> None:
    """`users` es una vista: el ALTER falla con OperationalError y la columna sigue sin existir."""
    con_vista = create_engine(f"sqlite:///{(tmp_path / 'vista.db').as_posix()}", future=True)
    try:
        with con_vista.begin() as connection:
            connection.execute(text("CREATE TABLE otra (id INTEGER NOT NULL, PRIMARY KEY (id))"))
            connection.execute(text("CREATE VIEW users AS SELECT id FROM otra"))

        with pytest.raises(OperationalError):
            run_migrations(con_vista)
    finally:
        con_vista.dispose()


def test_mg06_si_la_columna_sigue_faltando_tras_el_error_se_relanza(
    engine_anterior: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La columna existe pero la relectura sigue sin verla: no se puede afirmar la carrera, se relanza."""
    with engine_anterior.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(10) NOT NULL DEFAULT 'user'"))

    real = migrations._column_names

    def siempre_sin_role(connection: Any, table: str) -> set[str] | None:
        columnas = real(connection, table)
        return None if columnas is None else columnas - {"role"}

    monkeypatch.setattr(migrations, "_column_names", siempre_sin_role)

    with pytest.raises(OperationalError):
        with engine_anterior.begin() as connection:
            migrations._add_users_role(connection)


# --- init_db() ------------------------------------------------------------------------------


def test_init_db_aplica_las_migraciones_tras_create_all(
    engine_anterior: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """init_db() sobre una BD anterior (engine global sustituido por el temporal): crea y migra."""
    antes = _filas_antiguas(engine_anterior)
    monkeypatch.setattr(database, "engine", engine_anterior)

    database.init_db()

    assert _filas_antiguas(engine_anterior) == antes
    assert _roles_y_versiones(engine_anterior) == [(1, "user", 0), (2, "user", 0)]
    assert set(_columnas_nuevas(engine_anterior)) == set(COLUMNAS_NUEVAS)

    esquema = _esquema(engine_anterior)
    database.init_db()
    assert _esquema(engine_anterior) == esquema
    assert _filas_antiguas(engine_anterior) == antes
