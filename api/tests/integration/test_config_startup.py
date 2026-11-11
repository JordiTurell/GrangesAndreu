"""Regresión de arranque (contrato base-tests-password §7.6.2, ST-01 a ST-10) y efectos de get_settings().

Los casos S ejecutan subprocesos sobre una COPIA temporal de `api/` (sin `.env` ni `data/`) con el cwd
y las variables que indica el contrato: ni el `api/.env` real ni `api/data/` intervienen, y no se abre
ningún puerto. Cada test crea y borra su propio directorio temporal.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core import config

API_DIR = Path(__file__).resolve().parents[2]
CAMPOS_SETTINGS = {nombre.upper() for nombre in config.Settings.model_fields}
IGNORAR_EN_LA_COPIA = shutil.ignore_patterns(
    ".env", ".env.*", "data", "__pycache__", ".pytest_cache", "tests", ".venv", "*.pyc"
)
SECRET_KEY_DE_PRUEBA = "clave-de-prueba-qa-0123456789abcdef0123456789"

# Réplica del formato de api/.env.example que describe el contrato (ST-01): el fichero real no se lee.
DOTENV_FORMATO_EXAMPLE = """\
DEBUG=true
SECRET_KEY=
DATABASE_URL=sqlite:///./data/app.db
CORS_ORIGINS=http://localhost:4200
"""

SCRIPT_CONFIG = """
import json, os
from app.core import config
s = config.settings
print(json.dumps({"base_dir": str(config.BASE_DIR), "cors": s.cors_origins, "db": s.database_url,
                  "clave_intacta": s.secret_key == os.environ.get("SECRET_KEY")}))
"""

SCRIPT_INIT_DB = """
import json
from app.core import config
from app.core.database import engine, init_db
init_db()
engine.dispose()
s = config.settings
print(json.dumps({"base_dir": str(config.BASE_DIR), "cors": s.cors_origins, "db": s.database_url}))
"""

# Arranque completo de la app (lifespan incluido) y preflight CORS por ASGI: sin abrir puertos.
SCRIPT_APP = """
import json
from main import app
from fastapi.testclient import TestClient
from app.core import config
from app.core.database import engine

def preflight(client, origen):
    r = client.options("/api/auth/login",
                       headers={"Origin": origen, "Access-Control-Request-Method": "POST"})
    return [r.status_code, r.headers.get("access-control-allow-origin")]

with TestClient(app) as client:
    salud = client.get("/health")
    datos = {"base_dir": str(config.BASE_DIR), "health": [salud.status_code, salud.json()],
             "cors": config.settings.cors_origins,
             "permitido": preflight(client, "http://localhost:4200"),
             "b": preflight(client, "http://b:4200"),
             "ajeno": preflight(client, "http://evil.example")}
