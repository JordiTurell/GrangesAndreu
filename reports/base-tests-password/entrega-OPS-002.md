## Entrega · OPS-002
**Intento:** 2 (el intento 1 fue RECHAZADO por QA: BUG-001, S3; ver `reports/base-tests-password/qa-OPS-002.md`)
**Contrato:** contracts/base-tests-password.md (aprobado), §1 (EP-01-D5 a D8), §4.3 y §7.6
**Estado propuesto:** in_qa

**Qué cambió en el intento 2 (BUG-001):**
- Único cambio de código: `api/app/core/config.py`, función `sqlite_file_database`: `except ArgumentError:` → `except (ArgumentError, ValueError):` (devuelve `None`, con un comentario de una línea sobre el motivo). `make_url` de SQLAlchemy 2.1.2 lanza `ValueError` (no `ArgumentError`) con puerto no numérico o vacío y con corchete IPv6 sin cerrar (`int(components["port"])` en `_parse_url`), de modo que `Settings` fallaba en `_apply_defaults` y pydantic mostraba `input_value` con la cola de la URL (credenciales). Ahora la función devuelve `None` (DB-1, DB-4) y el fallo vuelve a ocurrir en `create_engine`, como en HEAD.
- DB-6: no se ha añadido ningún `raise` ni `warn`; el único texto nuevo de la tarea sigue siendo `CORS_ORIGINS no es una lista JSON válida` (sin valores).
- `api/requirements.txt` y el resto del árbol: sin cambios respecto al intento 1.
- Al empezar el intento 2 el árbol ya contenía esa corrección; no se dio por buena: se verificó con ejecución real (sección "Verificación realizada (intento 2)"), incluido un control negativo con el código del intento 1.
- Historial: el intento 1 (15/15 PASS propios, rechazado por QA con 160 PASS y 3 FAIL por BUG-001) se conserva abajo como "Verificación del intento 1".

**Cambios (acumulados, intentos 1 y 2):**
- `api/app/core/config.py`:
  - `Settings.cors_origins` pasa a `Annotated[list[str], NoDecode]` (mismo defecto); `_split_origins` solo delega en `parse_cors_origins`.
  - Nuevas funciones puras `parse_cors_origins`, `sqlite_file_database` y `resolve_database_url` (reglas CORS-1..5 y DB-1..5) y `ensure_database_directory` (único `mkdir`). `sqlite_file_database` captura `(ArgumentError, ValueError)` desde el intento 2 (BUG-001).
  - `Settings._apply_defaults` sin efectos laterales: ya no llama a `mkdir`; defecto `sqlite:///{(DATA_DIR/'app.db').as_posix()}` y luego `resolve_database_url`. La comprobación de `SECRET_KEY` y la clave efímera con `RuntimeWarning` quedan como estaban.
  - `get_settings()` construye `Settings()`, llama a `ensure_database_directory` y devuelve; `settings = get_settings()` sigue evaluándose al importar.
  - Ningún mensaje nuevo incluye valores de variables (DB-6): el único texto nuevo es `CORS_ORIGINS no es una lista JSON válida`.
- `api/requirements.txt`: `pydantic-settings>=2.4.0` → `>=2.7.0` (solo esa línea).
- Sin cambios en `database.py`, `main.py`, `.env.example`, `.env`, `api/data/` ni endpoints. Sin ficheros de test: pytest llega con OPS-001, que escribirá los unitarios U de §7.6.1 en `api/tests/unit/test_config.py`.

**Cómo probar:** (OPS-002 no incluye tests en el repo; QA ejecuta ST-01..ST-10 con un script de usar y tirar, §7.6.2)
1. Copiar `api/` a un directorio temporal fuera del repo con `shutil.copytree(..., ignore=shutil.ignore_patterns('.env','data','__pycache__','.pytest_cache','tests','.venv'))`.
2. Lanzar `[sys.executable, "-c", <script>]` con `cwd` en un directorio vacío distinto, `PYTHONPATH=<copia>` y un entorno sin ninguna variable de `Settings`; el script importa `app.core.config` (y `app.core.database` + `init_db()` en ST-01 y ST-07) e imprime `cors_origins` y `database_url`.
3. Comprobar salida, stderr y contenido de la copia y del `cwd` según §7.6.2.
No importar `app.core.config` desde el `api/` real: lee `api/.env` y puede crear `api/data/`.

