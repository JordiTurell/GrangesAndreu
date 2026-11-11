# Informe QA · base-tests-password · OPS-002 (EP-01) · intento 2
**Veredicto:** APROBADO
**Alcance verificado:** OPS-002 (US-03; contrato §1 EP-01-D5 a D8, §4.3 y §7.6)   **Estado del árbol:** `git status --porcelain -uall -- api` → solo ` M api/app/core/config.py` y ` M api/requirements.txt` (+65/-8 líneas). El resto del árbol (`.github/agents/*`, `AGENTS.md`, `flujo-agents.md`, `tasks/*`, `web/angular.json`, `reports/…/entrega-OPS-002.md`) es ajeno y no se ha tocado; `git status` idéntico antes y después de la verificación.
**Estado propuesto por tarea:** OPS-002 → `done`
**Entorno:** Windows, Python 3.13.5, pydantic-settings 2.15.0, SQLAlchemy 2.1.2, pydantic 2.13.5; HEAD `f3a79f4` + árbol de trabajo; copias de `api/` sin `.env` ni `data/` en `$env:TEMP`; BD solo en temporales.

## Historial del intento 1 (resumen)
- Veredicto **RECHAZADO**: 172 comprobaciones, 160 PASS, 3 FAIL, 9 OBS. Único defecto: **BUG-001 (S3)**: `sqlite_file_database` solo capturaba `ArgumentError`, pero `make_url` lanza `ValueError` con puerto no numérico o vacío y con corchete IPv6 sin cerrar (`postgresql://u:p@h:abc/db`, `postgresql://u:p@h:/db`, `mysql://[::1/db`); `Settings` fallaba en `_apply_defaults` y pydantic mostraba la cola de la URL con la contraseña (contra DB-1, DB-4 y DB-6).
- Observaciones OBS-1 a OBS-7 (S4, sin acción del Developer): ver "Observaciones"; siguen vigentes y sin cambios.

## Resumen del intento 2
- Un script de usar y tirar (solo biblioteca estándar, en `$env:TEMP`, borrado al terminar junto con todas las copias) ejecutó **135 comprobaciones: 135 PASS, 0 FAIL, 8 observaciones informativas**.
- Una primera ejecución del propio script dio 14 FAIL, **todos defectos del script, no del producto** (comparaba `resolve_database_url` con un booleano en lugar de la cadena; imprimía la URL con el centinela y se autoinculpaba; en el control negativo la clave de prueba hacía que pydantic truncara el `input_value`; el diferencial no normalizaba la ruta de la copia ni separaba la creación deliberada del directorio de una ruta absoluta; `app.routes` no lista las rutas de `include_router` en esta versión de FastAPI y se pasó a `app.openapi()["paths"]`). Se corrigió el script y se repitió todo; los números de arriba son los de la segunda ejecución completa.
- Cubierto: CO-01..CO-10, DB-01..DB-11 y FX-01..FX-03 (piezas puras en subproceso sobre copia), ST-01..ST-10, regresión (`from main import app`, diferencial HEAD vs nuevo con 7 escenarios, OpenAPI idéntico, preflight CORS), BUG-001 (22 cadenas de DB-09 ampliado, 15 extra y fuzz de 20 000 URL), DB-6, el hallazgo del `OSError` (16 rutas relativas inválidas y 2 fuzz) y la Definition of Done de la entrega.
- No ejecutado: pytest y unitarios del repo (no existen hasta OPS-001), `TestClient` (falta `httpx2`; OPS-001), `api/.env` real (prohibido), Linux/macOS.

Método (§7.6.2): copia de `api/` por caso con `shutil.copytree(..., ignore=shutil.ignore_patterns('.env','data','__pycache__','.pytest_cache','tests','.venv'))`; subprocesos con `cwd` en un directorio vacío distinto de la copia, `PYTHONPATH=<copia>`, `PYTHONDONTWRITEBYTECODE=1` y entorno derivado de `os.environ` sin ningún campo de `Settings`; los `.env` se crean dentro de la copia (`.env.example` copiado como `.env` en ST-01, solo dentro de la copia); nunca se imprime `secret_key`. Comprobado antes: `bootstrap._missing_requirements() == []` (importar `main` no instala nada). Diferencial: copia con `git show HEAD:api/app/core/config.py` (git solo lectura) y una tercera copia de **control negativo** con el `except ArgumentError:` del intento 1, para confirmar que las pruebas detectan el defecto.

