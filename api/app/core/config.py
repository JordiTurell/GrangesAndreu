"""Configuración central de la API (variables de entorno + .env)."""

from __future__ import annotations

import secrets
import warnings
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# api/
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
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

    cors_origins: list[str] = ["http://localhost:4200"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def _apply_defaults(self) -> "Settings":
        if not self.database_url:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            self.database_url = f"sqlite:///{(DATA_DIR / 'app.db').as_posix()}"

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
    return Settings()


settings = get_settings()
