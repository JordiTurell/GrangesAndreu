# Informe QA · base-tests-password · API-001 (EP-01) · intento 1
**Veredicto:** APROBADO
**Alcance verificado:** API-001 (US-02; contrato §1 ADR-004, §3, §4.1, §5, §7.2 a §7.5; ADR-004 y `contracts/auth.md`); tests nuevos `api/tests/unit/test_password_bytes.py`; infraestructura de OPS-001 como herramienta.
**Estado del árbol** (`git status --porcelain -uall`, idéntico antes y después de verificar; HEAD `9a8c2c0`): ` M api/app/core/security.py`, ` M api/app/modules/auth/schemas.py`, ` M api/requirements.txt` (OPS-001, ya `done`), ` M tasks/base-tests-password.json` y `.md` (PM), `?? api/tests/__init__.py`, `conftest.py`, `test_health.py`, `unit/__init__.py`, `unit/test_config.py` (OPS-001), `?? api/tests/unit/test_password_bytes.py` (API-001), `?? reports/base-tests-password/entrega-API-001.md`, `entrega-OPS-001.md` y `qa-OPS-001.md`. Con este informe se añade `qa-API-001.md`. Nada fuera de alcance.
**Estado propuesto por tarea:** API-001 → `done`
**Entorno:** Windows, Python 3.13.5, bcrypt 5.0.0, pydantic 2.13.5 (core 2.46.5), starlette 1.7.0, fastapi 0.142.2, httpx2 2.16.0, pytest 9.2.0, SQLAlchemy 2.1.2; BD solo temporal; ningún puerto abierto.

## Resumen
- **Suite completa** (`python -m pytest`) desde `api/`: **90 passed** en `-v`, `-W error`, `-W error::DeprecationWarning` y con otro orden de ficheros; y **90 passed** en una copia sin `api/.env`, sin `data/` y sin variables de `Settings` (`-v`, `-W error`, `-W error::DeprecationWarning`). 0 avisos, sin `StarletteDeprecationWarning`, sin restos `granjas-tests-*`.
- **Integración con la app real** (`TestClient` + BD temporal, batería desechable de 34 tests, en copia, también con `-W error`): R-01 a R-14, L-01 a L-06, §7.4, §7.5, OpenAPI y regresión → **34 passed**. Contra HEAD, los mismos casos reproducen el 500 original.
- **Unitarios del Developer:** 37 tests; en orden normal, invertido, 8 órdenes aleatorios y **uno por uno (37/37)**; **26 mutaciones** manuales de `security.py` y `schemas.py`, **todas detectadas**.
- **Defectos:** ninguno S1, S2 ni S3. Dos S4 abiertos (BUG-004, BUG-005), ninguno causado por API-001 ni bloqueante.
- No ejecutado: bcrypt 4.x real (no instalado; simulado con un truncador, ver Cobertura), servidor HTTP real (uvicorn), Linux/macOS, versiones mínimas de las dependencias.

Método: scripts y copias de usar y tirar en `$env:TEMP\qa-api001-work` (fuera del repo, borrados al terminar). Copia de `api/` sin `.env`, `.env.example`, `data/` ni cachés (`robocopy`); copia «HEAD» = esa misma con `security.py` y `schemas.py` sustituidos por `git show HEAD:<fichero>`. No se añadió ningún fichero a `api/tests/`. Metadatos de `api/data` solo con `stat`: `app.db` 4096 B (sin cambios desde el inicio) y `app.db-wal` 24 752 B (sin cambios), con `mtime` (ns) idéntico antes y después de las 4 ejecuciones de pytest sobre `api/` y en la lectura final; el directorio sigue con esos tres ficheros. **Matiz:** el `mtime` de `app.db-shm` (32 768 B) cambió una vez, unos 12 minutos después de mi primera lectura y antes de lanzar ningún pytest sobre `api/` (hasta ese momento QA solo había ejecutado copias en `$env:TEMP`); no varió durante ni después de mis ejecuciones. Es el mismo comportamiento ya descrito en `qa-OPS-001.md`: el `python main.py` del usuario mantiene la BD abierta y toca el `-shm`; ningún test abre la BD real (guarda F-2). `api/.env`, `api/.env.example` y `api/data/app.db` no se abrieron (la importación de `app.core.config` en las 4 ejecuciones sobre `api/` lee `api/.env` por el propio código de producción, como en OPS-001). Los procesos del usuario siguen (puerto 8000, PID 3036; puerto 4200, PID 30632).

