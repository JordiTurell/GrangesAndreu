## Entrega · OPS-001
**Intento:** 1
**Contrato:** contracts/base-tests-password.md (aprobado), §1 (EP-01-D1 a D4, D8), §4.2 (F-1 a F-10), §7.1 y §7.6.1
**Estado propuesto:** in_qa

**Cambios:**
- `api/requirements.txt`: añadidas `pytest>=8.0.0` y `httpx2>=2.0.0` (sin `httpx`; EP-01-D4). Se conservan los finales de línea CRLF del fichero.
- `api/tests/__init__.py` y `api/tests/unit/__init__.py`: vacíos (EP-01-D3).
- `api/tests/conftest.py`:
  - F-1: en el nivel de módulo, antes de cualquier import de `app.*` o `main`, asigna (sin `setdefault`) `DEBUG=true`, `SECRET_KEY` de prueba (38 caracteres) y `DATABASE_URL=sqlite:///<dir>/session.db`, con `<dir>` = `tempfile.mkdtemp(prefix="granjas-tests-")` y ruta en POSIX.
  - F-2: fixture de sesión `autouse` (`_guarda_entorno`) que comprueba `settings.database_url == SESSION_DATABASE_URL` y, si no, aborta con `pytest.exit(..., returncode=2)`.
  - F-3 `engine` (por test): SQLite en `tmp_path/"test.db"`, `check_same_thread=False`, `create_all` tras importar `app.modules.auth.entities`, `dispose()` en el teardown.
  - F-4 `db_session`: `Session` del `engine` (`autoflush=False`, `expire_on_commit=False`), cerrada en el teardown.
  - F-5 y F-6 `client`: `import main`, import perezoso de `fastapi.testclient.TestClient`, `get_db` sobrescrito con una sesión del `engine` del test (se elimina con `pop(get_db, None)`) y `TestClient(main.app, raise_server_exceptions=False)` en `with` (el lifespan ejecuta `init_db()` sobre el engine global, que es el temporal de sesión).
  - F-7: hook `pytest_sessionfinish` que hace `engine.dispose()` del engine global (solo si `app.core.database` se importó) y `shutil.rmtree(<dir>, ignore_errors=True)`.
- `api/tests/test_health.py`: `GET /health` → 200 y `{"status": "ok"}` (F-9). El tipo `TestClient` se importa bajo `TYPE_CHECKING`, de modo que el módulo no importa el cliente HTTP.
- `api/tests/unit/test_config.py`: 52 tests (casos U de §7.6.1) sobre `Settings(_env_file=None)`, `parse_cors_origins`, `sqlite_file_database`, `resolve_database_url` y `ensure_database_directory`, sin `client`, `engine` ni BD:
  - CO-01 a CO-10 (CO-02 a CO-07 parametrizados con el ID del contrato).
  - DB-01 (con `config.DATA_DIR` apuntando a `tmp_path`), DB-02 a DB-04 (ruta relativa respecto a `base_dir`, con y sin cambio de cwd; más un test a nivel `Settings` contra `config.BASE_DIR`), DB-05 (absoluta con ruta temporal, POSIX y, solo en Windows, con unidad y con barras invertidas), DB-06/07/09 (misma cadena y `sqlite_file_database` → `None`), DB-08, DB-10 y DB-11.
  - DB-09 incluye como regresión las tres cadenas de BUG-001 de OPS-002 (`postgresql://u:p@h:abc/db`, `postgresql://u:p@h:/db`, `mysql://[::1/db`), como pidió QA, además de `""` y `://`.
  - FX-01 a FX-03.
  - Fixture `autouse` `entorno_limpio` por módulo: borra `DATABASE_URL`, `CORS_ORIGINS`, `DEBUG` y `SECRET_KEY` y fija `DEBUG=true` y una `SECRET_KEY` válida; cada caso fija solo lo que necesita.
