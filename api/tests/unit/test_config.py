"""Unitarios de configuración (contrato base-tests-password §7.6.1): piezas puras de app.core.config."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core import config
from app.core.config import (
    Settings,
    ensure_database_directory,
    parse_cors_origins,
    resolve_database_url,
    sqlite_file_database,
)

SECRET_KEY_VALIDA = "clave-de-prueba-0123456789abcdef0123456789abcdef"

# DB-09 incluye las tres cadenas de BUG-001 (make_url lanza ValueError con ellas).
URLS_NO_SQLITE_DE_FICHERO = [
    pytest.param("sqlite://", id="DB-06-sqlite-vacia"),
    pytest.param("sqlite:///:memory:", id="DB-06-memoria"),
    pytest.param("sqlite:///file:x?mode=memory&uri=true", id="DB-06-uri-file"),
    pytest.param("postgresql+psycopg://u:p@h/db", id="DB-07-postgresql"),
    pytest.param("no-es-una-url", id="DB-09-no-parseable"),
    pytest.param("", id="DB-09-vacia"),
    pytest.param("://", id="DB-09-solo-separador"),
    pytest.param("postgresql://u:p@h:abc/db", id="DB-09-puerto-no-numerico"),
    pytest.param("postgresql://u:p@h:/db", id="DB-09-puerto-vacio"),
    pytest.param("mysql://[::1/db", id="DB-09-ipv6-sin-cerrar"),
]


def url_sqlite(ruta: Path) -> str:
    return f"sqlite:///{ruta.resolve().as_posix()}"


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parte de DEBUG=true y SECRET_KEY válida; el resto de variables de Settings, ausentes."""
    for nombre in ("DATABASE_URL", "CORS_ORIGINS", "DEBUG", "SECRET_KEY"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SECRET_KEY", SECRET_KEY_VALIDA)


def settings_con_cors(monkeypatch: pytest.MonkeyPatch, valor: str) -> Settings:
    monkeypatch.setenv("CORS_ORIGINS", valor)
    return Settings(_env_file=None)


# --- CORS_ORIGINS ---------------------------------------------------------------------------


def test_co_01_ausente_usa_el_defecto() -> None:
    assert Settings(_env_file=None).cors_origins == ["http://localhost:4200"]


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        pytest.param("http://localhost:4200", ["http://localhost:4200"], id="CO-02-una-url"),
        pytest.param(
            "http://a:4200,http://b:4200", ["http://a:4200", "http://b:4200"], id="CO-03-comas"
        ),
        pytest.param(
            " http://a:4200 , http://b:4200 ,, ",
            ["http://a:4200", "http://b:4200"],
            id="CO-04-espacios-y-vacios",
        ),
        pytest.param('["http://localhost:4200"]', ["http://localhost:4200"], id="CO-05-json"),
        pytest.param(
            '[ "http://a:4200" , "http://b:4200" ]',
            ["http://a:4200", "http://b:4200"],
            id="CO-06-json-con-espacios",
        ),
        pytest.param("", [], id="CO-07-vacia"),
        pytest.param("   ", [], id="CO-07-espacios"),
        pytest.param(",", [], id="CO-07-coma"),
        pytest.param("[]", [], id="CO-07-json-vacio"),
    ],
)
def test_cors_origins_formatos(
    monkeypatch: pytest.MonkeyPatch, valor: str, esperado: list[str]
) -> None:
    assert settings_con_cors(monkeypatch, valor).cors_origins == esperado


def test_co_08_json_roto_aborta_sin_incluir_el_valor(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError) as excinfo:
        settings_con_cors(monkeypatch, '["http://a:4200"')

    error = excinfo.value.errors()[0]
    assert error["loc"] == ("cors_origins",)
    assert error["msg"].endswith("CORS_ORIGINS no es una lista JSON válida")


def test_co_09_elementos_no_str_se_rechazan(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError) as excinfo:
        settings_con_cors(monkeypatch, "[1, 2]")

    assert excinfo.value.errors()[0]["loc"][0] == "cors_origins"


def test_co_10_una_lista_ya_construida_pasa_sin_cambios() -> None:
    origenes = ["http://a"]

    assert parse_cors_origins(origenes) is origenes


# --- DATABASE_URL ---------------------------------------------------------------------------