## Matriz de verificación por caso (árbol de trabajo frente a HEAD)
Se comprobó siempre `status_code` y, en los 422, `detail[0].loc == ["body","password"]`, `type` y `"72 bytes" in msg` (más `ctx == {"max_bytes": 72}`, que el contrato no exige). Sin 500 en ningún caso (`raise_server_exceptions=False`).

### §7.2 · `POST /api/auth/register`
| ID | Contraseña (bytes/caracteres) | Esperado | Árbol | HEAD (diferencial) | Resultado |
|----|------|------|-------|------|-----------|
| R-01 | `ñ*40` (80/40) | 422 `password_too_long`, sin usuario | 422 `password_too_long`, `loc`/`msg`/`ctx` correctos; `db_session`: 0 usuarios | **500** (traceback) | PASS |
| R-02 | `a*72` | 201 | 201 (`id, username, email, is_active, created_at`) | 201 | PASS |
| R-03 | `a*73` | 422 `password_too_long` (no `string_too_long`) | 422 `password_too_long`; 0 usuarios | 422 `string_too_long` | PASS |
| R-04 | `ñ*36` (72/36) | 201 | 201 | 201 | PASS |
| R-05 | `a*70+ñ` (72/71) | 201 | 201 | 201 | PASS |
| R-06 | `a*71+ñ` (73/72) | 422 `password_too_long` | 422 `password_too_long`; 0 usuarios | **500** | PASS |
| R-07 | `ñ*37` (74/37) | 422 `password_too_long` | 422 `password_too_long` | **500** | PASS |
| R-08 | `😀*18` (72/18) | 201 | 201 | 201 | PASS |
| R-09 | `😀*18+a` (73/19) | 422 `password_too_long` | 422 `password_too_long` | **500** | PASS |
| R-10 | `ñ*8` (16/8) | 201 | 201 | 201 | PASS |
| R-11 | `a*7` | 422 `string_too_short` | 422 `string_too_short`, `loc` correcto | 422 `string_too_short` | PASS |
| R-12 | `ñ*10000` (20000/10000) | 422 `password_too_long`, no 500 | 422 `password_too_long` | 422 `string_too_long` | PASS |
| R-13 | tras R-01, R-03 y R-06, mismo email/usuario con `Password123` | 201 (no 409) | 201 las tres veces; `db_session`: 0 usuarios tras el 422 y 1 tras el 201 | — | PASS |
| R-14 | `Password123` y duplicado | 201 y 409 `conflict` | 201; 409 `conflict` con el mismo email, con el email en mayúsculas y con el usuario en mayúsculas | 201 | PASS |
| extra | NFC/NFD: `n\u0303*24` (72/48) y `+a` (73/49) | cuenta bytes recibidos, sin normalizar | 201 y 422 `password_too_long` | — | PASS |
| extra | email ya registrado + `ñ*40` | 422 (la validación va antes de la BD; no revela si el email existe) | 422 `password_too_long` idéntico a email inexistente | — | PASS |
| extra | otros 422 (username corto, email inválido, `password` ausente, `password` numérica) | formato `detail` sin cambios | `string_too_short`, `missing`, `string_type` con su `loc` | — | PASS |
| extra | `a*1 000 000` y `😀*250 000` | 422, sin degradación | 422 `password_too_long` (0,01 s) | — | PASS |