**Verificación realizada (intento 2):** script de usar y tirar en `$env:TEMP` (solo biblioteca estándar, borrado al terminar junto con todas las copias), una copia nueva de `api/` por caso (`shutil.copytree(..., ignore=shutil.ignore_patterns('.env','data','__pycache__','.pytest_cache','tests','.venv'))`), subprocesos con `cwd` en un directorio vacío distinto de la copia, `PYTHONPATH=<copia>` y un entorno sin ningún campo de `Settings`. No se ha leído ni usado `api/.env` ni `api/data/`; `api/.env.example` solo se copió dentro de la copia temporal (ST-01 lo exige), sin modificarlo. Resultado: **33/33 PASS** (más un control negativo y 2 observaciones del fuzz, abajo). Git solo en lectura.

Versiones: Python 3.13.5, `pydantic-settings` **2.15.0**, `sqlalchemy` **2.1.2**, `pydantic` 2.13.5. `bootstrap._missing_requirements() == []` (importar `main` no instala nada).

**Evidencia de BUG-001 resuelto:**

1. Control negativo (copia temporal con el `except ArgumentError:` del intento 1; el script lo detecta):
```
'postgresql://u:p@h:abc/db' LANZA ValueError
'postgresql://u:p@h:/db' LANZA ValueError
'mysql://[::1/db' LANZA ValueError
```
2. Código actual, `sqlite_file_database`, `resolve_database_url` y `ensure_database_directory` en subproceso sobre copia (DB-09 ampliado). Las 22 cadenas son una reconstrucción propia a partir del informe de QA (que solo enumera parte): `no-es-una-url`, `""`, `"   "`, `://`, `sqlite://`, `sqlite:///:memory:`, URI `file:`, `sqlite:///a?b=%zz`, `mysql://`, `postgresql://`, `postgresql+psycopg://u:p@h/db`, IPv6 válida, puerto `-1`, `99999`, de 20 dígitos, con espacio, con `+`, con dígitos Unicode, de 5000 dígitos y las 3 de BUG-001.
```
[PASS] DB-09 ampliado: 22 cadenas, ninguna lanza, no-parseables -> None / misma cadena
       'mysql://[::1/db'                    sfd={'ok': True, 'value': None} rdu_igual=True
       'postgresql://u:p@h:/db'             sfd={'ok': True, 'value': None} rdu_igual=True
       'postgresql://u:p@h:abc/db'          sfd={'ok': True, 'value': None} rdu_igual=True
[PASS] DB-11 las no-SQLite-fichero no crean nada (copia y cwd intactos)
[PASS] Fuzz 8000 cadenas (semilla 20261111): sin ValueError/ArgumentError/otras (solo OSError de Path.resolve)
```
3. Centinela de contraseña (`DEBUG=true`, `SECRET_KEY` de prueba, `DATABASE_URL=postgresql://u:SENTINELPW@h:abc/db`; también `...@h:/db` y `mysql://u:SENTINELPW@[::1/db`), NUEVO frente a HEAD (`git show HEAD:api/app/core/config.py` en otra copia):
```
[PASS] [h:abc/db] NUEVO: import app.core.config no falla (rc=0) y sin centinela
[PASS] [h:abc/db] NUEVO: falla en create_engine (database.py), rc=1, sin centinela
       ValueError: invalid literal for int() with base 10: 'abc'
[PASS] [h:abc/db] HEAD: mismo fallo en create_engine, rc=1, sin centinela (referencia)
       ValueError: invalid literal for int() with base 10: 'abc'
[PASS] [h:abc/db] NUEVO == HEAD en el error final y rc de `import app.core.database`
[PASS] [h:abc/db] `from main import app`: NUEVO y HEAD igual (rc=1, sin centinela)
(idem [h:/db] -> ...base 10: ''   y   [[::1/db] -> ...base 10: ':1'; las 5 comprobaciones PASS en cada una)
```
`SENTINELPW` no aparece en `stdout` ni en `stderr` de ninguna de las 18 ejecuciones (3 URL × 3 importaciones × NUEVO y HEAD).