engine.dispose()
print(json.dumps(datos))
"""


def borrar_arbol(raiz: Path) -> None:
    """Borra un directorio temporal en Windows: reintenta (antivirus) y quita el solo lectura."""

    def quitar_solo_lectura(funcion, ruta, _error) -> None:
        os.chmod(ruta, stat.S_IWRITE)
        funcion(ruta)

    for _ in range(5):
        try:
            shutil.rmtree(raiz, onexc=quitar_solo_lectura)
            return
        except OSError:
            time.sleep(0.2)
    shutil.rmtree(raiz, ignore_errors=True)


def url_sqlite(ruta: Path) -> str:
    return f"sqlite:///{ruta.resolve().as_posix()}"


def arbol(directorio: Path) -> list[str]:
    return sorted(p.relative_to(directorio).as_posix() for p in directorio.rglob("*"))


@dataclass
class Resultado:
    returncode: int
    stdout: str
    stderr: str

    @property
    def datos(self) -> dict:
        """Última línea JSON de la salida (con DEBUG=true SQLAlchemy escribe su eco antes)."""
        lineas = [linea for linea in self.stdout.splitlines() if linea.startswith("{")]
        assert lineas, f"sin JSON en la salida: {self.stdout[-400:]!r} / {self.stderr[-400:]!r}"
        return json.loads(lineas[-1])


@dataclass
class Entorno:
    raiz: Path
    copia: Path  # api/ sin .env ni data/
    cwd: Path  # directorio vacío distinto de la copia
    ajeno: Path  # directorio para DATABASE_URL absolutas fuera de la copia (no existe de entrada)

    def escribir_dotenv(self, contenido: str) -> None:
        (self.copia / ".env").write_text(contenido, encoding="utf-8")

    def ejecutar(
        self,
        script: str,
        variables: dict[str, str] | None = None,
        *,
        cwd: Path | None = None,
        avisos_como_error: bool = False,
    ) -> Resultado:
        env = {
            clave: valor
            for clave, valor in os.environ.items()
            if clave.upper() not in CAMPOS_SETTINGS | {"PYTHONPATH"}
        }
        env.update(PYTHONPATH=str(self.copia), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        env.update(variables or {})
        orden = [sys.executable]
        if avisos_como_error:
            orden += ["-W", "error::RuntimeWarning"]
        proceso = subprocess.run(
            [*orden, "-c", script],
            cwd=cwd or self.cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        return Resultado(proceso.returncode, proceso.stdout, proceso.stderr)

    def cwd_vacio(self) -> bool:
        return not any(self.cwd.iterdir())


@pytest.fixture
def entorno() -> Iterator[Entorno]:
    raiz = Path(tempfile.mkdtemp(prefix="granjas-qa-")).resolve()
    try:
        copia = raiz / "api"
        shutil.copytree(API_DIR, copia, ignore=IGNORAR_EN_LA_COPIA)
        assert not (copia / ".env").exists()
        assert not (copia / "data").exists()
        cwd = raiz / "cwd"
        cwd.mkdir()
        yield Entorno(raiz=raiz, copia=copia, cwd=cwd, ajeno=raiz / "ajeno")
    finally:
        borrar_arbol(raiz)


def exitoso(resultado: Resultado, entorno: Entorno) -> dict:
    assert resultado.returncode == 0, resultado.stderr[-800:]
    datos = resultado.datos
    # El subproceso ejecutó el código de la copia, no el de api/ (y por tanto no leyó api/.env).
    assert Path(datos["base_dir"]) == entorno.copia
    return datos


def fallido(resultado: Resultado, texto: str) -> None:
    assert resultado.returncode != 0
    assert texto in resultado.stderr


# --- ST-01 a ST-03: CORS_ORIGINS y .env con el formato de .env.example ------------------------


def test_st_01_dotenv_con_el_formato_de_env_example_arranca(entorno: Entorno) -> None:
    entorno.escribir_dotenv(DOTENV_FORMATO_EXAMPLE)

    datos = exitoso(entorno.ejecutar(SCRIPT_INIT_DB), entorno)

    assert datos["cors"] == ["http://localhost:4200"]
    assert datos["db"] == url_sqlite(entorno.copia / "data" / "app.db")
    assert (entorno.copia / "data" / "app.db").is_file()
    assert entorno.cwd_vacio()


def test_st_01_la_app_completa_arranca_con_el_formato_de_env_example(entorno: Entorno) -> None:
    entorno.escribir_dotenv(DOTENV_FORMATO_EXAMPLE)

    datos = exitoso(entorno.ejecutar(SCRIPT_APP), entorno)

    assert datos["health"] == [200, {"status": "ok"}]
    assert datos["permitido"] == [200, "http://localhost:4200"]
    assert datos["ajeno"][0] == 400
    assert datos["ajeno"][1] is None
    assert (entorno.copia / "data" / "app.db").is_file()
    assert entorno.cwd_vacio()


def test_st_02_dotenv_con_cors_en_lista_json(entorno: Entorno) -> None:
    entorno.escribir_dotenv(
        'DEBUG=true\nCORS_ORIGINS=["http://a:4200","http://b:4200"]\n'
        "DATABASE_URL=sqlite:///./data/app.db\n"
    )

    datos = exitoso(entorno.ejecutar(SCRIPT_CONFIG), entorno)

    assert datos["cors"] == ["http://a:4200", "http://b:4200"]


def test_st_02_la_app_completa_arranca_con_cors_en_lista_json(entorno: Entorno) -> None:
    entorno.escribir_dotenv(
        'DEBUG=true\nCORS_ORIGINS=["http://localhost:4200","http://b:4200"]\n'
    )

    datos = exitoso(entorno.ejecutar(SCRIPT_APP), entorno)

    assert datos["cors"] == ["http://localhost:4200", "http://b:4200"]
    assert datos["permitido"] == [200, "http://localhost:4200"]
    assert datos["b"] == [200, "http://b:4200"]
    assert datos["ajeno"][0] == 400


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        pytest.param("http://localhost:4200", ["http://localhost:4200"], id="CO-02-comas"),
        pytest.param(
            "http://a:4200, http://b:4200", ["http://a:4200", "http://b:4200"], id="CO-03-dos"
        ),
        pytest.param('["http://a:4200","http://b:4200"]', ["http://a:4200", "http://b:4200"], id="CO-05-json"),
        pytest.param('  ["http://a:4200"]  ', ["http://a:4200"], id="CO-02-json-con-espacios-alrededor"),
        pytest.param("", [], id="CO-07-vacia"),
    ],
)
def test_st_03_cors_como_variable_de_entorno_sin_dotenv(
    entorno: Entorno, valor: str, esperado: list[str]
) -> None:
    variables = {"DEBUG": "true", "CORS_ORIGINS": valor}

    datos = exitoso(entorno.ejecutar(SCRIPT_CONFIG, variables), entorno)

    assert datos["cors"] == esperado


def test_st_03_sin_cors_origins_usa_el_defecto(entorno: Entorno) -> None:
    datos = exitoso(entorno.ejecutar(SCRIPT_CONFIG, {"DEBUG": "true"}), entorno)

    assert datos["cors"] == ["http://localhost:4200"]


def test_st_03_la_variable_de_entorno_prevalece_sobre_dotenv(entorno: Entorno) -> None:
    entorno.escribir_dotenv('DEBUG=true\nCORS_ORIGINS=["http://de-dotenv:4200"]\n')

    datos = exitoso(
        entorno.ejecutar(SCRIPT_CONFIG, {"CORS_ORIGINS": "http://de-entorno:4200"}), entorno
    )

    assert datos["cors"] == ["http://de-entorno:4200"]


# --- ST-04 a ST-06: una configuración inválida no deja rastro ---------------------------------


@pytest.mark.parametrize(
    "variables",
    [
        pytest.param({"DEBUG": "false"}, id="ST-04-sin-database-url"),
        pytest.param(
            {"DEBUG": "false", "DATABASE_URL": "sqlite:///./sub/dir/app.db"},
            id="ST-05-database-url-relativa",
        ),
    ],
)
def test_st_04_05_secret_key_ausente_fuera_de_debug_no_crea_directorios(
    entorno: Entorno, variables: dict[str, str]
) -> None:
    antes = arbol(entorno.copia)

    resultado = entorno.ejecutar(SCRIPT_INIT_DB, variables)

    fallido(resultado, "SECRET_KEY es obligatoria")
    assert not (entorno.copia / "data").exists()
    assert not (entorno.copia / "sub").exists()
    assert arbol(entorno.copia) == antes
    assert entorno.cwd_vacio()


def test_st_04_secret_key_ausente_con_dotenv_en_la_copia(entorno: Entorno) -> None:
    entorno.escribir_dotenv("DEBUG=false\nDATABASE_URL=sqlite:///./data/app.db\n")

    resultado = entorno.ejecutar(SCRIPT_INIT_DB)

    fallido(resultado, "SECRET_KEY es obligatoria")
    assert not (entorno.copia / "data").exists()
    assert entorno.cwd_vacio()


@pytest.mark.parametrize(
    "database_url",
    [
        pytest.param("sqlite:///./sub/dir/app.db", id="ST-06-database-url-relativa"),
        pytest.param("", id="ST-06b-database-url-por-defecto"),
    ],
)
def test_st_06_cors_json_roto_no_crea_directorios(entorno: Entorno, database_url: str) -> None:
    antes = arbol(entorno.copia)
    variables = {"DEBUG": "true", "CORS_ORIGINS": '["x"', "DATABASE_URL": database_url}

    resultado = entorno.ejecutar(SCRIPT_INIT_DB, variables)

    fallido(resultado, "CORS_ORIGINS no es una lista JSON válida")
    assert not (entorno.copia / "data").exists()
    assert not (entorno.copia / "sub").exists()
    assert arbol(entorno.copia) == antes
    assert entorno.cwd_vacio()


@pytest.mark.parametrize(
    "variables",
    [
        pytest.param({"PORT": "no-es-un-puerto"}, id="port-no-numerico"),
        pytest.param({"DEBUG": "quizas"}, id="debug-no-booleano"),
        pytest.param({"ACCESS_TOKEN_EXPIRE_MINUTES": "x"}, id="expiracion-no-numerica"),
    ],
)
def test_fx_b_otras_configuraciones_invalidas_no_crean_directorios(
    entorno: Entorno, variables: dict[str, str]
) -> None:
    antes = arbol(entorno.copia)
    base = {"DEBUG": "true", "SECRET_KEY": SECRET_KEY_DE_PRUEBA}
    base.update(variables)

    resultado = entorno.ejecutar(SCRIPT_INIT_DB, base)

    assert resultado.returncode != 0
    assert "ValidationError" in resultado.stderr
    assert arbol(entorno.copia) == antes
    assert entorno.cwd_vacio()


# --- ST-07 y ST-08: DATABASE_URL relativa y absoluta ------------------------------------------


@pytest.mark.parametrize("cwd_en_la_copia", [False, True], ids=["cwd-ajeno", "cwd-app-de-la-copia"])
@pytest.mark.parametrize(
    ("url", "fichero", "ausente"),
    [
        pytest.param(
            "sqlite:///./deep/er/app.db", "deep/er/app.db", None, id="ST-07-punto-barra"
        ),
        pytest.param("sqlite:///deep/er/app.db", "deep/er/app.db", None, id="ST-07-sin-punto"),
        pytest.param(
            "sqlite:///./a/b/../c/app.db", "a/c/app.db", "a/b", id="ST-07-con-punto-punto"
        ),
    ],
)
def test_st_07_database_url_relativa_se_resuelve_respecto_a_api(
    entorno: Entorno, url: str, fichero: str, ausente: str | None, cwd_en_la_copia: bool
) -> None:
    cwd = entorno.copia / "app" if cwd_en_la_copia else entorno.cwd
    antes_de_app = arbol(entorno.copia / "app")

    resultado = entorno.ejecutar(
        SCRIPT_INIT_DB, {"DEBUG": "true", "DATABASE_URL": url}, cwd=cwd
    )

    datos = exitoso(resultado, entorno)
    assert datos["db"] == url_sqlite(entorno.copia / fichero)
    assert (entorno.copia / fichero).is_file()
    if ausente is not None:
        assert not (entorno.copia / ausente).exists()
    # Ni el cwd ajeno ni el directorio app/ (cwd de la variante) reciben nada.
    assert entorno.cwd_vacio()
    assert arbol(entorno.copia / "app") == antes_de_app


def test_st_08_database_url_absoluta_queda_identica_y_crea_su_directorio(
    entorno: Entorno,
) -> None:
    destino = entorno.ajeno / "abs" / "dir"
    url = f"sqlite:///{(destino / 'app.db').as_posix()}"

    datos = exitoso(entorno.ejecutar(SCRIPT_CONFIG, {"DEBUG": "true", "DATABASE_URL": url}), entorno)

    assert datos["db"] == url
    assert destino.is_dir()
    assert not (destino / "app.db").exists()
    assert not (entorno.copia / "data").exists()
    assert entorno.cwd_vacio()


# --- ST-09 y ST-10: sin fichero SQLite y regresión con variables válidas ----------------------


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("sqlite:///:memory:", id="ST-09-memoria"),
        pytest.param("postgresql+psycopg://u:p@localhost/db", id="ST-09-postgresql"),
    ],
)
def test_st_09_url_sin_fichero_sqlite_queda_identica_y_no_crea_nada(
    entorno: Entorno, url: str
) -> None:
    antes = arbol(entorno.copia)

    datos = exitoso(entorno.ejecutar(SCRIPT_CONFIG, {"DEBUG": "true", "DATABASE_URL": url}), entorno)

    assert datos["db"] == url
    assert not (entorno.copia / "data").exists()
    assert arbol(entorno.copia) == antes
    assert entorno.cwd_vacio()


# --- BUG-001 (OPS-002): make_url lanza ValueError con estas URL; Settings no debe fallar ni exponerlas

CENTINELA_CLAVE = "CLAVE-CENTINELA-QA"

SCRIPT_URL_IDENTICA = """
import json, os
from app.core import config
print(json.dumps({"base_dir": str(config.BASE_DIR),
                  "identica": config.settings.database_url == os.environ["DATABASE_URL"]}))