### §7.3 · `POST /api/auth/login`
| ID | Escenario | Esperado | Resultado | Estado |
|----|-----------|----------|-----------|--------|
| L-01 | registrar y login con `ñ*36` | 200 con `access_token` y `refresh_token` | 200, ambos presentes, `token_type: bearer` | PASS |
| L-02 | usuario existente, login `ñ*40` | 401 `unauthorized`, "Credenciales inválidas" | 401 `{"error":{"code":"unauthorized","message":"Credenciales inválidas"}}`, `WWW-Authenticate: Bearer` | PASS |
| L-03 | email inexistente, login `ñ*40` | 401 con el mismo cuerpo que L-02 | 401; cuerpo, cabeceras `content-type` y `WWW-Authenticate` idénticos a L-02 y a «contraseña ASCII errónea» (usuario existente e inexistente) | PASS |
| L-04 | cuenta `ñ*36`, login `ñ*36+x` (73/37) | 401, sin truncamiento | 401 `unauthorized`; también con un `bcrypt` que trunca a 72 bytes (simulación de 4.x): 401 (ver Cobertura) | PASS |
| L-05 | login `😀*20` (80/20) | 401, no 500 | 401; además `😀*18` registra y entra (200) y `😀*18+a` da 401 | PASS |
| L-06 | login `a*73` | 422 `string_too_long` | 422 `string_too_long`, `loc == ["body","password"]`; `""` → 422 `string_too_short` | PASS |
| L-07 | `verify_password` (3 casos) | `False`, sin excepción | `False` en los tres (y `"\ud800"` y hash vacío → `False`) | PASS (unitario del Developer y reescrito por QA) |
| L-08 | `LoginRequest` | `ñ*40` válido; `a*73` → `string_too_long` | válido; `string_too_long` | PASS |

### §7.4 · piezas internas
| Pieza | Resultado |
|-------|-----------|
| `exceeds_password_limit`: `""`, `a*72`, `ñ*36`, `😀*18` → `False`; `a*73`, `ñ*37`, `😀*18+a` → `True` | PASS (Developer, y reescrito por QA) |
| `hash_password("a"*73)` y `("ñ"*40)` → `ValueError`; `hash_password("ñ"*36)` → hash `$2…` que `verify_password` acepta | PASS |
| `UserCreate` R-01, R-03, R-06, R-07, R-09 → `ValidationError`, `type == "password_too_long"`, `loc == ("password",)`; R-02, R-04, R-05, R-08, R-10 válidos; R-11 `string_too_short` | PASS |

### §7.5 · seguridad y contrato
| Criterio | Resultado | Evidencia |
|----------|-----------|-----------|
| Ninguna respuesta (201, 200, 401, 409, 422) ni `/me` con `hashed_password` ni `$2a$`/`$2b$` | PASS | Cada llamada de la batería lo comprueba y un test final recorre todas las respuestas acumuladas (más de 60) |
| Ningún caso devuelve 500 | PASS | `raise_server_exceptions=False`; salvo el sustituto aislado, ver BUG-004 |
| `/openapi.json` ↔ §5 | PASS | `UserCreate.required = [username, email, password]`; `UserCreate.password = {"type":"string","minLength":8,"title":"Password","description":"Mínimo 8 caracteres y máximo 72 bytes en UTF-8 (límite de bcrypt)."}` (sin `maxLength`); `LoginRequest.password = {"type":"string","maxLength":72,"minLength":1,"title":"Password"}`; `register` → 201 `UserRead` y 422 `HTTPValidationError`; `login` → 200 `TokenResponse` y 422 `HTTPValidationError`; `username` 3-80 y `email` `format: email` sin cambios; `UserRead` sin `hashed_password` |
| Sustituto aislado | Ver BUG-004 | |
| Regresión | PASS | login 200 con `Password123`; `/me` 200; refresh 200; `/refresh` con token de acceso → 401; `/me` con refresh token → 401 y sin token → 401; contraseña con otra capitalización → 401; usuario inactivo con contraseña correcta → 401 |