**ST-01, ST-02, ST-04 y ST-07 (intento 2; rutas temporales abreviadas como `<tmp>`):**
```
[PASS] ST-01 .env.example como .env (comas, ruta relativa) + init_db
       rc=0 cors=['http://localhost:4200'] db=sqlite:///<tmp>/c9/api/data/app.db data/app.db=True cwd_vacio=True
[PASS] ST-02 .env con CORS JSON
       rc=0 cors=['http://a:4200', 'http://b:4200'] db=sqlite:///<tmp>/c10/api/data/app.db
[PASS] ST-04 sin SECRET_KEY y DEBUG=false
       rc=1 data_existe=False stderr: ...ECRET_KEY es obligatoria fuera de modo debug. Defínela en el entorno o en api/.env [type=value_error, input_value={'debug': 'false'}, input_type=dict]
[PASS] ST-07 ruta relativa profunda, cwd distinto + init_db
       rc=0 db=sqlite:///<tmp>/c16/api/deep/er/app.db deep/er/app.db=True cwd_vacio=True
```
Resto (regresión): `[PASS]` ST-03 (comas y JSON por variable de entorno), ST-05 (`sub_existe=False`), ST-06 (`data=False sub=False`), ST-08 (`identica=True`), ST-09 (`sqlite:///:memory:` y `postgresql+psycopg://u:p@localhost/db`, `identica=True`) y ST-10 (`-W error::RuntimeWarning`: rc=0, `key_ok=True`, `stderr` vacío). En ST-04/05/06 se comprueba además que la copia queda idéntica (misma lista de ficheros) y que el `cwd` sigue vacío.

**`python -c "from main import app"` (puerta del PM)**, `DEBUG=true` y `DATABASE_URL` absoluta a un temporal, sobre la copia de `api/` (con `cwd` = la copia, como `cd api`, y con `cwd` vacío + `PYTHONPATH`; no se ejecutó contra el `api/` real porque leería `api/.env`):
```
[PASS] rc=0/0 allow_origins=['http://localhost:4200'] rutas=['/api/auth/login', '/api/auth/me', '/api/auth/refresh', '/api/auth/register', '/health']
```
La única salida de `stderr` es el `RuntimeWarning` de clave efímera (sin `SECRET_KEY`, igual que en HEAD).

**Estado del repo tras el intento 2** (`git status --porcelain -uall -- api`): ` M api/app/core/config.py` y ` M api/requirements.txt`; no se ha tocado nada más (sin `api/.env`, `api/.env.example`, `api/data/`). Temporales propios borrados (`Temporal borrado: True`); sin procesos ni servidores en marcha. En `$env:TEMP` quedan `ops002-r2-probe`, `ops002-r2-tools` y `ops002-r2-work-*`: no son de este intento y no se han tocado.

---

**Verificación del intento 1 (histórica, conservada; sigue vigente salvo `sqlite_file_database` ante URLs malformadas):** script de usar y tirar fuera del repo (solo biblioteca estándar, borrado al terminar), una copia nueva de `api/` por caso, sin `.env` ni `data/` salvo los creados por el propio caso. Resultado: **15/15 PASS** (ST-01..ST-10, piezas puras y puerta del PM). QA, con un script más amplio, obtuvo 160 PASS y 3 FAIL (BUG-001, corregido en el intento 2).

