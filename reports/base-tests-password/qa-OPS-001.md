# Informe QA · base-tests-password · OPS-001 (EP-01) · intento 1
**Veredicto:** APROBADO
**Alcance verificado:** OPS-001 (US-01; contrato §1 EP-01-D1 a D4 y D8, §4.2 F-1 a F-10, §7.1 y §7.6.1)   **Estado del árbol:** `git status --porcelain -uall` (idéntico antes y después de la verificación) → ` M api/requirements.txt`, ` M tasks/base-tests-password.json` (del PM), `?? api/tests/__init__.py`, `?? api/tests/conftest.py`, `?? api/tests/test_health.py`, `?? api/tests/unit/__init__.py`, `?? api/tests/unit/test_config.py` y `?? reports/base-tests-password/entrega-OPS-001.md`. Nada fuera de alcance.
**Estado propuesto por tarea:** OPS-001 → `done`
**Entorno:** Windows, Python 3.13.5, starlette 1.7.0, fastapi 0.142.2, httpx2 2.16.0, pytest 9.2.0, pydantic-settings 2.15.0, SQLAlchemy 2.1.2; HEAD `f3a79f4` + árbol de trabajo; BD solo en temporales (`granjas-tests-*` del conftest y copias de `api/` en `$env:TEMP`).

## Resumen
- **35 sesiones completas de pytest en verde** (28 sobre `api/` con 53 tests y 7 sobre copias temporales con 53 + 6 sondas desechables) y **53 ejecuciones individuales** (una por test) en verde. 0 fallos, 0 tests inestables.
- **27 mutaciones** de `config.py` en una copia: 24 detectadas y 3 supervivientes: M05 (laguna de cobertura de CORS-2), M12b (aserción débil, BUG-002) y M14 (`get_settings()`, que el contrato asigna a QA-001); ver "Calidad de los unitarios".
- **Defectos:** ninguno S1, S2 ni S3. Dos S4 (BUG-002, BUG-003) y varias observaciones para el backlog.
- No ejecutado: Linux/macOS; `pytest.exe` a secas (el sistema deniega su ejecución, WinError 5); versiones mínimas `pytest 8.0.0` y `httpx2 2.0.0`; `api/.env` real (no se abre ni lee desde QA).

Método: scripts de usar y tirar en `$env:TEMP\qa-ops001-work` (fuera del repo, borrados al terminar con todas las copias). Las pruebas de aislamiento usan un *audit hook* de Python (`sys.addaudithook`) cargado con `-p` que registra `open`, `sqlite3.connect`, `os.mkdir`/`rename`/`remove`/`rmdir` y `os.scandir` sobre `\api\data`, `app.db` y `\api\.env`, y toda escritura bajo `api/` (salvo cachés). **Control positivo:** el mismo hook, contra una ruta `app.db` temporal, registró `sqlite3.connect`, `open` (escritura), `os.mkdir` y `os.remove`, de modo que habría detectado cualquier acceso real. Las mutaciones, `.env` de prueba y variables de shell contrarias se aplicaron **solo en copias** (`shutil.copytree` sin `.env`, `data/`, cachés ni `.venv`).