## Revisión del código (diff frente a HEAD)
| Punto | Resultado |
|-------|-----------|
| `exceeds_password_limit` única fuente del criterio | OK: `len(password.encode("utf-8")) > MAX_PASSWORD_BYTES` aparece solo en `security.py:30`; `schemas.py` y `hash_password`/`verify_password` la llaman. El resto de `encode`/`72` son el cuerpo de bcrypt, la `description` y `LoginRequest.max_length` (caracteres, a propósito) |
| `hash_password` lanza `ValueError` | OK (mensaje con "72 bytes"; el test monkeypatchea `bcrypt.hashpw` para demostrar que no se llama) |
| `verify_password` devuelve `False` sin llamar a bcrypt; codificación dentro del `try` | OK: la guardia queda dentro del `try`, de modo que `"\ud800"` (`UnicodeEncodeError` ⊂ `ValueError`) da `False`; sacarla del `try` (M05) rompe un test |
| Sin ciclo de importación | OK: `import app.core.security`, `app.modules.auth.schemas`, `…services`, `…controllers` y `main`, cada uno como primer import de un proceso nuevo con `-W error` → rc 0 |
| `UserCreate` sin `max_length` | OK (`Field(min_length=8, description=…)` + `AfterValidator`); `LoginRequest` sin cambios |
| Coherencia con §4.1 y ADR-004 | OK; el diff solo toca `security.py` (+10) y `schemas.py` (+18 −3); `services.py`, `controllers.py`, `config.py`, `database.py` y `main.py` intactos |
| Error de dominio | `PydanticCustomError("password_too_long", "…{max_bytes}…", {"max_bytes": 72})` → `msg == "La contraseña no puede superar los 72 bytes en UTF-8"` y `ctx == {"max_bytes": 72}`, como en ADR-004 |

**Diferencial frente a HEAD** (mismo script en dos copias, solo cambian `security.py` y `schemas.py`): con HEAD `register` con `ñ*40`, `a*71+ñ`, `ñ*37` y `😀*18+a` responde **500** (`ValueError` de bcrypt 5.x); con el árbol, 422 `password_too_long`. `a*73` y `ñ*10000` pasan de `string_too_long` a `password_too_long`. `login` (L-02, L-03, L-05, L-06, L-04) y los casos aceptados (R-02, R-04, R-05, R-08, R-10) no cambian entre HEAD y árbol.

## Calidad de los unitarios del Developer (37 tests)
- **Cobertura frente al contrato:** R-01 a R-11 (los marcados U), L-07, L-08, toda la tabla de §7.4, mensaje exacto, mínimo en caracteres y no en bytes, NFC frente a NFD, y el esquema JSON de `UserCreate` y `LoginRequest` (§5). Los casos I (R-12 a R-14, L-01 a L-06, §7.5 HTTP) son de QA-001.
- **Orden y cwd:** normal, invertido, 8 órdenes aleatorios (semillas 1 a 8) y cada test por separado (37/37); desde la raíz con ruta absoluta, desde `tests/` y desde `$env:TEMP` → verde. **Excepción:** `cwd = api/tests/unit` con ruta relativa → error de colección (BUG-005, común a todos los tests de la suite).
- **Mutación manual** (copias temporales; `M00` control: 37 passed). **26 mutaciones, todas detectadas:**
  | Mutación | Detectada por |
  |----------|---------------|
  | M01 contar caracteres | 10 tests (R-01, R-06, R-07, R-09, `exceeds…`, hash, verify) |
  | M02 `>=` en vez de `>` | 9 (72 exactos en helper, hash y `UserCreate`) |
  | M03 restaurar `max_length=72` | 3 (R-03, `string_too_long` frente a `password_too_long`, esquema JSON) |
  | M04 `verify_password` sin guardia | 1: `test_verify_password_no_llama_a_bcrypt_…` (con bcrypt 5.x el test del prefijo no lo detecta, ver OBS-3) |
  | M05 guardia fuera del `try` | 1: texto no codificable |
  | M06 `hash_password` sin guardia / M07 `TypeError` / M08 mensaje sin "72 bytes" | 2 cada una |
  | M09 `verify_password` devuelve `True` | 3 |
  | M10 UTF-16 / M11 normalizar NFC | 4 / 1 (`no_normaliza_unicode`) |
  | M12a `MAX=73` / M12b `MAX=71` | 13 / 19 |
  | M13 sin capturar `ValueError` en verify | 2 |
  | M15 sin `AfterValidator` / M16 tipo `string_too_long` / M17 mensaje sin "72 bytes" / M18 `ctx` con clave extra | 7 / 6 / 6 / 5 |
  | M19a `min_length=1` / M19b `min_length=9` | 3 / 2 |
  | M20 `LoginRequest` sin `max_length` / M21 `LoginRequest` valida bytes / M23 `min_length=0` | 2 / 1 / 2 |
  | M22 `description` sin "72 bytes" | 1 (esquema JSON) |
  | M24 esquema con criterio propio en caracteres / M25 criterio propio `> 73` | 5 / 3 |
