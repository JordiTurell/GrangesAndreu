# Contrato · base-tests-password (EP-01)
**Estado:** aprobado   **Alcance:** API
**Historias:** US-01, US-02   **Tareas que desbloquea:** OPS-001, API-001, QA-001

> Épica: infraestructura de tests de la API (US-01) y rechazo con 422 de las contraseñas de más de 72 bytes UTF-8 (US-02, [ADR-004](adr/ADR-004-password-bytes.md)). El comportamiento del módulo `auth` sigue descrito en [auth.md](auth.md), que se actualiza con esta épica.

## 1. Decisiones (ADR)
| ID | Decisión | Alternativas | Motivo | Consecuencias |
|----|----------|--------------|--------|---------------|
| [ADR-004](adr/ADR-004-password-bytes.md) (aceptado) | El límite de 72 bytes UTF-8 se valida en el esquema `UserCreate.password` con un helper único en `core/security.py`, con defensa en profundidad en `hash_password` y `verify_password`; `LoginRequest` no valida bytes | Validar en el servicio; capturar `ValueError` de bcrypt; pre-hash; truncar | 422 con el mecanismo vigente, antes de la BD y del hash; independiente de la versión de bcrypt | Cambian `schemas.py` y `core/security.py`; login no cambia de contrato |
| ADR-001 (pendiente) | **No bloquea este contrato:** el 422 usa el formato por defecto de FastAPI (`detail`), declarado en §3 | — | Fuera de alcance de la épica | Si cambia el envelope, se ajustan los tests; `type` y `loc` se conservan |
| EP-01-D1 | La fixture usa un directorio temporal de sesión para el engine **global** (variables de entorno fijadas antes de importar) y una BD SQLite **por test** enlazada con `get_db` sobrescrito | Una sola BD de sesión con limpieza de tablas; sobrescribir solo `get_db` | `settings` y `engine` son singletons creados al importar y el lifespan usa el engine global: sin fijar el entorno antes, se tocaría `api/data/app.db`; la BD por test da aislamiento total | El conftest debe fijar el entorno en el nivel de módulo, antes de cualquier import de `app.*` o `main` |
| EP-01-D2 | `TestClient(..., raise_server_exceptions=False)` | Valor por defecto (propaga excepciones) | Los tests verifican códigos HTTP reales, de modo que un 500 se observa como `status_code == 500` y no como excepción | Los tests deben asertar el código de estado explícitamente |
| EP-01-D3 | Estructura `api/tests/`: `conftest.py` y `test_health.py` (OPS-001); `unit/` (Developer, API-001) e `integration/` (QA, QA-001), cada subcarpeta con `__init__.py` | Ficheros planos | Cada rol escribe en su zona sin colisiones de nombres | La primera tarea que añada tests a una subcarpeta crea su `__init__.py` |

## 2. Modelo de datos
Sin cambios (tabla `users` en [auth.md](auth.md) §2). Migración: ninguna. Los hashes existentes no se modifican.

## 3. API
Solo cambian las respuestas descritas abajo; el resto de endpoints de `auth` no cambia.

### POST /api/auth/register
- **Auth:** pública
- **Request:** `UserCreate` — `{username, email, password}`; `password`: **mínimo 8 caracteres y máximo 72 bytes en UTF-8**
- **Response 201:** `UserRead` (sin `hashed_password`)
- **Errores:**
  - 409 → `{"error": {"code": "conflict", "message": ...}}` → email o usuario duplicado (sin cambios)
  - 422 → formato por defecto de FastAPI (`detail`, ADR-001 pendiente):
    - `password` de más de 72 bytes UTF-8 (cualquier número de caracteres):
      ```json
      {"detail": [{"type": "password_too_long", "loc": ["body", "password"],
                   "msg": "La contraseña no puede superar los 72 bytes en UTF-8",
                   "input": "<valor enviado>", "ctx": {"max_bytes": 72}}]}
      ```
    - `password` de menos de 8 caracteres → `type: "string_too_short"` (sin cambios)
    - resto de validaciones sin cambios
- **Reglas de negocio:**
  - El límite se cuenta en bytes de `password.encode("utf-8")`, sin normalización Unicode. 72 bytes exactos se aceptan; 73 se rechazan.
  - El mínimo de 8 se cuenta en caracteres.
  - La validación del esquema se ejecuta antes de consultar la BD: una contraseña rechazada no crea usuario ni revela si el email existe.
  - Nunca 500 por la longitud de la contraseña.

### POST /api/auth/login
- **Auth:** pública
- **Request:** `LoginRequest` — `{email, password}`; `password`: 1-72 **caracteres** (cota de tamaño, sin validación en bytes; sin cambios)
- **Response 200:** `TokenResponse` (sin cambios)
- **Errores:**
  - 401 `unauthorized` "Credenciales inválidas": usuario inexistente, contraseña errónea **o contraseña de más de 72 bytes** (≤72 caracteres), de forma indistinguible
  - 422 `detail`: `password` vacío o de más de 72 caracteres (`string_too_long`, sin cambios) o email inválido
