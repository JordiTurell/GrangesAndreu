"""Migraciones mínimas del esquema SQLite (ADR-005): pasos aditivos e idempotentes.

Cada paso inspecciona el esquema y no hace nada si su cambio ya está aplicado o si la tabla no existe,
de modo que una BD nueva (creada por ``create_all``) y una BD anterior pasan por el mismo código.
Solo se admiten cambios aditivos; borrar, renombrar o cambiar tipos requiere pasar a Alembic.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError

Migration = Callable[[Connection], None]

_USERS_ROLE_DDL = (
    "ALTER TABLE users ADD COLUMN role VARCHAR(10) NOT NULL DEFAULT 'user' "
    "CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))"
)
_USERS_TOKEN_VERSION_DDL = "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0"


def _column_names(connection: Connection, table: str) -> set[str] | None:
    """Columnas de la tabla, o ``None`` si no existe. Usa un inspector nuevo (sin caché)."""
    inspector = inspect(connection)
    if not inspector.has_table(table):
        return None
    return {column["name"] for column in inspector.get_columns(table)}


def _add_column(connection: Connection, table: str, column: str, ddl: str) -> None:
    """Añade ``column`` a ``table`` con ``ddl`` si falta; tolera la carrera entre procesos."""
    columns = _column_names(connection, table)
    if columns is None or column in columns:
        return
    try:
        connection.execute(text(ddl))
    except OperationalError:
        # Otro proceso pudo añadirla entre la inspección y el ALTER: se relee el esquema.
        columns = _column_names(connection, table)
        if columns is not None and column in columns:
            return
        raise


def _add_users_role(connection: Connection) -> None:
    _add_column(connection, "users", "role", _USERS_ROLE_DDL)


def _add_users_token_version(connection: Connection) -> None:
    _add_column(connection, "users", "token_version", _USERS_TOKEN_VERSION_DDL)


MIGRATIONS: tuple[Migration, ...] = (
    _add_users_role,
    _add_users_token_version,
)


def run_migrations(engine: Engine) -> None:
    """Ejecuta en una transacción los pasos de ``MIGRATIONS``; un fallo aborta y se propaga."""
    with engine.begin() as connection:
        for migration in MIGRATIONS:
            migration(connection)