- Sin cambios en `api/app/**`, `main.py`, `api/.env`, `api/.env.example`, `api/data/`, `web/` ni `tasks/*.json`. No hay `pytest.ini` ni `pyproject.toml`: no hizo falta configuración de pytest.

**Cómo probar:**
```powershell
cd api
python -m pip install -r requirements.txt   # necesita red
python -m pytest -v
```
- Se usa `python -m pytest` (contrato §4.2): `pytest.exe` se instala en `C:\Users\jordi.turell\AppData\Roaming\Python\Python313\Scripts`, que no está en el PATH de esta máquina. `api/tests/__init__.py` hace que pytest ponga `api/` en `sys.path` (modo de importación por defecto), de modo que `import main` y `import app` funcionan también con `pytest` a secas.
- Funciona con o sin `api/.env`; las variables de F-1 prevalecen sobre él.
- Reutilización (API-001, QA-001): usar los argumentos `engine`, `db_session` y `client`. Los tests de integración van en `api/tests/integration/` (con su `__init__.py`).

**Verificación realizada:**
- Entorno: Windows, Python 3.13.5. Versiones instaladas (`importlib.metadata`):

  | Paquete | Versión |
  |---|---|
  | starlette | **1.7.0** |
  | fastapi | **0.142.2** |
  | httpx2 | **2.16.0** (con `httpcore2` 2.16.0) |
  | pytest | **9.2.0** (con `pluggy` 1.7.0, `iniconfig` 2.3.1, `packaging` 26.3, `pygments` 2.21.0, `colorama` 0.4.6, `truststore` 0.10.5) |
  | pydantic-settings / SQLAlchemy | 2.15.0 / 2.1.2 (sin cambios) |

  `pip install -r requirements.txt` instaló solo esos paquetes nuevos (`httpx` no está instalado ni se declara). `python -c "import httpx2"` funciona. El piso `httpx2>=2.0.0` solo está verificado con la 2.16.0 (EP-01-D4); no se probó otra versión.