- **Reglas de negocio:** una contraseña de más de 72 bytes nunca autentica (no hay truncamiento); jamás produce 500.

### GET /health
- **Auth:** pública. **Response 200:** `{"status": "ok"}`. Sin cambios; lo usa el test de humo.

## 4. Esquemas Pydantic y piezas internas
### 4.1 Auth (API-001)

| Elemento | Contrato |
|----------|----------|
| `core/security.py · exceeds_password_limit(password: str) -> bool` | Nuevo. `True` si `len(password.encode("utf-8")) > MAX_PASSWORD_BYTES`. Única fuente del criterio |
| `core/security.py · hash_password(password)` | Lanza `ValueError` si `exceeds_password_limit(password)`; en otro caso, sin cambios |
| `core/security.py · verify_password(password, hashed)` | Devuelve `False` (sin llamar a bcrypt) si `exceeds_password_limit(password)`; la codificación y la comprobación quedan dentro del `try` que captura `ValueError` y devuelve `False` (cubre también hash malformado y `UnicodeEncodeError`) |
| `UserCreate.password` | `str`, `Field(min_length=8, description=...)` + `AfterValidator` que lanza `PydanticCustomError("password_too_long", "La contraseña no puede superar los {max_bytes} bytes en UTF-8", {"max_bytes": MAX_PASSWORD_BYTES})` si `exceeds_password_limit`. **Sin `max_length`**. La `description` menciona "72 bytes" |
| `LoginRequest.password` | Sin cambios: `Field(min_length=1, max_length=72)` (caracteres) |
| Resto (`UserRead`, `TokenResponse`, `RefreshRequest`) | Sin cambios |

### 4.2 Infraestructura de tests (US-01 · OPS-001)
Ficheros: `api/requirements.txt` (añadir `pytest>=8.0.0` y `httpx>=0.27.0`, mismo estilo `>=`), `api/tests/__init__.py`, `api/tests/conftest.py`, `api/tests/test_health.py`. Ejecución: `cd api`, `pip install -r requirements.txt` y `python -m pytest`, sin `api/.env` y sin `pytest.ini` (si el Developer lo necesitara, lo escala al PM).

La fixture cumple todos estos requisitos:

| # | Requisito |
|---|-----------|
| F-1 | **Entorno antes de importar.** En el nivel de módulo de `conftest.py`, antes de cualquier import de `main` o `app.*`, se asignan (asignación directa, **no** `setdefault`, para ignorar valores del shell): `DEBUG=true`; `SECRET_KEY` = constante de prueba de ≥32 caracteres; `DATABASE_URL=sqlite:///<dir>/session.db` con `<dir>` creado con `tempfile.mkdtemp(prefix="granjas-tests-")`, fuera de `api/`, y la ruta en formato POSIX (`Path.as_posix()`). Motivo: `settings` y `engine` se crean al importar y los tests unitarios importan `app.*` a nivel de módulo |
| F-2 | **Guarda.** Fixture de sesión `autouse` que importa `app.core.config` y comprueba que `settings.database_url` es exactamente la URL de F-1; si no, aborta la sesión (`pytest.exit`) con un mensaje claro. Nada de silenciar el desajuste |
| F-3 | **`engine` (por test).** Engine SQLite en `tmp_path/"test.db"` (`tmp_path` de pytest) con `connect_args={"check_same_thread": False}`; crea las tablas con `Base.metadata.create_all` tras importar `app.modules.auth.entities`; hace `engine.dispose()` en el teardown. Los pragmas (`foreign_keys`, WAL) los aplica el listener global de `Engine` |
| F-4 | **`db_session`.** `Session` ligada a `engine` (`autoflush=False`, `expire_on_commit=False`, como `SessionLocal`), cerrada en el teardown. Permite a QA comprobar el estado de la BD (p. ej. que no se creó el usuario) |
| F-5 | **`get_db` sobrescrito.** `app.dependency_overrides[get_db]` apunta a un generador que abre y cierra una sesión del `engine` de F-3; el teardown lo elimina (`pop(get_db, None)`) |
| F-6 | **`client`.** `with TestClient(main.app, raise_server_exceptions=False) as client`. `import main` se hace dentro de la fixture, tras F-1 (ejecuta `bootstrap.ensure_dependencies()`: requiere `requirements.txt` instalado). El lifespan se ejecuta y llama a `init_db()` sobre el engine global, que por F-1 es el temporal de sesión |
| F-7 | **Limpieza de sesión.** Al terminar (`pytest_sessionfinish` o fixture de sesión): `app.core.database.engine.dispose()` si el módulo se importó y `shutil.rmtree(<dir>, ignore_errors=True)` (WAL bloquea el borrado en Windows si no se libera el engine) |
| F-8 | **Sin tocar la configuración local.** No crea, edita ni exige `api/.env`; con un `api/.env` presente, las variables de F-1 prevalecen. No toca `api/data/` |
| F-9 | **Humo.** `api/tests/test_health.py`: `GET /health` → 200 y `{"status": "ok"}` |