## Trazabilidad
| Criterio (US-03 / contrato) | Caso | Resultado | Evidencia (truncada) |
|---|---|---|---|
| BUG-001 / DB-1, DB-4: `sqlite_file_database` no lanza con URL no parseable | DB-09 ampliado (22 cadenas), 15 cadenas extra, fuzz de 20 000 URL | PASS | Las 22 y las 15: `sqlite_file_database`, `resolve_database_url` y `ensure_database_directory` no lanzan; las 3 de BUG-001 devuelven `None` / misma cadena / sin efecto en disco. Control negativo (código del intento 1): 11 de las 37 lanzan `ValueError`. Fuzz (semilla 20261111): 0 excepciones en `sqlite_file_database`; 3 `OSError` de `Path.resolve()` (ver OBS-8) |
| BUG-001: el fallo ocurre en `create_engine` como en HEAD y sin la contraseña | `DEBUG=true` y `DATABASE_URL=postgresql://u:SENTINELPW@h:abc/db`, `@h:/db` y `mysql://u:SENTINELPW@[::1/db`, con y sin `SECRET_KEY`; `import app.core.config`, `import app.core.database` y `from main import app` | PASS | NUEVO: `config` rc=0 y URL idéntica; `database` rc=1 con traceback por `create_engine` (database.py) y `ValueError: invalid literal for int() with base 10: 'abc'` (`''`, `':1'`); **idéntico a HEAD** (rc y excepción final); `SENTINELPW` ausente de stdout y stderr en todas las ejecuciones NUEVO y HEAD comprobadas (30). Control negativo sin clave: rc=1, `ValidationError` y `SENTINELPW` visible en stderr (reproduce BUG-001) |
| DB-6: ningún texto nuevo incluye valores | revisión estática del diff y 4 escenarios de error comparados con HEAD | PASS | Único `raise` nuevo: `raise ValueError("CORS_ORIGINS no es una lista JSON válida") from None` (constante, sin interpolación); ningún `warn` nuevo. CORS JSON roto, `PORT=abc` y `SECRET_KEY` con centinela: sin centinela en NUEVO ni en HEAD. `SECRET_KEY` ausente: el centinela de `DATABASE_URL` aparece en NUEVO **y** en HEAD (`input_value` de pydantic, pre-existente, contrato §8): sin filtración nueva |
| US-03.1 `.env` = `.env.example` arranca; JSON sigue funcionando | ST-01, ST-02, ST-03, CO-01..CO-10, REG con `.env.example` | PASS | ST-01 rc=0, `cors=['http://localhost:4200']`, `db=sqlite:///<copia>/data/app.db`, `data/app.db` creado, cwd vacío. ST-02 `['http://a:4200','http://b:4200']`. ST-03: coma, JSON y `""` (→ `[]`) por variable de entorno. `from main import app` con `.env.example`: rc=0, preflight `OPTIONS /api/auth/login` con `Origin: http://localhost:4200` → 200 y `access-control-allow-origin`; con `http://evil.example` → 400. HEAD con el mismo `.env`: rc=1 (`SettingsError … cors_origins … DotEnvSettingsSource`) |
| US-03.2 SQLite relativa respecto a `api/`, crea el directorio, independiente del cwd | ST-01, ST-07, DB-02, DB-03, DB-04, DB-08, DB-10 | PASS | ST-07 rc=0, `db=sqlite:///<copia>/deep/er/app.db`, `deep/er/app.db` existe, cwd vacío. DB-04: resultado idéntico desde otro cwd y sin dejar nada en él. DB-08 conserva driver y `?timeout=30` |
| US-03.3 un arranque fallido no crea `api/data/` | ST-04, ST-05, ST-06, ST-06b, FX-01, FX-B (PORT, DEBUG, ACCESS_TOKEN_EXPIRE_MINUTES) | PASS | ST-04 rc=1, "SECRET_KEY es obligatoria", `data/` no existe, copia y cwd sin cambios; ST-05 `sub/` no existe; ST-06 y ST-06b rc=1 con "CORS_ORIGINS no es una lista JSON válida" y ningún directorio creado; 3 configuraciones inválidas más: `added=[]` |
| US-03.4 con variables válidas nada cambia | ST-08, ST-09, ST-10, FX-02, FX-03 y diferencial HEAD vs nuevo (7 escenarios) | PASS | Mismo rc, `cors`, `db`, longitud de clave, aviso (`RuntimeWarning` de clave efímera) y ficheros creados en la copia y el cwd en los 7 escenarios. ST-10 con `-W error::RuntimeWarning`: rc=0, stderr vacío, clave intacta. **Única diferencia, deliberada (D6/D7, ST-08):** con URL SQLite absoluta NUEVO crea el directorio padre y HEAD no (ver OBS-9) |
| §4.3 piezas (CORS-1..5, DB-1..5) | CO-01..CO-10, DB-01..DB-11 y 21 casos CORS (12 del contrato y 9 propios) | PASS | JSON sin recorte de elementos; tipos mixtos → `loc=('cors_origins','1')`; `*`, mayúsculas, barra final y unicode sin normalizar; JSON truncado, coma final o texto extra → `ValidationError` sin el valor en el `msg`; objeto `{…}` tratado por comas; URL absolutas (unidad Windows con `/` y `\`, `/tmp`, UNC, `?timeout`), no SQLite, `:memory:`, URI `file:` y no parseables: **misma cadena**; defecto sin `DATABASE_URL` = `sqlite:///<DATA_DIR>/app.db` |
| §4.3 FX-A/B/C/D | FX-01..FX-03, FX-A, ST-04..ST-06 | PASS | `Settings()` y las funciones puras no crean nada; `get_settings()` crea el directorio solo tras construir `Settings` sin error y no crea el `.db` |
| §4.3 ficheros: solo `config.py` y `requirements.txt`; `pydantic-settings>=2.7.0` | `git status`, `git diff` | PASS | `git diff -U0 -- api/requirements.txt`: únicas líneas `-pydantic-settings>=2.4.0` / `+pydantic-settings>=2.7.0`. `database.py`, `main.py`, `.env.example`, `.env` y `data/` sin cambios (tamaño y fecha) |
| Regresión: la API importa y sirve | `from main import app` (HEAD y nuevo; `DEBUG=true` y `DATABASE_URL` absoluta temporal, con y sin `CORS_ORIGINS` JSON) | PASS | rc=0 en ambos y salida idéntica; `app.openapi()` con el mismo SHA-256 truncado (`2892f7313014b34c`) en HEAD y NUEVO; rutas `/api/auth/login`, `/api/auth/me`, `/api/auth/refresh`, `/api/auth/register`, `/health`; `GET /health` → 200 `{"status":"ok"}` (llamada ASGI directa, sin `TestClient`) |
| Aislamiento (§7.6.3) | metadatos antes y después, `git status` | PASS | Ver "Seguridad y aislamiento" |
| DoD de OPS-002: entrega con ST-01, ST-02, ST-04 y ST-07, versiones y documento | `entrega-OPS-002.md` | PASS | Ver "Definition of Done de la entrega" |

## Resultados por nivel
- **Piezas puras (U, vía subproceso):** CO-01..CO-10, DB-01..DB-11 y FX-01..FX-03 en PASS; DB-09 ya completo (BUG-001 resuelto).
- **Subproceso (S):** ST-01..ST-10 en PASS. Salida de esta ejecución (rutas abreviadas como `<tmp>`):
  ```
  ST-01 rc=0 cors=['http://localhost:4200'] db=...<tmp>/c067/api/data/app.db data/app.db=True cwd_vacio=True
  ST-02 rc=0 cors=['http://a:4200', 'http://b:4200']
  ST-04 rc=1 data_existe=False stderr: ...SECRET_KEY es obligatoria fuera de modo debug...
  ST-07 rc=0 db=...<tmp>/c076/api/deep/er/app.db deep/er/app.db=True cwd_vacio=True
  ```
- **Contrato/OpenAPI:** sin cambios de endpoints (SHA de `/openapi.json` idéntico a HEAD).
- **Integración Front↔API y SSR:** no aplica (la épica no toca la Web). Solo CORS por ASGI directo.
- **Regresión:** sin pytest (no existe). Equivalente ejecutado: diferencial HEAD vs nuevo (7 escenarios) y `from main import app` (3 variantes). Un `.env` equivalente al local (CORS en JSON) se simuló en la copia; el `api/.env` real no se leyó.

### Seguridad y aislamiento
- **Diff sin secretos:** el diff de `config.py` y `requirements.txt` no contiene secretos (patrones: cadenas ≥32 caracteres, `password/secret/token/api_key = "…"`, `eyJ…`, `$2b$`, claves privadas: 0 coincidencias). Tampoco la entrega.
- **Configuración inválida:** ST-04, ST-05, ST-06, ST-06b y 3 casos de FX-B: ni `data/` ni otro directorio o fichero en la copia ni en el cwd.
- **`api/.env` y `api/data/app.db`:** solo se compararon metadatos (sin abrir ni leer). Antes y después: `app.db` 4096 B, 10/11/2026 15:20:09; `app.db-wal` 24 752 B, 15:20:09; `app.db-shm` 32 768 B, 11/11/2026 8:29:08; `api/.env` 532 B, 15:20:37 (sigue existiendo); `.env.example` 442 B, 12:11:40; `config.py` 4469 B, 17:15:22 y `requirements.txt` 186 B, 16:57:25 (ambos del 10/11, anteriores a hoy); listado de `api/data/` idéntico (`app.db`, `app.db-shm`, `app.db-wal`). No se creó `api/tests/`.
- **Procesos ajenos:** en `8000` escucha `python.exe .\main.py` (PID 3036) y en `4200` `ng serve` (PID 30632), ambos del usuario y previos a la verificación; QA no los arrancó, no los tocó y no ha arrancado ni dejado ningún servidor.
- **Limpieza:** carpeta de herramientas y copias de trabajo borradas. En `$env:TEMP` quedan `ops002-r2-probe`, `ops002-r2-tools` y `ops002-r2-work-21ziwmxs` (ajenas, no se tocan; ver OBS-10).

### Definition of Done de la entrega (OPS-002)
| Punto | Estado |
|---|---|
| CORS con comas y con JSON se interpreta bien | Verificado por QA (CO-xx, ST-01..ST-03) |
| DATABASE_URL relativa desde cualquier cwd y crea el directorio | Verificado por QA (ST-01, ST-07, DB-04) |
| SECRET_KEY ausente fuera de debug no crea `api/data/` | Verificado por QA (ST-04) |
| La API arranca con el `api/.env` existente sin cambios | Equivalente verificado en copia (CORS JSON, `from main import app`); la comprobación con el `.env` real queda para la puerta del PM al cerrar la épica (§7.6.3) |
| Entrega con la salida de ST-01, ST-02, ST-04 y ST-07 | Presente (bloque "ST-01, ST-02, ST-04 y ST-07 (intento 2)"); coincide con esta ejecución |
| Versiones de pydantic-settings y sqlalchemy | Declaradas (2.15.0 y 2.1.2) y coinciden con las instaladas |
| Entrega documentada en `reports/base-tests-password/entrega-OPS-002.md` | Existe; documenta el cambio a `except (ArgumentError, ValueError)`, la desviación de DB-3 y las deudas |

### Verificación del cambio de código declarado por el Developer
El Developer declara que `sqlite_file_database` ya capturaba `(ArgumentError, ValueError)` al empezar el intento 2 y que solo cambió la entrega. Verificado: el árbol contiene `except (ArgumentError, ValueError):` y el control negativo con `except ArgumentError:` reproduce BUG-001 (rc=1, `ValidationError` y centinela visible), de modo que el cambio es real y es el que corrige el defecto. Dato de trazabilidad (OBS-10): `config.py` tiene fecha 10/11/2026 17:15:22, posterior a mi informe del intento 1 (17:11:09) y anterior a la entrega de hoy (11/11 9:57:50); la corrección se aplicó entre ambos, fuera de la entrega.

### Evaluación de la desviación declarada (DB-3: sustitución textual en lugar de `render_as_string`)
Verificado: con SQLAlchemy 2.1.2 `render_as_string` devuelve `sqlite:///C%3A/Users/x y/app.db` (codifica la unidad), lo que incumpliría las cadenas que exigen DB-02, DB-08, ST-01 y ST-07 (`sqlite:///<ruta POSIX literal>`). El comportamiento observable de la implementación textual **cumple** DB-02, DB-03, DB-04, DB-05, DB-08, ST-01 y ST-07, incluida la unidad de Windows, espacios, `ñ`, `#`, `@`, `+`, `;`, `&`, `=`, `,`, corchetes, paréntesis, `..` y backslashes (todas abren el fichero en la ruta esperada y `ensure_database_directory` crea el mismo directorio). **Observación, no defecto** (OBS-1 y OBS-2 abajo): el contrato debería actualizar la redacción de DB-3.

## Defectos
**No hay defectos abiertos. BUG-001 (S3) queda CERRADO** y no han aparecido defectos nuevos.

### BUG-001 · `sqlite_file_database` lanzaba `ValueError` con URL malformada — CERRADO
Verificado con las 3 cadenas originales, DB-09 ampliado (22), 15 cadenas extra, el diferencial HEAD vs nuevo con centinela de contraseña (con y sin `SECRET_KEY`), DB-6 y un control negativo con el código del intento 1 (que reproduce el defecto: rc=1, `ValidationError` y `SENTINELPW` visible en stderr). Con el código actual el fallo ocurre en `create_engine` (database.py) igual que en HEAD y sin la contraseña en stdout ni stderr.

### Evaluación del hallazgo fuera de alcance: `OSError` de `Path.resolve()`
**Clasificación: deuda / backlog (S4, OBS-8). No es defecto respecto al contrato y no bloquea.**
- **Reproducción:** `DATABASE_URL=sqlite+pysqlite:///db:memory:*C:٣///%41+-` (valor de prueba): NUEVO falla al importar `app.core.config` con `OSError: [WinError 1113]` propagado tal cual (no como `ValidationError`); en HEAD el mismo valor importa bien y falla después al abrir la BD (`init_db()`, rc=1). Sin ficheros ni directorios creados en la copia ni en el cwd (FX-B se cumple); el mensaje incluye la ruta, no credenciales ni la clave de prueba.
- **Alcance real:** exige una ruta SQLite **relativa** con `:` seguido de un dígito Unicode no ASCII (y, en las muestras, `*` o más `:`). Casos inválidos realistas en Windows (`a*b.db`, `a|b.db`, `a<b.db`, `CON`, `NUL`, `a.db.`, ` a.db`, ruta de 300 caracteres, `a:b.db`, `ab:٣`, `C:rel.db`) **no** lanzan. Frecuencia en fuzz (semilla 20261111): 3 de 20 000 URL aleatorias y 7 de 8000 rutas SQLite aleatorias, ambos alfabetos con `:` y `٣`; `sqlite_file_database` no lanzó en ninguna.
- **Contrato:** ningún criterio de §7.6 (CO, DB, FX, ST) lo cubre ni lo incumple. DB-1 y DB-4 hablan de URL que `make_url` no puede parsear (aquí sí parsea); DB-3 no define qué hacer si `resolve()` falla; FX-B se cumple; DB-6 se cumple (el texto lleva la ruta, no valores de variables sensibles). Es un camino de error nuevo, pero solo para una ruta que ya es inválida y que antes fallaba más tarde con otro error.
- **Recomendación (decisión del PM/Arquitecto, sin urgencia):** documentar en DB-3 que una ruta no resoluble se devuelve sin resolver y capturar `OSError` en `resolve_database_url` (el fallo queda en la apertura de la BD, como en HEAD), o aceptar el fallo temprano. No bloquea OPS-002 ni OPS-001.

## Observaciones (S4, no bloquean; para el backlog del PM)
- **OBS-1 · `%XX` en la ruta de instalación (consecuencia de la desviación DB-3).** SQLAlchemy decodifica `%XX` al parsear la URL; la sustitución textual no lo escapa. Con `api/` bajo un directorio `p%41q` y `DATABASE_URL=sqlite:///./data/app.db`, el SQLite se crea en `pAq/data/app.db`. HEAD (URL por defecto) falla con "unable to open database file" en ese mismo escenario (limitación preexistente). Declarado por el Developer; prácticamente irrelevante.
- **OBS-2 · Redacción de DB-3 desfasada.** `render_as_string(hide_password=False)` produce `C%3A` en 2.1.2; el contrato debería describir la sustitución textual (cabecera + `:///` + ruta POSIX + `?consulta`).
- **OBS-3 · `sqlite://host/a/b.db` (host en la URL SQLite).** Se deja intacta sin resolver y `ensure_database_directory` crearía `a/` relativo al cwd; SQLAlchemy rechazaría después esa URL en `create_engine`. Formato inválido y sin uso en el repo.
- **OBS-4 · Cadena JSON escalar entre comillas** (`CORS_ORIGINS="http://a"` con las comillas dentro del valor) se trata como lista por comas y produce `['"http://a"']`. Conforme a CORS-3/CORS-4 (solo `[` inicia JSON); sin acción.
- **OBS-5 · `%20` en ruta relativa** se decodifica a espacio (`./a%20b/app.db` → directorio `a b`), igual que lo haría SQLAlchemy en HEAD; coherente entre `resolve_database_url`, `ensure_database_directory` y el motor.
- **OBS-6 · `sqlite:///C:rel.db` (unidad relativa de Windows)** se resuelve como `<api>/rel.db`; sin excepción.
- **OBS-7 · Aviso de clave efímera:** el `RuntimeWarning` sigue apareciendo como en HEAD; no se ha cambiado su texto.
- **OBS-8 · `OSError` de `Path.resolve()`** con rutas SQLite relativas inválidas en Windows (ver "Defectos"). Backlog; decidir si `resolve_database_url` debe capturarlo.
- **OBS-9 · Redacción de FX-C frente a ST-08/EP-01-D7.** FX-C dice que con variables válidas el comportamiento no cambia, pero ST-08 y D7 exigen (y la implementación hace) crear el directorio padre de una URL SQLite **absoluta**, algo que HEAD no hacía (solo creaba `api/data/` con `DATABASE_URL` vacía). Cambio deliberado y probado (diferencial HEAD vs nuevo); el contrato debería precisar "salvo la creación del directorio padre de una ruta SQLite absoluta". También DB-1 debería citar `ValueError` además de `ArgumentError`.
- **OBS-10 · Trazabilidad y temporales ajenos.** (a) La corrección de BUG-001 está en `config.py` desde el 10/11 17:15:22 y la entrega del intento 2 no la describe como cambio propio. (b) Las carpetas `ops002-r2-*` de `$env:TEMP` (10/11, 17:15 a 17:18) coinciden en el tiempo con ese cambio, aunque la entrega afirma que no son de ese intento. QA no las ha tocado; conviene que el usuario o el Developer las borre.
- **OBS-11 · Pre-existente (contrato §8).** El `ValidationError` por `SECRET_KEY` ausente muestra en `input_value` el contenido de las variables leídas (incluido el centinela de `DATABASE_URL`); idéntico en HEAD y NUEVO. Candidato `hide_input_in_errors=True` para ADR-001 o backlog.

## Cobertura y huecos
- Los unitarios U de §7.6.1 no existen en el repo (llegan con OPS-001); aquí se ejecutaron con un script desechable. Los ST-xx se persistirán en QA-001 (`api/tests/integration/test_config_startup.py`).
- No verificado de forma independiente por QA: que `pydantic-settings==2.7.0` sea el primer release con `NoDecode` (QA no instala paquetes ni descarga artefactos; se toma de la entrega, que lo contrastó con 2.6.1 y 2.7.0). Con 2.15.0 instalada todo funciona.
- Sin Linux/macOS: las rutas `/…` y la sensibilidad a mayúsculas solo se comprobaron como cadenas. El `OSError` es específico de Windows (WinError 1113).
- Sin `TestClient`/lifespan completo (falta `httpx2`; OPS-001): CORS y `/health` por llamadas ASGI directas; `init_db()` vía script en ST-01 y ST-07.
- El `api/.env` real no se leyó ni se usó (lo comprobará el PM con la puerta del cierre de la épica). Un `.env` equivalente (CORS en JSON) se simuló en copia (ST-02, `from main import app`).
- No se hace hash de `api/data/*` (no se leen): el aislamiento se acredita con existencia, tamaño y fecha de modificación.
- Peticiones de herramienta (`OPS-*`): ninguna adicional.

## Siguiente paso
1. PM: marcar OPS-002 como `done` (BUG-001 cerrado) y proponer al usuario el commit de `api/app/core/config.py` y `api/requirements.txt` (sin `.env`, `*.db`, `data/`); continuar con OPS-001.
2. PM: pasar al backlog OBS-8 (decidir el tratamiento del `OSError`), OBS-9, OBS-10 y OBS-11; Arquitecto (sin bloquear): ajustar DB-1, DB-3 y FX-C en `contracts/base-tests-password.md`.
3. OPS-001: los unitarios de §7.6.1 deben incluir DB-09 con las 3 cadenas de BUG-001 como regresión.
4. QA-001: persistir ST-01..ST-10 y los casos de BUG-001 en `api/tests/integration/test_config_startup.py`.