## Trazabilidad (DoD de OPS-001, §7.1 y puntos pedidos)
| # | Criterio | Caso | Resultado | Evidencia (truncada) |
|---|---|---|---|---|
| 1 | `python -m pytest -v` desde `api/` en verde | Ejecución exacta con `-W error::DeprecationWarning` (y con `-W error`, todos los avisos como error) | PASS | `53 passed in 1.12s` (rc 0); con `-W error`: `53 passed` |
| 2 | En verde **sin** `api/.env` y sin variables extra | Copia sin `.env` ni `data/`, entorno sin campos de `Settings`, `-W error::DeprecationWarning` y `-W error` | PASS | `59 passed` (53 + 6 sondas) ×2; `data/` no existe; árbol de la copia idéntico antes y después |
| 3 | Sin `StarletteDeprecationWarning` ni `RuntimeError` de `starlette.testclient` | Salida de las ejecuciones con `-W error` | PASS | La salida no contiene `warning`; rc 0 |
| 4 | `requirements.txt`: `pytest>=` y `httpx2>=2.0.0`, sin `httpx` | `git diff`, lectura de bytes, `grep httpx` en `api/**`, `import httpx2` / `import httpx` | PASS | Diff: solo `+pytest>=8.0.0` y `+httpx2>=2.0.0`; 11 líneas CRLF y ninguna LF suelta (estilo del fichero conservado); única coincidencia de `httpx` en `api/`: `requirements.txt:11 httpx2>=2.0.0`; `import httpx2` → 2.16.0; `import httpx` → rc 1 (no instalado) |
| 5 | Ningún fichero de `api/tests/` importa `httpx` ni `httpx2` | Búsqueda de texto | PASS | 0 coincidencias; `test_health.py` solo importa `TestClient` bajo `TYPE_CHECKING` y `conftest.py` de forma perezosa desde `fastapi.testclient` |
| 6 | Versiones de starlette, fastapi, httpx2 y pytest en la entrega, coherentes con las instaladas | `importlib.metadata` frente a `entrega-OPS-001.md` | PASS | starlette 1.7.0, fastapi 0.142.2, httpx2 2.16.0 (+`httpcore2` 2.16.0), pytest 9.2.0 (+pluggy 1.7.0, iniconfig 2.3.1, packaging 26.3, pygments 2.21.0, colorama 0.4.6, truststore 0.10.5), pydantic-settings 2.15.0, SQLAlchemy 2.1.2: todas coinciden. `pip check`: "No broken requirements found" |
| 7 | `GET /health` → 200 `{"status": "ok"}` (F-9) | `tests/test_health.py::test_health` | PASS | PASSED en todas las sesiones |
| 8 | Unitarios de §7.6.1 (`tests/unit/test_config.py`) en verde | `pytest tests/unit` | PASS | `52 passed` (rc 0) desde `api/`, desde la raíz, desde `tests/unit` y desde `$env:TEMP` |
| 9 | `api/data/app.db` no se crea ni se modifica (R-02/R-03) | Existencia, tamaño y mtime en ns antes/después de cada bloque (solo `os.stat`) + audit hook | PASS | Ver "Aislamiento". `app.db` 4096 B (15:20:09 del 10/11), `app.db-wal` 24 752 B (15:20:09), `app.db-shm` 32 768 B (11/11 11:03:00): idénticos en unas 85 ejecuciones sobre `api/` |
| 10 | Aislamiento entre tests (dos tests registran el mismo email → 201) | Sondas desechables en la copia (`test_probe_aislamiento_a/b`) | PASS | Ambos 201; en B `db_session` ve 0 usuarios al empezar; el usuario del test A no aparece en el `session.db` global (`select count(*) from users` → 0) |
| 11 | La guarda F-2 falla ruidosamente (F-2) | Plugin `-p` que importa `app.core.config` con otra `DATABASE_URL` antes del conftest | PASS | rc 2: `Exit: Los tests no pueden ejecutarse: settings.database_url no es la BD temporal de sesión (¿se importó app.* antes de cargar tests/conftest.py?). Se aborta para no tocar api/data/.`; sin restos `granjas-tests-*` |
| 12 | Fixture reutilizable (F-1 a F-8) | Revisión del código + sondas | PASS | Ver "Fixture" |
| 13 | Sin secretos ni claves reales; sin tocar nada fuera de alcance | Búsqueda de patrones (JWT `eyJ`, `$2b$`, claves privadas, cadenas ≥40 caracteres, `password/secret/token = "…"`) y `git status` | PASS | Solo constantes de prueba (`clave-solo-para-tests-0123456789abcdef`, 38 caracteres; `clave-de-prueba-…` en `test_config.py`); resto de coincidencias son nombres de test largos. `api/.env`: 532 B y mtime iguales que en `qa-OPS-002.md` |
| 14 | Entrega documentada y coherente | `entrega-OPS-001.md` frente al código y a mis ejecuciones | PASS | Ver "Entrega" |