Reutilización: `engine`, `db_session` y `client` son las fixtures que usan los tests unitarios (API-001, solo si necesitan BD, normalmente no) y de integración (QA-001).

## 5. Fragmento OpenAPI 3.1
Fuente de verdad: `/openapi.json` generado. Debe coincidir con lo siguiente en lo relevante:

```yaml
paths:
  /api/auth/register:
    post:
      requestBody: { required: true, content: { application/json: { schema: { $ref: "#/components/schemas/UserCreate" } } } }
      responses:
        "201": { content: { application/json: { schema: { $ref: "#/components/schemas/UserRead" } } } }
        "422": { content: { application/json: { schema: { $ref: "#/components/schemas/HTTPValidationError" } } } }
  /api/auth/login:
    post:
      requestBody: { required: true, content: { application/json: { schema: { $ref: "#/components/schemas/LoginRequest" } } } }
      responses:
        "200": { content: { application/json: { schema: { $ref: "#/components/schemas/TokenResponse" } } } }
        "422": { content: { application/json: { schema: { $ref: "#/components/schemas/HTTPValidationError" } } } }
components:
  schemas:
    UserCreate:
      required: [username, email, password]
      properties:
        username: { type: string, minLength: 3, maxLength: 80 }
        email: { type: string, format: email }
        password:
          type: string
          minLength: 8            # sin maxLength: el máximo es en bytes
          description: "<texto que menciona el límite de 72 bytes UTF-8>"
    LoginRequest:
      required: [email, password]
      properties:
        email: { type: string, format: email }
        password: { type: string, minLength: 1, maxLength: 72 }   # sin cambios
```
Los demás esquemas no cambian. Las diferencias frente a lo generado son un defecto.

## 6. Front (Angular)
No aplica: la épica no toca la Web. Nota para el futuro registro Web: medir bytes con `TextEncoder` (no `maxlength`) y tratar `detail[].type == "password_too_long"` (ADR-004).

## 7. Criterios de verificación (para QA)
Notación: **U** = test unitario (Developer, `api/tests/unit/`), **I** = integración (QA, `api/tests/integration/`). `ñ` ocupa 2 bytes y `😀` 4. Comprobar siempre `status_code` y, en los 422, `detail[0].loc == ["body", "password"]`, `detail[0].type` y que `detail[0].msg` contiene "72 bytes"; no se comprueba `ctx` ni el texto exacto del envelope.

### 7.1 US-01 · infraestructura (OPS-001)
- Tras `pip install -r requirements.txt`, `python -m pytest` desde `api/` pasa en verde sin `api/.env` (también con él presente) y `requirements.txt` incluye `pytest>=…` y `httpx>=…`.
- `api/data/app.db` no se crea ni se modifica: comparar existencia y fecha de modificación antes y después; si `api/data/` no existía, sigue sin existir.
- Aislamiento: dos tests consecutivos que registran el mismo email responden ambos 201 (BD limpia por test).
- La guarda F-2 falla ruidosamente si `DATABASE_URL` no es la temporal (revisión del código del conftest).
- `GET /health` → 200 `{"status": "ok"}`.

### 7.2 US-02 · `POST /api/auth/register`
Usuario y email únicos en cada caso.

| ID | Contraseña | Bytes / caracteres | Esperado | Nivel |
|----|-----------|--------------------|----------|-------|
| R-01 | `"ñ" * 40` | 80 / 40 | 422 `password_too_long`; no 500; no se crea usuario | U (esquema), I |
| R-02 | `"a" * 72` | 72 / 72 | 201 | U, I |
| R-03 | `"a" * 73` | 73 / 73 | 422 `password_too_long` (no `string_too_long`) | U, I |
| R-04 | `"ñ" * 36` | 72 / 36 | 201 | U, I |
| R-05 | `"a" * 70 + "ñ"` | 72 / 71 | 201 | U, I |
| R-06 | `"a" * 71 + "ñ"` | 73 / 72 | 422 `password_too_long` (72 caracteres: el antiguo `max_length` la aceptaba) | U, I |
| R-07 | `"ñ" * 37` | 74 / 37 | 422 `password_too_long` | U |
| R-08 | `"😀" * 18` | 72 / 18 | 201 | U, I |
| R-09 | `"😀" * 18 + "a"` | 73 / 19 | 422 `password_too_long` | U, I |
| R-10 | `"ñ" * 8` | 16 / 8 | 201 (el mínimo cuenta caracteres) | U |
| R-11 | `"a" * 7` | 7 / 7 | 422 `string_too_short` | U |
| R-12 | `"ñ" * 10000` | 20000 / 10000 | 422 `password_too_long`; no 500 | I |
| R-13 | tras R-01/R-03/R-06: registrar el mismo email/usuario con `Password123` | — | 201 (no 409): la contraseña rechazada no dejó usuario; comprobable también con `db_session` | I |
| R-14 | `Password123` (regresión) y duplicado de email | 11 / 11 | 201 y luego 409 `conflict` (sin cambios) | I |