- **Triviales:** ninguno. `test_limite_es_72_bytes` solo fija la constante, pero detecta M12; cada test falla ante al menos una mutación de la lista.
- **Control positivo de mi batería de integración:** contra M01, M02, M03, M04, M15, M21 y M24 falla (de 1 a 14 tests según el caso; M04 solo por la simulación de bcrypt 4.x); contra M06 (`hash_password` sin guardia) **no** falla, lo esperado: por HTTP es inalcanzable (el esquema rechaza antes y bcrypt 5.x lanza igualmente) y lo cubren los unitarios del Developer (M06 detectada arriba).

## Seguridad básica
- **Secretos:** el diff de `api/app` y los ficheros nuevos (`test_password_bytes.py`, `entrega-API-001.md`) no contienen JWT, hashes bcrypt, claves privadas ni claves: 0 coincidencias. Los tokens no se copian a este informe.
- **Contraseñas en logs:** con `caplog` a nivel DEBUG y `capfd`, ni la contraseña válida ni la larga (`ñ*40` + marca) aparecen en logs, salida estándar ni salida de error en register (201 y 422) y login (200 y 401). Con el engine global (`DEBUG=true`, `echo=True`) la contraseña en claro tampoco aparece; el **hash bcrypt sí** sale en el SQL de `INSERT` (OBS-2, previo y ajeno a esta tarea).
- **Errores nuevos:** el 422 de `password_too_long` devuelve `input` con la contraseña rechazada (`input == contraseña enviada`, verificado), tal como declara §8/ADR-004; lo único nuevo es el `ctx`. Sin otros datos internos.
- **Sin enumeración:** una contraseña larga con email existente o inexistente da el mismo 422; L-02 y L-03 son indistinguibles en cuerpo y cabeceras.
- **Árbol:** solo ficheros de la tarea, de OPS-001 (`done`), `tasks/` del PM y `reports/`.

## Defectos
No hay S1, S2 ni S3 abiertos. Dos S4 abiertos, no bloqueantes, ninguno causado por API-001:

### BUG-004 · Un sustituto Unicode aislado en `password` provoca 500 en `register` y `login` (formato 422 por defecto de FastAPI)
**Tarea/Historia:** API-001 / US-02 (preexistente; fuera del cambio de la tarea)   **Capa:** API
**Severidad:** S4   **Devolver a:** Arquitecto (redacción de §7.5 y §8) y PM (backlog; resolución en ADR-001)
**Entorno:** Windows, Python 3.13.5, pydantic 2.13.5, starlette 1.7.0, fastapi 0.142.2; copias temporales de HEAD y del árbol, BD temporal, `DEBUG` true y false
**Pasos para reproducir:** 1. Copia de `api/` con `main` y `DATABASE_URL`/`SECRET_KEY` de sesión. 2. `TestClient(main.app, raise_server_exceptions=False)`. 3. `POST /api/auth/register` con el cuerpo crudo `{"username":"sur0001","email":"sur0001@example.com","password":"\ud800abcdefgh"}` (`Content-Type: application/json`, escape JSON del sustituto). 4. Repetir con `POST /api/auth/login` y `{"email":"…","password":"\ud800"}`.
**Resultado esperado** (contrato §3 «jamás produce 500», §4.1 y §7.5 «en `login` debe dar 401, nunca 500»): `login` sin 500.
**Resultado actual:** **500** en `register` y en `login`, tanto con HEAD como con el árbol (`DEBUG=false`: `Internal Server Error`; `DEBUG=true`: traceback que acaba en `UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800' … surrogates not allowed`).
**Evidencia:** matriz HEAD/árbol: `SUR register password`, `SUR login (usuario existente)` y `SUR login (usuario inexistente)` → 500 en ambos. Control: el mismo 500 con el sustituto en `username` (register), en `email` (login) y en `refresh_token` (refresh), es decir, **no es específico de la contraseña ni de `auth.password`**. `UserCreate(password="\ud800abcdefgh")` y `LoginRequest(password="\ud800")` dan `string_unicode` con `loc == ("password",)` (pydantic rechaza el texto antes del `AfterValidator` y de `verify_password`); `verify_password("\ud800", hash)` → `False` (test unitario).
**Notas y clasificación:** la causa es el handler 422 por defecto de FastAPI: serializa `detail[].input` (el texto con el sustituto) y `JSONResponse.render` falla al codificar en UTF-8. API-001 no la introduce ni puede resolverla con los ficheros de la tarea (un handler de `RequestValidationError` es ADR-001, que además debería omitir `input` en `password`). **No es un BUG bloqueante de API-001**: el contrato §7.5 lo declara explícitamente como «observación no bloqueante, S4» y §8 dice que solo se garantiza `login` «sin 500 vía `verify_password`». Ambigüedad: la frase «en `login` debe dar 401, nunca 500» (§7.5) **no es alcanzable por HTTP aunque se corrigiera el handler**: el esquema rechazaría el texto con 422 `string_unicode`, nunca con 401; `verify_password` solo recibe textos codificables por HTTP. **Propuesta de redacción al Arquitecto (§7.5 y §8):** «Con sustitutos aislados (`"\ud800"`): `verify_password` devuelve `False` (L-07, unitario). Por HTTP, pydantic rechaza el valor (`string_unicode`) y, mientras no exista un handler de `RequestValidationError` (ADR-001), el handler por defecto lo convierte en 500 en cualquier campo de texto de cualquier endpoint (preexistente, S4); no se garantiza 401 ni 422 en register ni en login.» Y eliminar «debe dar 401, nunca 500» de §7.5. Registrarlo como entrada de ADR-001 (junto con la omisión de `input` en `password`).