## Resultados por nivel
### Aislamiento (R-02/R-03) y el cambio de `app.db-shm`
- **Audit hook sobre una sesión completa desde `api/`** (53 passed): **ningún** `open`, `sqlite3.connect`, `mkdir`, `rename` ni `remove` sobre `api\data` o `app.db`, y ninguna escritura bajo `api/` (salvo cachés). Solo dos eventos de lectura: (1) `os.scandir` sobre `api\data` lanzado por `_pytest/main.py` al recolectar (pytest recorre los subdirectorios de `api/` cuando se ejecuta sin argumentos desde `api/`; lista el directorio, no abre ningún fichero; OBS-1) y (2) un `open` de lectura de `api\.env` por `pydantic_settings` al importar `app.core.config` (comportamiento de producción, FX-D; QA no lo lee ni lo muestra; OBS-2).
- **Metadatos antes/después**, solo `os.stat` (existencia, tamaño y `st_mtime_ns` de `app.db`, `app.db-wal` y `app.db-shm`): 1 ejecución `-W error` con audit, 3 consecutivas, 11 con orden invertido o aleatorio, 53 individuales, 8 desde otros directorios y 3 concurrentes: idénticos siempre (última comprobación a las 11:21); `api/data/` sin ficheros nuevos.
- **`app.db-shm`:** al empezar mi verificación ya valía `11/11/2026 11:03:00` (local), el mismo valor que la entrega atribuye a la sesión del Developer, y no cambió en toda mi ventana (11:07 a 11:21, unas 85 ejecuciones de pytest sobre `api/`). Hallazgo: **ningún test abre ni toca la BD real**, de modo que el cambio no lo causa pytest. **Limitación:** el `python main.py` con reload del usuario (PID 3036, hijo 26840, puerto 8000; `ng serve`, PID 30632, puerto 4200, los mismos que en OPS-002) mantiene la BD abierta y no pude observar qué proceso escribió el `-shm` a las 11:03:00 (la causa «recarga del servidor tras escribir los `.py`» es plausible pero no demostrada). No los paré ni los toqué.
- **`.env` ajeno en copia** (copia sin `data/` ni `.env`, `PYTHONDONTWRITEBYTECODE=1`, árbol de ficheros comparado antes y después):
  | Caso | Resultado |
  |---|---|
  | `.env` con `DEBUG=false`, otra `SECRET_KEY`, `DATABASE_URL=sqlite:///./data/app.db`, `CORS_ORIGINS` con comas y `PORT=9999` | `59 passed`; la sonda confirma `settings.database_url == SESSION_DATABASE_URL`, `secret_key == TEST_SECRET_KEY`, `debug is True`; `cors_origins` sale del `.env` ajeno (no forma parte de F-1); no se crea `data/` |
  | Lo anterior + variables de shell contrarias (`DATABASE_URL=sqlite:///./otra/ruta.db`, `DEBUG=false`, `SECRET_KEY` vacía, `CORS_ORIGINS=http://z:1`) | `59 passed`; ni `data/` ni `otra/`; árbol idéntico (la asignación directa de F-1 prevalece; con `setdefault` se habría creado `otra/`) |
  | Variable de shell con `DATABASE_URL` absoluta en otro directorio temporal | `59 passed`; el directorio ajeno sigue vacío |
  | `.env` ajeno con `CORS_ORIGINS=["x"` (JSON roto) | rc 2: `2 errors during collection` (`ValidationError` al importar `app.core.config`); no se crea nada; sin restos. Comportamiento de producción, no de la fixture (OBS-2) |