### 7.3 US-02 · `POST /api/auth/login`
| ID | Escenario | Esperado | Nivel |
|----|-----------|----------|-------|
| L-01 | Registrar con `"ñ" * 36` (72 bytes) y hacer login con la misma | 200 con `access_token` y `refresh_token` | I |
| L-02 | Usuario existente (registrado con `Password123`), login con `"ñ" * 40` (80 bytes, 40 caracteres) | 401 `error.code == "unauthorized"`, "Credenciales inválidas"; no 500 | I |
| L-03 | Email inexistente, login con `"ñ" * 40` | 401 con el **mismo** cuerpo que L-02 | I |
| L-04 | Registrar con `"ñ" * 36` y login con `"ñ" * 36 + "x"` (73 bytes, 37 caracteres) | 401: no se acepta un prefijo de 72 bytes (sin truncamiento) | I |
| L-05 | Login con `"😀" * 20` (80 bytes, 20 caracteres) | 401; no 500 | I |
| L-06 | Login con `"a" * 73` (73 caracteres) | 422 (`string_too_long`, cota de caracteres vigente); no 500 | I |
| L-07 | `verify_password("ñ" * 40, <hash de "ñ" * 36>)`, `verify_password("ñ" * 36 + "x", <hash de "ñ" * 36>)` y `verify_password("x", "no-es-un-hash")` | `False` en los tres, sin excepción | U |
| L-08 | `LoginRequest(email=..., password="ñ" * 40)` | válido (sin límite en bytes); `password="a" * 73` → error `string_too_long` | U |

### 7.4 Piezas internas (unitarios, API-001)
- `exceeds_password_limit`: `""`, `"a"*72`, `"ñ"*36`, `"😀"*18` → `False`; `"a"*73`, `"ñ"*37`, `"😀"*18 + "a"` → `True`.
- `hash_password("a" * 73)` y `hash_password("ñ" * 40)` lanzan `ValueError`; `hash_password("ñ" * 36)` devuelve un hash bcrypt que `verify_password("ñ" * 36, hash)` acepta.
- `UserCreate(...)` con los casos R-01 a R-11: `ValidationError` con `errors()[0]["type"] == "password_too_long"` y `loc == ("password",)` para R-01, R-03, R-06, R-07 y R-09.

### 7.5 Seguridad y contrato
- Ninguna respuesta de R-xx y L-xx (201, 200, 401, 422) ni `GET /api/auth/me` contiene `hashed_password` ni un hash bcrypt (`$2b$`, `$2a$`) en `response.text`.
- Ningún caso devuelve 500 (`client` con `raise_server_exceptions=False`).
- Los tokens y contraseñas no se copian a los informes (truncar).
- `/openapi.json` cumple §5: `UserCreate.password` con `minLength: 8`, sin `maxLength` y con `description` que menciona "72 bytes"; `LoginRequest.password` con `minLength: 1` y `maxLength: 72`.
- Regresión: `python -m pytest` completo en verde.
- Observaciones no bloqueantes (se anotan como S4): el 422 incluye `input` con la contraseña rechazada (ver §8); el comportamiento ante contraseñas con sustitutos Unicode aislados (`"\ud800"`) en `register`; en `login` debe dar 401, nunca 500.

## 8. Fuera de alcance y preguntas abiertas
- ADR-001 (envelope de los 422). Entrada para ese ADR: el 422 por defecto devuelve `detail[].input` con la contraseña rechazada; debería omitirse para `password`.
- Contraseñas con caracteres no codificables en UTF-8 (sustitutos aislados) en `register`: no se garantiza el 422; solo `login` se garantiza sin 500 (vía `verify_password`).
- Linter, CI, tests de otros endpoints de `auth`, cambios en la Web, rate limiting de `login`, reglas de complejidad de contraseña y migraciones.
- Tras API-001, el PM actualiza el hueco conocido de `AGENTS.md` y el caso conocido de `qa.agent.md` sobre `max_length=72`.
- Preguntas de negocio: ninguna.