### BUG-005 · Con `cwd = api/tests/unit` y ruta relativa el `conftest.py` de `tests/` no se carga (se saltan F-1 y F-2)
**Tarea/Historia:** OPS-001 / US-01 (infraestructura; también afecta a `test_password_bytes.py` y `test_config.py`)   **Capa:** API (tests)
**Severidad:** S4   **Devolver a:** PM (decisión: el contrato §4.2 prohíbe `pytest.ini` sin escalarlo; la solución sería un fichero de configuración en `api/` o documentar «ejecutar siempre desde `api/`»)
**Entorno:** Windows, Python 3.13.5, pytest 9.2.0; copia de `api/` sin `.env`, sin `data/` y sin variables de `Settings`
**Pasos para reproducir:** 1. `cd <copia>\tests\unit`. 2. `python -m pytest test_password_bytes.py`.
**Resultado esperado** (F-1 y F-2: el entorno se fija antes de importar `app.*` y la guarda aborta si no es la BD temporal): 37 passed con la BD temporal.
**Resultado actual:** `1 error`: `ValidationError … SECRET_KEY es obligatoria fuera de modo debug` al importar `app.core.config`. Con `DEBUG=true` en el shell (sin `.env`) el módulo se importa **sin** `conftest` (`37 passed`) y la importación crea el `data/` por defecto de la copia (`<copia>\data\`): se salta la fixture y su guarda.
**Evidencia:** `rc=2 … 1 error in 1.05s`; sin `-W error` igual. Desde `tests/` (`unit/test_password_bytes.py`), desde la raíz con ruta absoluta y desde `$env:TEMP` → 37 passed.
**Notas:** sin fichero de configuración, pytest toma como `rootdir` y `confcutdir` el directorio común de `cwd` y de los argumentos (`tests/unit`), por lo que `tests/conftest.py` queda fuera. Con el `api/.env` real presente el error se enmascararía previsiblemente (se usarían sus valores; no verificado, QA no lo usa). No afecta a `python -m pytest` desde `api/` (el comando del contrato), ni al uso normal. Mismo hallazgo para `test_config.py` (la verificación de OPS-001 desde ese directorio dio verde, probablemente por ese enmascaramiento del `.env` real).

## Observaciones (S4, sin acción obligatoria)
- **OBS-1 (Arquitecto/PM, al cerrar API-001):** `contracts/auth.md` conserva en la cabecera «rev. ADR-004 pendiente de `API-001`» y la nota «hasta entonces el código aplica `max_length=72` … y `register` devuelve 500» (líneas 2 y 6): quedan obsoletas al cerrar la tarea. El contrato §8 solo cita `AGENTS.md` y `qa.agent.md` (hueco conocido y caso `max_length=72`); conviene añadir `auth.md`.
- **OBS-2 (previo, backlog):** `database.py` crea el engine con `echo=settings.debug`; con `DEBUG=true` el hash bcrypt del `INSERT` aparece en el log SQL (verificado: `$2b$` presente con `DEBUG=true` y ausente con `false`; la contraseña en claro no aparece nunca). Candidato junto al «500 con traceback en modo debug» del backlog.
- **OBS-3 (tests):** con bcrypt 5.x, `checkpw` lanza `ValueError` para más de 72 bytes y `verify_password` lo captura, de modo que `test_l_07_verify_password_no_acepta_un_prefijo_de_72_bytes` pasa **también sin la guardia** (M04) y no discrimina en este entorno; solo lo detecta `test_verify_password_no_llama_a_bcrypt_…`. Sugerencia no bloqueante: monkeypatchear `bcrypt.hashpw`/`checkpw` con un truncador a 72 bytes dentro de ese test para que ejerza la propiedad «sin truncamiento» con independencia de la versión (como hace mi simulación de 4.x).
- **OBS-4 (previo):** `authenticate_user` no llama a `verify_password` cuando el usuario no existe: hay diferencia de tiempo entre usuario inexistente y contraseña errónea (ya señalado por el Developer; fuera de alcance).
- **OBS-5 (para ADR-001):** el 422 devuelve `input` con la contraseña rechazada y, con `ñ*10000`, reenvía los 10 000 caracteres (amplificación de la respuesta): otra razón para omitir `input` en `password`.
- **OBS-6:** bcrypt 5.0.0 acepta contraseñas con `\u0000` (201 en register y 401 en login): sin 500.

## Cobertura y huecos
- **bcrypt 4.x:** no hay una instalación real; se simuló con un `bcrypt` que trunca a 72 bytes (`hashpw`/`checkpw`) y el resultado no cambia (registro 201, `ñ*36` 200, `ñ*36+x` y `ñ*40` 401), lo que confirma la defensa en profundidad de `verify_password`. Sin verificar la versión mínima declarada (`bcrypt>=4.2.0`).
- No se probó con un servidor HTTP real (uvicorn) ni se abrieron puertos; la integración Front↔API no aplica (la épica no toca la Web). Tampoco Linux/macOS.
- Los casos I (R-xx, L-xx, §7.5) de esta verificación son desechables y **no se persistieron** (límite de la tarea): los persiste QA-001 en `api/tests/integration/`. Material reutilizable: R-01 a R-14 y los extra (NFC/NFD, email existente + contraseña larga, otros 422), L-01 a L-06 más el L-04 con bcrypt truncador, regresión de `/me` y `/refresh`, comprobación de `hashed_password`/`$2b$` en todas las respuestas y comprobación de logs.
- No se pidieron herramientas nuevas (`OPS-*`).

## Siguiente paso
1. **PM:** dar API-001 por `done` (los cambios quedan sin commit en el árbol; mensaje sugerido: `API-001: Rechazar con 422 las contraseñas que superan 72 bytes UTF-8 (ADR-004)`, ficheros `api/app/core/security.py`, `api/app/modules/auth/schemas.py`, `api/tests/unit/test_password_bytes.py`; épica EP-01, historia US-02, veredicto APROBADO, contrato `contracts/base-tests-password.md`, informe `reports/base-tests-password/qa-API-001.md`). Actualizar `AGENTS.md` y `qa.agent.md` (hueco `max_length=72`, ADR-004) según §8, y desbloquear QA-001.
2. **Arquitecto (BUG-004, OBS-1):** ajustar la redacción de §7.5 y §8 (sustitutos aislados) y la cabecera de `auth.md`. El PM pasa BUG-004, BUG-005, OBS-2, OBS-3 y OBS-5 al backlog (ADR-001 y una futura tarea `OPS` para `pytest.ini`/`rootdir`).
3. **QA-001:** persistir en `api/tests/integration/` los casos listados en Cobertura (con `client` y `db_session`), además de los ST-01 a ST-10 de §7.6.2.