### Fixture (`conftest.py`, F-1 a F-8) y robustez
| Requisito | Verificación | Resultado |
|---|---|---|
| F-1 entorno antes de importar, asignación directa | Lectura del código; variables de shell contrarias ignoradas; `SESSION_DIR` bajo `tempfile.mkdtemp(prefix="granjas-tests-")` fuera de `api/`; ruta POSIX; clave de 38 caracteres | PASS |
| F-2 guarda | Plugin de preimportación → rc 2 con mensaje claro | PASS |
| F-3 `engine` por test | `tmp_path/test.db`, `check_same_thread=False`, `create_all`, `dispose()` en el teardown. Sondas A→B: `shutil.rmtree` del `tmp_path` del test A (BD en WAL con conexiones abiertas) **no falla en Windows**, de modo que el engine se libera | PASS |
| F-4 `db_session` | `autoflush=False`, `expire_on_commit=False`; ve los datos escritos por `client` (también tras haber consultado antes) | PASS |
| F-5 `get_db` sobrescrito y retirado | Registros del test van a la BD del test, no al `session.db` global; `get_db not in dependency_overrides` en un test posterior | PASS |
| F-6 `client` en `with` (lifespan) con `raise_server_exceptions=False` | La tabla `users` existe en el engine global (`init_db()` del lifespan sobre la BD de sesión); `GET /no-existe` → 404 y una ruta que lanza → `status_code == 500` observable (EP-01-D2) | PASS |
| F-7 limpieza | `pytest_sessionfinish`: tras cada sesión (incluidos fallos de colección, guarda F-2, `--collect-only`, `--version`, `-k` sin coincidencias y 3 sesiones concurrentes) no queda `granjas-tests-*`. **Excepción:** `--help` (BUG-003, S4) | PASS (con BUG-003) |
| F-8 sin tocar la configuración local | Sin `api/.env` y con uno ajeno; `api/data/` intacto | PASS |
| Orden | Invertido y 10 aleatorios (semillas 1 a 10) | 11/11 PASS |
| Ejecución individual | 53 ids con `--collect-only -q`, uno por proceso | 53/53 PASS |
| Otro directorio | Desde la raíz (`api/tests`, `api/tests/unit`, un fichero y un `::test`), desde `api/tests`, `api/tests/unit`, `$env:TEMP` (ruta absoluta) y `web/` (`../api/tests`), con `-p no:cacheprovider` | 8/8 PASS (53, 52, 1, 1, 53, 52, 53, 53) |
| Consecutivas y concurrentes | 3 consecutivas y 3 sesiones a la vez (cada una con su `mkdtemp`) | PASS; sin restos |