Versiones del intento 1: Python 3.13.5, `pydantic-settings` **2.15.0**, `sqlalchemy` **2.1.2**, `pydantic` 2.13.5.

Salida truncada (rutas temporales abreviadas como `<tmp>`):
```
[PASS] ST-01 .env.example como .env (comas, ruta relativa) rc=0
       {"cors": ["http://localhost:4200"], "db": "sqlite:///<tmp>/st01/api/data/app.db"}   # data/ y app.db creados; cwd vacío
[PASS] ST-02 .env con CORS JSON rc=0
       {"cors": ["http://a:4200", "http://b:4200"], "db": "sqlite:///<tmp>/st02/api/data/app.db"}
[PASS] ST-04 sin SECRET_KEY y DEBUG=false rc=1 data_existe=False
       stderr: ...value_error, input_value={'debug': 'false'}, input_type=dict]   # contiene "SECRET_KEY es obligatoria"; no existe <copia>/data; cwd vacío
[PASS] ST-07 ruta relativa profunda, cwd distinto rc=0
       {"cors": ["http://localhost:4200"], "db": "sqlite:///<tmp>/st07/api/deep/er/app.db"}   # existe <copia>/deep/er/app.db; cwd vacío
```
Resto de casos ejecutados:
```
[PASS] ST-03 variable de entorno (comas) rc=0   cors == ["http://localhost:4200"]
[PASS] ST-03 variable de entorno (JSON)  rc=0   cors == ["http://a:4200", "http://b:4200"]
[PASS] ST-05 como ST-04 con ruta relativa rc=1  sub_existe=False; cwd vacío
[PASS] ST-06 CORS JSON roto rc=1  data=False deep=False   # "...CORS_ORIGINS no es una lista JSON válida [type=value_error, input_value='["x"'..."
[PASS] ST-08 URL absoluta rc=0   db idéntica a la entrada; <tmp>/other/abs/dir creado; sin <copia>/data
[PASS] ST-09 sqlite:///:memory: rc=0 y postgresql+psycopg://u:p@localhost/db rc=0   db idéntica; sin <copia>/data
[PASS] ST-10 (-W error::RuntimeWarning) rc=0   {"cors": ["http://a:4200"], "db": "<la de entrada>", "key_ok": true}; stderr vacío
```
Piezas puras (subproceso sobre copia, `Settings(_env_file=None)`, `base_dir` temporal): PASS CO-01..CO-10, DB-01..DB-11, FX-01..FX-03, más CORS con `JSON sin recorte` y `CORS_ORIGINS=""` por variable de entorno real (confirma que `NoDecode` entrega la cadena cruda también desde el entorno).

Puerta del PM: desde una copia temporal sin `.env` ni `data/`, con `DEBUG=true` y `DATABASE_URL` absoluta temporal, `from main import app` funciona (`FastAPI`, `CORSMiddleware`, `allow_origins=['http://a:4200']`). Con `.env.example` copiado como `.env` dentro de la copia, `from main import app` arranca y `allow_origins == ['http://localhost:4200']`.

Contraste de `NoDecode` (`pip download --no-deps` en un directorio temporal fuera del repo, borrado después): `pydantic-settings==2.6.1` **no** contiene `NoDecode`; `2.7.0` sí (`pydantic_settings/__init__.py` y `sources.py`). 2.7.0 es el primer release con `NoDecode` (2.6.1 es el anterior), de modo que el piso del contrato se mantiene. Comprobación adicional con 2.7.0 instalada solo con `pip install --target` en un temporal (el entorno no se modificó): coma, JSON y cadena vacía se interpretan igual que con 2.15.0.

Estado final del repo (`git status --porcelain -uall`): modificados solo `api/app/core/config.py` y `api/requirements.txt` (más los ya modificados antes de la tarea: `.github/agents/{developer,pm,qa}.agent.md`, `AGENTS.md`, `flujo-agents.md`, `tasks/base-tests-password.{json,md}`) y nuevo este informe. `api/data/app.db`: Length 4096, LastWriteTime 15:20:09 del 10/11/2026 (sin cambios; no se ejecutó ningún proceso contra el `api/` real; `app.db-shm` y `app.db-wal` ya estaban en `api/data/`, ignorados por git). Copias y temporales borrados; sin procesos ni servidores en marcha. No se leyó ni se creó `api/.env`.