"""


@pytest.mark.parametrize(
    "plantilla",
    [
        pytest.param("postgresql://u:{clave}@h:abc/db", id="puerto-no-numerico"),
        pytest.param("postgresql://u:{clave}@h:/db", id="puerto-vacio"),
        pytest.param("mysql://u:{clave}@[::1/db", id="ipv6-sin-cerrar"),
    ],
)
def test_bug_001_url_no_parseable_no_rompe_settings_ni_filtra_la_clave(
    entorno: Entorno, plantilla: str
) -> None:
    url = plantilla.format(clave=CENTINELA_CLAVE)
    antes = arbol(entorno.copia)
    variables = {"DEBUG": "true", "SECRET_KEY": SECRET_KEY_DE_PRUEBA, "DATABASE_URL": url}

    configuracion = entorno.ejecutar(SCRIPT_URL_IDENTICA, variables)

    assert exitoso(configuracion, entorno)["identica"] is True
    assert CENTINELA_CLAVE not in configuracion.stdout + configuracion.stderr
    assert arbol(entorno.copia) == antes
    # El fallo sigue ocurriendo donde ocurría (create_engine), sin mostrar la clave.
    motor = entorno.ejecutar("import app.core.database", variables)
    assert motor.returncode != 0
    assert "create_engine" in motor.stderr
    assert CENTINELA_CLAVE not in motor.stdout + motor.stderr
    assert entorno.cwd_vacio()


def test_st_10_con_variables_validas_nada_cambia(entorno: Entorno) -> None:
    url = f"sqlite:///{(entorno.ajeno / 'valida' / 'app.db').as_posix()}"
    variables = {
        "DEBUG": "true",
        "SECRET_KEY": SECRET_KEY_DE_PRUEBA,
        "DATABASE_URL": url,
        "CORS_ORIGINS": '["http://localhost:4200"]',
    }

    resultado = entorno.ejecutar(SCRIPT_CONFIG, variables, avisos_como_error=True)

    datos = exitoso(resultado, entorno)
    assert datos["db"] == url
    assert datos["cors"] == ["http://localhost:4200"]
    assert datos["clave_intacta"] is True
    assert "RuntimeWarning" not in resultado.stderr  # no se genera clave efímera
    assert not (entorno.copia / "data").exists()


def test_fx_c_sin_database_url_se_crea_data_como_siempre(entorno: Entorno) -> None:
    datos = exitoso(entorno.ejecutar(SCRIPT_INIT_DB, {"DEBUG": "true"}), entorno)

    assert datos["db"] == url_sqlite(entorno.copia / "data" / "app.db")
    assert (entorno.copia / "data" / "app.db").is_file()
    assert entorno.cwd_vacio()


# --- get_settings(): el único punto con efecto en disco (EP-01-D7, mutación M14 de qa-OPS-001) -


@pytest.fixture
def directorio_temporal() -> Iterator[Path]:
    raiz = Path(tempfile.mkdtemp(prefix="granjas-qa-")).resolve()
    try:
        yield raiz
    finally:
        borrar_arbol(raiz)


@pytest.fixture
def settings_en_proceso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Entorno limpio y sin leer api/.env, para llamar a get_settings() dentro del proceso."""
    for nombre in CAMPOS_SETTINGS:
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setattr(config, "Settings", partial(config.Settings, _env_file=None))
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("SECRET_KEY", SECRET_KEY_DE_PRUEBA)