### Calidad de los unitarios (§7.6.1)
**Cobertura frente al contrato:** CO-01 a CO-10, DB-01 a DB-11 y FX-01 a FX-03 están todos (52 tests; CO-02 a CO-07 y DB-02 a DB-04 parametrizados con el ID en el nombre). Añaden DB-02 a nivel `Settings`, DB-05 POSIX y con unidad de Windows (`/` y `\`) y las tres cadenas de BUG-001 (OPS-002) en DB-09 y DB-11. Aislamiento: `entorno_limpio` borra y fija las cuatro variables en cada test, `Settings(_env_file=None)`, `base_dir` y `DATA_DIR` sobre `tmp_path`, `monkeypatch.chdir` donde procede; no leen ni `api/.env` ni `api/data/` (el único acceso a `api/.env` es el de la importación de producción) ni usan `client`, `engine` o BD. Independientes del orden y del cwd (ver arriba).

**Mutación manual** en `app/core/config.py` de una copia (restaurada, control: 52 passed):
| Mutación | Resultado |
|---|---|
| M01 `except ArgumentError:` (sin `ValueError`) | Detectada: 6 fallos (DB-09 puerto no numérico, puerto vacío, IPv6 sin cerrar, en DB-06/07/09 y DB-11) |
| M02 quitar `NoDecode` | Detectada: 7 fallos (CO-02, CO-03, CO-04, CO-07 coma, CO-08…) |
| M03 resolver respecto al cwd | Detectada: 11 fallos |
| M04 sin `.resolve()` (no normaliza `..`) | Detectada: 2 fallos (DB-03 con `..`) |
| M06 `mkdir` de la ruta del fichero | Detectada: DB-10 |
| M07 `mkdir` en el validador antes de `SECRET_KEY` | Detectada: FX-01, FX-02 y DB-01 |
| M08 `ensure_database_directory` en el validador | Detectada: FX-02 y DB-01 |
| M09 re-renderizar la URL absoluta | Detectada (rc 2) por la guarda F-2 antes de ejecutar los tests: la BD de sesión deja de coincidir |
| M10 perder `?timeout=30` | Detectada: DB-08 |
| M11 sin rama JSON | Detectada: 5 fallos (CO-05, CO-06, CO-08, CO-09…) |
| M12a mensaje con el valor **al final** | Detectada: CO-08 |
| M13 sin comprobar `/` y `\` iniciales | Detectada: `test_db_05_url_absoluta_posix_queda_identica` (en Windows `/tmp` no es absoluta) |
| M15 sin `RuntimeWarning` | Detectada: FX-03 |
| M16 cadena vacía no devuelve `[]` | Detectada: CO-07 vacía y espacios |
| M17 sin `isinstance(str)` | Detectada: rc 2, error de colección al importar `app.core.config` |
| M18 `:memory:` como fichero / M19 URI `file:` como fichero / M20 sin comprobar backend | Detectadas: DB-06 memoria / DB-06 URI / DB-07 |
| M21 defecto de `DATABASE_URL` distinto / M23 defecto de CORS distinto | Detectadas: DB-01 / CO-01 |
| M22 no descartar vacíos | Detectada: CO-04, CO-07 coma |
| M24 condición de debug invertida / M25 clave efímera vacía | Detectadas: FX-01 y FX-03 / FX-03 |
| M26 `ensure_database_directory` también crea el fichero | Detectada: DB-10 |
| **M05** sin `strip()` de la cadena | **Sobrevive.** CORS-2 no tiene caso en §7.6.1 con espacios alrededor de una lista JSON (`'  ["http://a:4200"]  '`); con coma/vacío el resultado es el mismo. Laguna de cobertura (OBS-3) |
| **M12b** mensaje con el valor **al principio** | **Sobrevive** (BUG-002, S4): CO-08 solo comprueba `endswith`, aunque el test se llama `..._sin_incluir_el_valor` |
| **M14** `get_settings()` sin crear el directorio | **Sobrevive.** `get_settings()` no tiene unitario (lo declara la entrega): lo cubren ST-01/ST-07 de QA-001 por subproceso (contrato §7.6.3). No es defecto |

No hay tests triviales ni siempre en verde: todas las mutaciones que rompen una regla del contrato fallan al menos un test, salvo las tres de arriba.

### Entrega (`entrega-OPS-001.md`)
Coherente con el código y con mis ejecuciones: 53 tests (52 unitarios + humo), versiones instaladas, rangos `>=` sin `httpx`, ausencia de avisos, `api/data/` sin cambios, guarda F-2 (código 2 y mensaje), copia con `.env` propio y variables de shell contrarias, procesos de usuario (PID 3036 y 30632), `git status`, y desviaciones («ninguna»; los añadidos de `test_config.py` están declarados). Cumple los puntos de DoD (salida de pytest, versiones, decisiones de diseño y deuda: `.env` leído al importar, rangos `>=` sin verificar los mínimos, `pytest.exe` fuera del PATH, `get_settings()` sin unitario).

## Defectos
No hay S1, S2 ni S3 abiertos. Dos S4 (no bloquean; al backlog del PM):

### BUG-002 · CO-08 no verifica «sin incluir el valor» (una mutación que lo filtra sobrevive)
**Tarea/Historia:** OPS-001 / US-03   **Capa:** API (tests)
**Severidad:** S4   **Devolver a:** Developer (backlog; el Arquitecto puede endurecer la redacción de CO-08 en §7.6.1)
**Entorno:** Windows, Python 3.13.5, pytest 9.2.0; copia temporal de `api/`
**Pasos para reproducir:** 1. Copiar `api/` (sin `.env` ni `data/`) a `$env:TEMP`. 2. En `app/core/config.py` de la copia cambiar `raise ValueError("CORS_ORIGINS no es una lista JSON válida") from None` por `raise ValueError(text + " CORS_ORIGINS no es una lista JSON válida") from None`. 3. `python -m pytest tests/unit -q`.
**Resultado esperado** (CORS-3 y DB-6: el texto de error no incluye el valor de la variable): algún test falla.
**Resultado actual:** `52 passed`; `test_co_08_json_roto_aborta_sin_incluir_el_valor` solo asierta `msg.endswith("CORS_ORIGINS no es una lista JSON válida")` y `loc`, de modo que un valor al principio del mensaje pasa. (Con el valor al final, `endswith` sí falla.)
**Evidencia:** mutación M12b: `rc=0 ... 52 passed`; M12a: `FAILED test_co_08_...`.
**Notas:** el contrato (CO-08) pide literalmente «termina en»; el test lo cumple pero la garantía de seguridad no queda verificada. Sugerencia: añadir `assert "a:4200" not in error["msg"]` (el valor enviado era `["http://a:4200"`).

### BUG-003 · `pytest --help` deja un directorio `granjas-tests-*` vacío en `$env:TEMP`
**Tarea/Historia:** OPS-001 / US-01   **Capa:** API (tests)
**Severidad:** S4   **Devolver a:** Developer (backlog)
**Entorno:** Windows, Python 3.13.5, pytest 9.2.0
**Pasos para reproducir:** 1. `cd api`. 2. `python -m pytest --help`. 3. `Get-ChildItem $env:TEMP -Directory -Filter 'granjas-tests-*'`.
**Resultado esperado** (F-7, «limpieza de sesión» y petición de QA de no dejar restos): sin restos.
**Resultado actual:** queda un directorio vacío por invocación. `--version`, `--collect-only`, `-k sin_coincidencias` (rc 5), una colección con errores y la guarda F-2 (rc 2) **no** dejan restos.
**Evidencia:** tras `--help`: `granjas-tests-wc_sg6aq` con contenido `[]` (borrado por QA, era mío).
**Notas:** `mkdtemp` se ejecuta al importar el conftest y la limpieza solo está en `pytest_sessionfinish`, que no se invoca cuando pytest sale antes de iniciar la sesión. Impacto nulo en el uso normal; opciones: crear el directorio de forma perezosa o añadir un `atexit`.

## Observaciones (S4, sin acción obligatoria)
- **OBS-1:** `python -m pytest` sin argumentos desde `api/` recorre también `api/data/` (solo `os.scandir`, sin abrir ficheros). Un `testpaths = tests` lo evitaría, pero el contrato prohíbe `pytest.ini` sin escalarlo al PM: decisión suya.
- **OBS-2:** `app.core.config` lee `api/.env` al importarse (también en los tests; FX-D, ya señalado por el Developer). Un `.env` con `CORS_ORIGINS` JSON roto hace fallar la sesión en colección (rc 2, sin efectos en disco). Es la misma configuración inválida que impide arrancar la API.
- **OBS-3:** laguna de cobertura: añadir a CO-0x un caso con espacios alrededor de una lista JSON (CORS-2, mutación M05).
- **OBS-4:** `pytest.exe` (`%APPDATA%\Python\Python313\Scripts`) devuelve «Acceso denegado» al lanzarse desde Python en esta máquina, así que no se verificó el comando `pytest` a secas; `python -m pytest` (el del contrato) sí.
- **OBS-5 (para API-001 y QA-001):** (a) el conftest deja `DEBUG`, `SECRET_KEY` y `DATABASE_URL` en `os.environ`: los subprocesos ST-xx de QA-001 deben derivar su entorno **quitando** los campos de `Settings` (§7.6.2); (b) el conftest se importa como `tests.conftest`; (c) `db_session` ve los cambios del `client` aunque haya consultado antes (comprobado con la sonda).
- **OBS-6 (riesgo R-06):** los pisos `pytest>=8.0.0` y `httpx2>=2.0.0` solo están verificados con 9.2.0 y 2.16.0, como declara la entrega.

## Cobertura y huecos
- No verificado: Linux/macOS; `pytest`/`pytest.exe` sin `python -m` (OBS-4); mínimos de las dependencias de test; `pytest-xdist` (no instalado).
- `get_settings()` y los ST-01 a ST-10 (subproceso) quedan para QA-001 (`api/tests/integration/test_config_startup.py`). Los casos I de `register`/`login` (US-02) llegan con API-001 y QA-001.
- No se pidieron herramientas nuevas (no hay `OPS-*` adicionales).
- QA no añadió tests a `api/tests/`.

## Siguiente paso
PM: dar OPS-001 por `done` y desbloquear API-001 (depende de OPS-001); pasar BUG-002, BUG-003 y OBS-1/OBS-3 al backlog (el Developer puede cerrar BUG-002 y OBS-3 junto con los unitarios de API-001, en `api/tests/unit/test_config.py`, que ya es zona suya). Al cerrar la épica, la puerta del PM de §7.6.3 usa el `api/.env` real: no la ejecutó QA.