- `python -m pytest -v` desde `api/`, con el `api/.env` del usuario presente (no se abrió ni se leyó): **53 passed in 0.70 s**:
  ```
  ============================= test session starts =============================
  platform win32 -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0 -- C:\Python313\python.exe
  cachedir: .pytest_cache
  rootdir: C:\proves\g\api
  plugins: anyio-4.15.1
  collecting ... collected 53 items

  tests/test_health.py::test_health PASSED                                 [  1%]
  tests/unit/test_config.py::test_co_01_ausente_usa_el_defecto PASSED      [  3%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-02-una-url] PASSED [  5%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-03-comas] PASSED [  7%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-04-espacios-y-vacios] PASSED [  9%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-05-json] PASSED [ 11%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-06-json-con-espacios] PASSED [ 13%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-07-vacia] PASSED [ 15%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-07-espacios] PASSED [ 16%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-07-coma] PASSED [ 18%]
  tests/unit/test_config.py::test_cors_origins_formatos[CO-07-json-vacio] PASSED [ 20%]
  tests/unit/test_config.py::test_co_08_json_roto_aborta_sin_incluir_el_valor PASSED [ 22%]
  tests/unit/test_config.py::test_co_09_elementos_no_str_se_rechazan PASSED [ 24%]
  tests/unit/test_config.py::test_co_10_una_lista_ya_construida_pasa_sin_cambios PASSED [ 26%]
  tests/unit/test_config.py::test_db_01_sin_database_url_usa_data_dir PASSED [ 28%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-02-punto-barra-cwd-actual] PASSED [ 30%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-02-punto-barra-DB-04-otro-cwd] PASSED [ 32%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-sin-punto-cwd-actual] PASSED [ 33%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-sin-punto-DB-04-otro-cwd] PASSED [ 35%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-en-la-raiz-cwd-actual] PASSED [ 37%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-en-la-raiz-DB-04-otro-cwd] PASSED [ 39%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-con-punto-punto-cwd-actual] PASSED [ 41%]
  tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-con-punto-punto-DB-04-otro-cwd] PASSED [ 43%]
  tests/unit/test_config.py::test_db_02_settings_resuelve_respecto_a_api PASSED [ 45%]
  tests/unit/test_config.py::test_db_05_url_absoluta_queda_identica PASSED [ 47%]
  tests/unit/test_config.py::test_db_05_url_absoluta_posix_queda_identica PASSED [ 49%]
  tests/unit/test_config.py::test_db_05_url_absoluta_con_unidad_queda_identica[sqlite:///C:/x/app.db] PASSED [ 50%]
  tests/unit/test_config.py::test_db_05_url_absoluta_con_unidad_queda_identica[sqlite:///C:\\x\\app.db] PASSED [ 52%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-06-sqlite-vacia] PASSED [ 54%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-06-memoria] PASSED [ 56%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-06-uri-file] PASSED [ 58%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-07-postgresql] PASSED [ 60%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-no-parseable] PASSED [ 62%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-vacia] PASSED [ 64%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-solo-separador] PASSED [ 66%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-puerto-no-numerico] PASSED [ 67%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-puerto-vacio] PASSED [ 69%]
  tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-ipv6-sin-cerrar] PASSED [ 71%]
  tests/unit/test_config.py::test_db_08_conserva_los_parametros_de_consulta PASSED [ 73%]
  tests/unit/test_config.py::test_db_10_crea_el_directorio_pero_no_el_fichero PASSED [ 75%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-06-sqlite-vacia] PASSED [ 77%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-06-memoria] PASSED [ 79%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-06-uri-file] PASSED [ 81%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-07-postgresql] PASSED [ 83%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-no-parseable] PASSED [ 84%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-vacia] PASSED [ 86%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-solo-separador] PASSED [ 88%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-puerto-no-numerico] PASSED [ 90%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-puerto-vacio] PASSED [ 92%]
  tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-ipv6-sin-cerrar] PASSED [ 94%]
  tests/unit/test_config.py::test_fx_01_secret_key_ausente_fuera_de_debug_no_crea_data PASSED [ 96%]
  tests/unit/test_config.py::test_fx_02_configuracion_valida_no_crea_data PASSED [ 98%]
  tests/unit/test_config.py::test_fx_03_debug_sin_secret_key_genera_clave_efimera PASSED [100%]

  ============================= 53 passed in 0.70s ==============================
  ```
  Dos ejecuciones más desde `api/` (`-q` y `-v`) dieron también 53 passed.
- Sin avisos: la salida de `pytest -v` no contiene `StarletteDeprecationWarning` ni sección de avisos; tampoco el `RuntimeError` de `starlette.testclient`. Búsqueda de texto de `httpx` en `api/`: solo aparece `httpx2` en `requirements.txt`; ningún fichero de `api/tests/` importa `httpx` ni `httpx2`.
- `api/data/` (solo existencia, tamaño y fecha; no se abrió ni leyó): `app.db` existe, 4096 B, y su fecha de modificación (`10/11/2026 15:20:09`, ticks UTC 639299172098399457) es idéntica antes y después de cada ejecución; `app.db-wal` también (24 752 B, ticks 639299172098471243). Comparando los tres ficheros inmediatamente antes y después de la última ejecución de `pytest -v` no hay ninguna diferencia. No se creó ningún fichero nuevo en `api/data/` ni quedan directorios `granjas-tests-*` en `$env:TEMP`.
- Pruebas en una copia temporal de `api/` fuera del repo (sin `.env` ni `data/`; `$env:TEMP\ops001-copia-*`, borrada al terminar; `.env.example` copiado sin tocarlo). Resultados:
  - Sin `.env`: 53 passed (más 3 de una prueba desechable de integración) con `-W error::DeprecationWarning`; no se crea `data/` en la copia. `pytest tests/unit` solo: 52 passed.
  - Aislamiento (US-01, §7.1): dos tests consecutivos que registran el mismo email responden ambos 201 y el segundo ve la tabla `users` vacía con `db_session`; `GET /no-existe` se observa como `status_code == 404`. Esa prueba desechable no se ha añadido al repo (su alcance es de QA-001).
  - Con un `.env` propio en la copia (`DEBUG=false`, otra `SECRET_KEY`, `DATABASE_URL=sqlite:///./data/app.db`, `CORS_ORIGINS` con comas): 56 passed y no se crea `data/` (las variables de F-1 prevalecen).
  - Con variables contrarias en el shell (`DATABASE_URL` a otra ruta, `DEBUG=false`, `SECRET_KEY` vacía): 56 passed y no se crea el directorio de esa ruta (asignación directa, no `setdefault`).
  - Guarda F-2: con un plugin (`-p`) que importa `app.core.config` con otra `DATABASE_URL` antes de cargar el conftest, la sesión se aborta con código 2 y el mensaje `Los tests no pueden ejecutarse: settings.database_url no es la BD temporal de sesión...`; el directorio temporal de sesión se borra igualmente.