def llamar_a_get_settings() -> config.Settings:
    # __wrapped__ evita el lru_cache: get_settings() devolvería la instancia ya creada al importar.
    return config.get_settings.__wrapped__()


@pytest.mark.usefixtures("settings_en_proceso")
def test_get_settings_valida_crea_el_directorio_pero_no_el_fichero(
    monkeypatch: pytest.MonkeyPatch, directorio_temporal: Path
) -> None:
    destino = directorio_temporal / "deep" / "er"
    url = f"sqlite:///{(destino / 'app.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)

    resultado = llamar_a_get_settings()

    assert resultado.database_url == url
    assert destino.is_dir()
    assert not (destino / "app.db").exists()


@pytest.mark.usefixtures("settings_en_proceso")
def test_get_settings_sin_database_url_crea_data_dir_como_siempre(
    monkeypatch: pytest.MonkeyPatch, directorio_temporal: Path
) -> None:
    monkeypatch.setattr(config, "DATA_DIR", directorio_temporal / "data")

    resultado = llamar_a_get_settings()

    assert resultado.database_url == url_sqlite(directorio_temporal / "data" / "app.db")
    assert (directorio_temporal / "data").is_dir()
    assert not (directorio_temporal / "data" / "app.db").exists()


@pytest.mark.usefixtures("settings_en_proceso")
@pytest.mark.parametrize(
    ("variables", "texto"),
    [
        pytest.param({"DEBUG": "false", "SECRET_KEY": ""}, "SECRET_KEY es obligatoria", id="sin-clave"),
        pytest.param({"CORS_ORIGINS": '["x"'}, "CORS_ORIGINS no es una lista JSON válida", id="cors"),
        pytest.param({"PORT": "no-es-un-puerto"}, "port", id="port"),
    ],
)
def test_get_settings_con_configuracion_invalida_no_deja_directorios(
    monkeypatch: pytest.MonkeyPatch,
    directorio_temporal: Path,
    variables: dict[str, str],
    texto: str,
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(directorio_temporal / 'deep' / 'app.db').as_posix()}")
    monkeypatch.setattr(config, "DATA_DIR", directorio_temporal / "data")
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)

    with pytest.raises(ValidationError, match=texto):
        llamar_a_get_settings()

    assert list(directorio_temporal.iterdir()) == []