def test_db_01_sin_database_url_usa_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")

    settings = Settings(_env_file=None)

    assert settings.database_url == "sqlite:///" + (tmp_path / "data" / "app.db").as_posix()
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("otro_cwd", [False, True], ids=["cwd-actual", "DB-04-otro-cwd"])
@pytest.mark.parametrize(
    ("url", "ruta_esperada"),
    [
        pytest.param("sqlite:///./data/app.db", Path("data", "app.db"), id="DB-02-punto-barra"),
        pytest.param("sqlite:///data/app.db", Path("data", "app.db"), id="DB-03-sin-punto"),
        pytest.param("sqlite:///app.db", Path("app.db"), id="DB-03-en-la-raiz"),
        pytest.param(
            "sqlite:///./a/b/../c/app.db", Path("a", "c", "app.db"), id="DB-03-con-punto-punto"
        ),
    ],
)
def test_db_02_03_04_ruta_relativa_respecto_a_base_dir(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    url: str,
    ruta_esperada: Path,
    otro_cwd: bool,
) -> None:
    if otro_cwd:
        cwd = tmp_path / "otro"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
    base = tmp_path / "base"

    assert resolve_database_url(url, base) == url_sqlite(base / ruta_esperada)


def test_db_02_settings_resuelve_respecto_a_api(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./data/app.db")

    settings = Settings(_env_file=None)

    assert settings.database_url == url_sqlite(config.BASE_DIR / "data" / "app.db")
    assert list(tmp_path.iterdir()) == []


def test_db_05_url_absoluta_queda_identica(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'x' / 'app.db').as_posix()}"

    assert resolve_database_url(url, tmp_path / "base") == url


def test_db_05_url_absoluta_posix_queda_identica(tmp_path: Path) -> None:
    url = "sqlite:////tmp/x/app.db"

    assert resolve_database_url(url, tmp_path) == url


@pytest.mark.skipif(os.name != "nt", reason="Rutas con unidad: solo Windows")
@pytest.mark.parametrize("url", ["sqlite:///C:/x/app.db", "sqlite:///C:\\x\\app.db"])
def test_db_05_url_absoluta_con_unidad_queda_identica(tmp_path: Path, url: str) -> None:
    assert resolve_database_url(url, tmp_path) == url


@pytest.mark.parametrize("url", URLS_NO_SQLITE_DE_FICHERO)
def test_db_06_07_09_sin_fichero_sqlite_queda_identica(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, url: str
) -> None:
    monkeypatch.chdir(tmp_path)

    assert sqlite_file_database(url) is None
    assert resolve_database_url(url, tmp_path / "base") == url


def test_db_08_conserva_los_parametros_de_consulta(tmp_path: Path) -> None:
    resuelta = resolve_database_url("sqlite:///./data/app.db?timeout=30", tmp_path)

    assert resuelta == url_sqlite(tmp_path / "data" / "app.db") + "?timeout=30"


def test_db_10_crea_el_directorio_pero_no_el_fichero(tmp_path: Path) -> None:
    url = resolve_database_url("sqlite:///./deep/er/app.db", tmp_path)

    ensure_database_directory(url)
    ensure_database_directory(url)  # idempotente

    assert (tmp_path / "deep" / "er").is_dir()
    assert not (tmp_path / "deep" / "er" / "app.db").exists()


@pytest.mark.parametrize("url", URLS_NO_SQLITE_DE_FICHERO)
def test_db_11_sin_fichero_sqlite_no_crea_nada(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, url: str
) -> None:
    monkeypatch.chdir(tmp_path)

    ensure_database_directory(url)

    assert list(tmp_path.iterdir()) == []


# --- Efectos laterales ----------------------------------------------------------------------


def test_fx_01_secret_key_ausente_fuera_de_debug_no_crea_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.delenv("SECRET_KEY")

    with pytest.raises(ValidationError, match="SECRET_KEY es obligatoria"):
        Settings(_env_file=None)

    assert not (tmp_path / "data").exists()


def test_fx_02_configuracion_valida_no_crea_data(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")

    Settings(_env_file=None)

    assert not (tmp_path / "data").exists()


def test_fx_03_debug_sin_secret_key_genera_clave_efimera(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SECRET_KEY")

    with pytest.warns(RuntimeWarning, match="clave efímera"):
        settings = Settings(_env_file=None)

    assert settings.secret_key