- `get_errors` sobre `api/tests`: sin errores. Prettier no aplica (solo Web). No se ha arrancado ningún servidor ni abierto puertos; los procesos del usuario siguen en 8000 (`python.exe .\main.py`, PID 3036) y 4200 (`ng serve`, PID 30632), los mismos PID que en el informe de QA de OPS-002.
- Git (solo lectura): `git status --porcelain -uall` lista ` M api/requirements.txt`, ` M tasks/base-tests-password.json` (del PM) y los 5 ficheros nuevos de `api/tests/`; `.pytest_cache/` y `__pycache__/` no aparecen (ignorados).

**Desviaciones del contrato:** ninguna. Detalles de implementación que el contrato deja al Developer: el cierre de F-7 se hace con el hook `pytest_sessionfinish`; el helper `_session_factory` evita repetir el `sessionmaker`; `test_config.py` añade, además de §7.6.1, el test DB-02 a nivel `Settings`, variantes de DB-05 (POSIX y, solo en Windows, con unidad) y las cadenas de BUG-001 en DB-09 y DB-11.

**Deuda o riesgos detectados:**
- `app.core.config` sigue leyendo `api/.env` al importarse (comportamiento de producción, FX-D): esta tarea no lo lee ni lo usa, pero el `settings` global de la sesión de tests lo carga igualmente. Las variables de F-1 prevalecen y los unitarios usan `Settings(_env_file=None)`, de modo que ningún test depende de él; pero un `api/.env` con sintaxis inválida haría fallar la importación (y, por tanto, la sesión). Evitarlo exigiría tocar `config.py` (fuera de alcance): queda como aviso para el PM.
- El `python main.py` con reload del usuario vigila `api/`: al crear los `.py` de esta tarea `app.db-shm` pasó de `11/11 8:29:08` a `11:02:40` (coincide con la última escritura de `test_config.py`, 11:02:38) y a `11:03:00` después. Es plausible que sea el servidor del usuario reiniciándose o recibiendo peticiones; no lo causa `pytest` (las comparaciones antes/después de cada ejecución de pytest son idénticas y `app.db` y `app.db-wal` no han cambiado). Es solo una conjetura: no se ha comprobado qué proceso lo escribió.
- `httpx2>=2.0.0` solo está verificado con 2.16.0; `pytest>=8.0.0` solo con 9.2.0 (riesgo R-06 del plan: rangos `>=` sin versiones exactas).
- `pytest.exe` no está en el PATH de esta máquina; hay que usar `python -m pytest` (como indica el contrato).
- `tests/unit/test_config.py` no cubre `get_settings()` (el único punto con efecto en disco): lo cubren los ST-xx de QA-001 por subproceso.

**Siguiente paso:** QA de OPS-001 (`reports/base-tests-password/qa-OPS-001.md`); después API-001 (desbloqueada por OPS-001) y QA-001 usan `engine`, `db_session` y `client`.