@pytest.mark.usefixtures("settings_en_proceso")
def test_get_settings_el_error_de_cors_no_incluye_el_valor_en_el_mensaje(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # CORS-3 y DB-6: el mensaje del validador es una constante; el valor solo va en input_value.
    monkeypatch.setenv("CORS_ORIGINS", '["http://valor-reconocible:4200"')

    with pytest.raises(ValidationError) as excinfo:
        llamar_a_get_settings()

    error = excinfo.value.errors()[0]
    assert error["loc"] == ("cors_origins",)
    assert error["msg"].endswith("CORS_ORIGINS no es una lista JSON válida")
    assert "valor-reconocible" not in error["msg"]


@pytest.mark.usefixtures("settings_en_proceso")
def test_get_settings_con_configuracion_invalida_y_url_por_defecto_no_crea_data(
    monkeypatch: pytest.MonkeyPatch, directorio_temporal: Path
) -> None:
    monkeypatch.setattr(config, "DATA_DIR", directorio_temporal / "data")
    monkeypatch.setenv("DEBUG", "false")
    monkeypatch.delenv("SECRET_KEY")

    with pytest.raises(ValidationError, match="SECRET_KEY es obligatoria"):
        llamar_a_get_settings()

    assert not (directorio_temporal / "data").exists()