**Desviaciones del contrato:** ninguna del comportamiento observable. DB-1 cita solo `ArgumentError`; el comportamiento exigido (devolver `None` y no lanzar si `make_url` no parsea) obliga a capturar también `ValueError` (SQLAlchemy 2.1.2): el Arquitecto debería ajustar la redacción, como pide QA. Una del mecanismo sugerido en DB-3: `resolve_database_url` sustituye la ruta **textualmente** (`cabecera + ":///" + ruta_absoluta.as_posix() + "?" + consulta`) en lugar de `make_url(...).set(...).render_as_string(hide_password=False)`. Motivo: con SQLAlchemy 2.1.2 `render_as_string` codifica la unidad en Windows (`sqlite:///C%3A/...`) y rompe lo que exigen DB-02/DB-08/ST-01/ST-07 (`sqlite:///<base>/data/app.db` con ruta POSIX literal) y la coherencia con el defecto `sqlite:///{(DATA_DIR/'app.db').as_posix()}`. El texto textual conserva driver y parámetros de consulta tal como venían. El contrato dice que el cuerpo es del Developer, pero conviene que el Arquitecto/PM lo sepan por si quieren ajustar la redacción de DB-3.

**Deuda o riesgos detectados:**
- `bootstrap.ensure_dependencies()` solo comprueba presencia: un entorno con `pydantic-settings` < 2.7.0 ya instalado fallará con `ImportError` de `NoDecode` hasta que se actualice el paquete (previsto en §4.3).
- La sustitución textual no codifica ni decodifica caracteres especiales: una ruta de `api/` con `?` o `#` rompería la URL (igual que el defecto previo), y un `%` literal en la ruta absoluta se interpretaría como escape al volver a parsear. Casos raros, fuera de alcance.
- Una URL SQLite con host (`sqlite://host/ruta`, sin `:///`) se deja intacta sin resolver; `ensure_database_directory` crearía entonces el padre relativo al cwd. No es un formato soportado por el repo.
- Pre-existente (§8 del contrato): el `ValidationError` de configuración muestra `input_value` con el contenido de las variables (visible en la salida de ST-04/ST-05); no se cambia aquí.
- Los unitarios (casos U de §7.6.1) no existen aún: llegan con OPS-001. Las comprobaciones de piezas puras de esta entrega se hicieron con un script desechable.
- Hallazgo del fuzz del intento 2 (no corregido, fuera del alcance de BUG-001): `resolve_database_url` deja pasar el `OSError` de `Path.resolve()` (WinError 1113, "no hay traducción Unicode") con rutas SQLite relativas que mezclan `:` y dígitos no ASCII, p. ej. `sqlite+pysqlite:///db:memory:*C:٣///%41+-` (2 de 8000 cadenas aleatorias; `Path(...).resolve()` falla igual por sí solo). Es una ruta inválida en Windows que en HEAD fallaba más tarde, al abrir la BD; el mensaje contiene la ruta, no credenciales (SQLite no lleva contraseña). Se deja a decisión de QA/PM/Arquitecto; si se quiere cubrir, bastaría añadir `OSError` al manejo de DB-3.
- Observaciones OBS-1..OBS-7 del informe de QA: sin acción del Developer (S4, para el backlog del PM; OBS-2 es la redacción de DB-3 del Arquitecto).

**Siguiente paso:** QA (reverificación de OPS-002 tras BUG-001: repetir DB-09 ampliado, ST-01..ST-10, el diferencial HEAD/nuevo y `from main import app`, y comprobar `git status --porcelain -- api` y `api/data/app.db`); después OPS-001.
