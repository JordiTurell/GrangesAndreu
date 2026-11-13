"""Configuración central de la API (variables de entorno + .env)."""

from __future__ import annotations

import json
import secrets
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

# api/
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


def parse_cors_origins(value: object) -> object:
    """Interpreta CORS_ORIGINS como lista JSON o como lista separada por comas."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            return json.loads(text)
        except ValueError:
            raise ValueError("CORS_ORIGINS no es una lista JSON válida") from None
    return [origin.strip() for origin in text.split(",") if origin.strip()]


def sqlite_file_database(url: str) -> str | None:
    """Devuelve la ruta del fichero si la URL es SQLite de fichero; si no, None."""
    try:
        parsed = make_url(url)
    except (ArgumentError, ValueError):  # ValueError: puerto no numérico o vacío, corchete IPv6 sin cerrar
        return None
    if parsed.get_backend_name() != "sqlite":
        return None
    database = parsed.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return None
    return database


def resolve_database_url(url: str, base_dir: Path = BASE_DIR) -> str:
    """Resuelve una ruta SQLite relativa respecto a base_dir; el resto queda igual."""
    database = sqlite_file_database(url)
    if database is None:
        return url
    if Path(database).is_absolute() or database.startswith(("/", "\\")):
        return url
    head, separator, tail = url.partition(":///")
    if not separator:
        return url
    # Sustitución textual: render_as_string codifica "C:" como "C%3A" (SQLAlchemy 2.1).
    _, question, query = tail.partition("?")
    absolute = (base_dir / database).resolve().as_posix()
    return f"{head}{separator}{absolute}{question}{query}"


def ensure_database_directory(database_url: str) -> None:
    """Crea el directorio padre del fichero SQLite (no el fichero)."""
    database = sqlite_file_database(database_url)
    if database is not None:
        Path(database).parent.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "GrangesAndreu API"
    api_prefix: str = "/api"
    debug: bool = False

    host: str = "127.0.0.1"
    port: int = 8000

    database_url: str = ""

    secret_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Primer administrador (contrato auth-completo §4.5): se valida al arrancar, no aquí.
    initial_admin_email: str = ""
    initial_admin_username: str = ""
    initial_admin_password: SecretStr = SecretStr("")

    # NoDecode: pydantic-settings no decodifica el JSON antes de parse_cors_origins.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:4200"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        return parse_cors_origins(value)

    @model_validator(mode="after")
    def _apply_defaults(self) -> "Settings":
        if not self.database_url:
            self.database_url = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"
        self.database_url = resolve_database_url(self.database_url)

        if not self.secret_key:
            if not self.debug:
                raise ValueError(
                    "SECRET_KEY es obligatoria fuera de modo debug. Defínela en el entorno o en api/.env"
                )
            self.secret_key = secrets.token_urlsafe(64)
            warnings.warn(
                "SECRET_KEY no definida: se ha generado una clave efímera (solo desarrollo). "
                "Los tokens dejarán de ser válidos al reiniciar.",
                RuntimeWarning,
                stacklevel=2,
            )
        return self


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    ensure_database_directory(s.database_url)
    return s


settings = get_settings()
