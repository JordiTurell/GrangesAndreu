# Contrato · base-tests-password (EP-01)
**Estado:** aprobado   **Alcance:** API
**Historias:** US-01, US-02, US-03   **Tareas que desbloquea:** OPS-001, OPS-002, API-001, QA-001

> Épica: infraestructura de tests de la API (US-01), rechazo con 422 de las contraseñas de más de 72 bytes UTF-8 (US-02, [ADR-004](adr/ADR-004-password-bytes.md)) y arranque fiable de la API con la configuración documentada en `.env.example` (US-03, §4.3). El comportamiento del módulo `auth` sigue descrito en [auth.md](auth.md), que se actualiza con esta épica; US-03 no afecta a `auth.md`.
>
> Revisión ARQ-002 (2026-11-10): se añaden EP-01-D4 a EP-01-D8 y la sección 4.3; lo aprobado de ADR-004 (§3, §4.1, §7.2 a §7.5) no cambia. EP-01-D4 corrige §4.2 y §7.1 (`httpx` pasa a `httpx2`).

## 1. Decisiones (ADR)
| ID | Decisión | Alternativas | Motivo | Consecuencias |
|----|----------|--------------|--------|---------------|
| [ADR-004](adr/ADR-004-password-bytes.md) (aceptado) | El límite de 72 bytes UTF-8 se valida en el esquema `UserCreate.password` con un helper único en `core/security.py`, con defensa en profundidad en `hash_password` y `verify_password`; `LoginRequest` no valida bytes | Validar en el servicio; capturar `ValueError` de bcrypt; pre-hash; truncar | 422 con el mecanismo vigente, antes de la BD y del hash; independiente de la versión de bcrypt | Cambian `schemas.py` y `core/security.py`; login no cambia de contrato |
| ADR-001 (pendiente) | **No bloquea este contrato:** el 422 usa el formato por defecto de FastAPI (`detail`), declarado en §3 | — | Fuera de alcance de la épica | Si cambia el envelope, se ajustan los tests; `type` y `loc` se conservan |
| EP-01-D1 | La fixture usa un directorio temporal de sesión para el engine **global** (variables de entorno fijadas antes de importar) y una BD SQLite **por test** enlazada con `get_db` sobrescrito | Una sola BD de sesión con limpieza de tablas; sobrescribir solo `get_db` | `settings` y `engine` son singletons creados al importar y el lifespan usa el engine global: sin fijar el entorno antes, se tocaría `api/data/app.db`; la BD por test da aislamiento total | El conftest debe fijar el entorno en el nivel de módulo, antes de cualquier import de `app.*` o `main` |
| EP-01-D2 | `TestClient(..., raise_server_exceptions=False)` | Valor por defecto (propaga excepciones) | Los tests verifican códigos HTTP reales, de modo que un 500 se observa como `status_code == 500` y no como excepción | Los tests deben asertar el código de estado explícitamente |
| EP-01-D3 | Estructura `api/tests/`: `conftest.py` y `test_health.py` (OPS-001); `unit/` (Developer, API-001) e `integration/` (QA, QA-001), cada subcarpeta con `__init__.py` | Ficheros planos | Cada rol escribe en su zona sin colisiones de nombres | La primera tarea que añada tests a una subcarpeta crea su `__init__.py` |
| EP-01-D4 | Cliente HTTP de `TestClient`: `httpx2>=2.0.0` en `requirements.txt` (y **no** `httpx`). Los tests solo importan `fastapi.testclient.TestClient` (reexporta el de Starlette), nunca `httpx` ni `httpx2` | `httpx>=0.27.0` (contrato anterior); declarar `httpx2` y `httpx`; `httpx2` más un tope o piso de `starlette` | Hechos verificados el 2026-11-10: starlette 1.7.0 importa `httpx2` primero; con solo `httpx` emite `StarletteDeprecationWarning` y sin ninguno lanza `RuntimeError`. `httpx2` basta por sí solo (2.16.0 hoy; `>=2.0.0` es el piso de la línea mayor, mismo estilo `>=` que el resto): con él instalado Starlette no cae al respaldo `httpx`, y con starlette 1.7.0 declarar `httpx` añadiría un paquete que solo se usa como respaldo obsoleto. No se fija `starlette`: lo gobierna `fastapi` y el contrato no depende de su versión más allá de que importe `httpx2` | §4.2 y §7.1 actualizados. El piso `2.0.0` solo está verificado con la 2.16.0 instalada; si una versión menor fallara, el Developer sube el piso y lo anota. Un entorno con una starlette anterior a la que adoptó `httpx2` (la que solo admite `httpx`) queda fuera de la épica; el Developer registra las versiones de `starlette`, `fastapi`, `httpx2` y `pytest` en la entrega (riesgo R-06 del plan) |
| EP-01-D5 | `CORS_ORIGINS` acepta lista separada por comas (`.env.example`) y lista JSON (`api/.env` local): `cors_origins: Annotated[list[str], NoDecode]` y el `field_validator(mode="before")` interpreta los dos formatos | Cambiar `.env.example` a JSON; cambiar el `api/.env` del usuario (prohibido); campo `str` más propiedad con otro nombre (`settings.cors_origins` ya lo usa `main.py`); fuente de settings personalizada | pydantic-settings decodifica `list[str]` como JSON **antes** del validador, de modo que la cadena con comas falla con `SettingsError`; `NoDecode` entrega la cadena cruda con el menor cambio y conserva el nombre del atributo | `pydantic-settings>=2.7.0` (§4.3). Cadena vacía = `[]` (ningún origen), no el defecto. JSON inválido aborta el arranque con `ValidationError` |
| EP-01-D6 | `DATABASE_URL` SQLite relativa se resuelve respecto a `api/` (`BASE_DIR`), no al cwd, en una función pura `resolve_database_url`; las absolutas, `:memory:`, las URI `file:` y las no SQLite se dejan idénticas | Respecto al cwd (comportamiento actual); crear `data/` en el cwd; rechazar rutas relativas | `sqlite:///./data/app.db` (valor de `.env.example`) falla con `unable to open database file` si el cwd no es `api/` o no existe `data/`; la ruta relativa debe significar lo mismo desde cualquier directorio | Una URL absoluta conserva la misma cadena, de modo que la guarda F-2 de §4.2 sigue exacta. Sin `expanduser`; `..` permitido (configuración del operador) |
| EP-01-D7 | La validación de `Settings` no tiene efectos laterales: el directorio padre del SQLite se crea en `get_settings()`, solo después de construir `Settings` sin error (`ensure_database_directory`) | Reordenar dentro del `model_validator` (`mkdir` tras comprobar `SECRET_KEY`); crear el directorio en `database.py` antes de `create_engine`; crearlo en `init_db()` (lifespan) | Hoy `_apply_defaults` hace `DATA_DIR.mkdir` antes de validar `SECRET_KEY` y deja `api/data/` vacío tras un arranque fallido; con efecto dentro del validador, cualquier validación futura posterior lo reintroduciría y `Settings(...)` no sería testeable sin disco. Mantenerlo en `config.py` conserva el momento actual (al importar) y un solo fichero de código | Con configuración válida el efecto es el de hoy. `database.py` no cambia. Las pruebas pueden construir `Settings` sin tocar el sistema de ficheros |
| EP-01-D8 | Verificación de OPS-002: se entrega **sin pytest** (la infraestructura nace en OPS-001, posterior) con comandos reproducibles; los unitarios (nivel **U** de §7.6) los escribe el Developer en `api/tests/unit/test_config.py` dentro de **OPS-001**, que pasa a depender de OPS-002; QA verifica por subproceso sobre una copia temporal de `api/` (nivel **S**) | Unitarios dentro de OPS-002 instalando pytest a mano (invade OPS-001); invertir el orden (OPS-001 antes); solo QA | El orden fijado por el PM es OPS-002 → OPS-001; instalar herramientas de test es tarea `OPS`. Las funciones puras de §4.3 permiten unitarios sin app ni BD, y el `settings` real y el `api/.env` del usuario solo intervienen en subprocesos sobre copia | El PM amplía OPS-001 (ficheros, DoD y `depends_on`). QA persiste los casos S como regresión en `api/tests/integration/` durante QA-001. Sin ADR transversal: todas las decisiones son locales a la épica |

## 2. Modelo de datos
Sin cambios (tabla `users` en [auth.md](auth.md) §2). Migración: ninguna. Los hashes existentes no se modifican.

## 3. API
Solo cambian las respuestas descritas abajo; el resto de endpoints de `auth` no cambia. OPS-002 (§4.3) no cambia ningún endpoint ni el OpenAPI: solo cómo se leen `CORS_ORIGINS` y `DATABASE_URL`.

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
Ficheros: `api/requirements.txt` (añadir `pytest>=8.0.0` y `httpx2>=2.0.0`, mismo estilo `>=`; **no** `httpx`, EP-01-D4), `api/tests/__init__.py`, `api/tests/conftest.py`, `api/tests/test_health.py` y, por EP-01-D8, `api/tests/unit/__init__.py` y `api/tests/unit/test_config.py` (F-10). Ejecución: `cd api`, `pip install -r requirements.txt` y `python -m pytest`, sin `api/.env` y sin `pytest.ini` (si el Developer lo necesitara, lo escala al PM).

La fixture cumple todos estos requisitos:

| # | Requisito |
|---|-----------|
| F-1 | **Entorno antes de importar.** En el nivel de módulo de `conftest.py`, antes de cualquier import de `main` o `app.*`, se asignan (asignación directa, **no** `setdefault`, para ignorar valores del shell): `DEBUG=true`; `SECRET_KEY` = constante de prueba de ≥32 caracteres; `DATABASE_URL=sqlite:///<dir>/session.db` con `<dir>` creado con `tempfile.mkdtemp(prefix="granjas-tests-")`, fuera de `api/`, y la ruta en formato POSIX (`Path.as_posix()`). Motivo: `settings` y `engine` se crean al importar y los tests unitarios importan `app.*` a nivel de módulo |
| F-2 | **Guarda.** Fixture de sesión `autouse` que importa `app.core.config` y comprueba que `settings.database_url` es exactamente la URL de F-1; si no, aborta la sesión (`pytest.exit`) con un mensaje claro. Nada de silenciar el desajuste |
| F-3 | **`engine` (por test).** Engine SQLite en `tmp_path/"test.db"` (`tmp_path` de pytest) con `connect_args={"check_same_thread": False}`; crea las tablas con `Base.metadata.create_all` tras importar `app.modules.auth.entities`; hace `engine.dispose()` en el teardown. Los pragmas (`foreign_keys`, WAL) los aplica el listener global de `Engine` |
| F-4 | **`db_session`.** `Session` ligada a `engine` (`autoflush=False`, `expire_on_commit=False`, como `SessionLocal`), cerrada en el teardown. Permite a QA comprobar el estado de la BD (p. ej. que no se creó el usuario) |
| F-5 | **`get_db` sobrescrito.** `app.dependency_overrides[get_db]` apunta a un generador que abre y cierra una sesión del `engine` de F-3; el teardown lo elimina (`pop(get_db, None)`) |
| F-6 | **`client`.** Dentro de la fixture, tras F-1 y en este orden: `import main` (ejecuta `bootstrap.ensure_dependencies()`: requiere `requirements.txt` instalado), `from fastapi.testclient import TestClient` (import perezoso: los tests que no usan `client` no necesitan el cliente HTTP) y `with TestClient(main.app, raise_server_exceptions=False) as client`. Ningún fichero de `api/tests/` importa `httpx` ni `httpx2` (EP-01-D4). El lifespan se ejecuta y llama a `init_db()` sobre el engine global, que por F-1 es el temporal de sesión |
| F-7 | **Limpieza de sesión.** Al terminar (`pytest_sessionfinish` o fixture de sesión): `app.core.database.engine.dispose()` si el módulo se importó y `shutil.rmtree(<dir>, ignore_errors=True)` (WAL bloquea el borrado en Windows si no se libera el engine) |
| F-8 | **Sin tocar la configuración local.** No crea, edita ni exige `api/.env`; con un `api/.env` presente, las variables de F-1 prevalecen. No toca `api/data/` |
| F-9 | **Humo.** `api/tests/test_health.py`: `GET /health` → 200 y `{"status": "ok"}` |
| F-10 | **Unitarios de configuración.** `api/tests/unit/test_config.py` (con `unit/__init__.py`) implementa los casos de nivel **U** de §7.6 sobre las piezas de §4.3. Importa `app.core.config` a nivel de módulo (seguro por F-1: el `settings` ya apunta a la BD temporal), construye `Settings(_env_file=None)` con `monkeypatch` y no usa `client`, `engine` ni BD |

Reutilización: `engine`, `db_session` y `client` son las fixtures que usan los tests unitarios (API-001, solo si necesitan BD, normalmente no) y de integración (QA-001).

### 4.3 Configuración de arranque (US-03 · OPS-002)
Ficheros: `api/app/core/config.py` y `api/requirements.txt` (solo subir `pydantic-settings` a `>=2.7.0`, versión en la que se introdujo `NoDecode`; el Developer lo contrasta con el changelog del paquete y, si fuera otra, usa esa y lo anota en la entrega; verificado con 2.15.0). **No cambian** `api/app/core/database.py` (crea el engine con `settings.database_url` ya resuelta y `_is_sqlite` sigue valiendo), `api/main.py`, `api/.env.example`, `api/.env`, `api/data/` ni ningún endpoint. `bootstrap.ensure_dependencies()` solo comprueba presencia, no versión: el nuevo piso afecta a instalaciones nuevas y un entorno con una versión anterior fallaría con `ImportError` de `NoDecode`.

**Piezas de `config.py`** (nombres y firmas contractuales; el cuerpo es del Developer):

| Pieza | Contrato |
|-------|----------|
| `Settings.cors_origins` | `Annotated[list[str], NoDecode]`, mismo nombre y defecto `["http://localhost:4200"]`. `NoDecode` impide la decodificación JSON previa de pydantic-settings tanto en variables de entorno como en `.env` |
| `parse_cors_origins(value: object) -> object` | Pura. Reglas CORS-1 a CORS-5. El `field_validator("cors_origins", mode="before")` solo delega en ella |
| `sqlite_file_database(url: str) -> str \| None` | Pura. Devuelve la parte `database` de la URL solo si es un **fichero SQLite** (regla DB-1); `None` en cualquier otro caso. La comparten `resolve_database_url` y `ensure_database_directory` para clasificar igual |
| `resolve_database_url(url: str, base_dir: Path = BASE_DIR) -> str` | Pura (ni toca el disco ni depende del cwd). Reglas DB-2 a DB-4. `base_dir` es parámetro para poder probarla con `tmp_path` |
| `Settings._apply_defaults` | `model_validator(mode="after")` **sin efectos laterales**: si `database_url` está vacía usa `sqlite:///{(DATA_DIR / 'app.db').as_posix()}` (la misma cadena de hoy); después `database_url = resolve_database_url(database_url)`. La comprobación de `SECRET_KEY` (mensaje `SECRET_KEY es obligatoria fuera de modo debug...`) y la clave efímera con `RuntimeWarning` en debug quedan como hoy. Ya no llama a `mkdir` |
| `ensure_database_directory(database_url: str) -> None` | Si `sqlite_file_database(database_url)` no es `None`, crea `Path(database).parent` con `parents=True, exist_ok=True`; si es `None`, no hace nada. No crea ni abre el fichero `.db`. Idempotente |
| `get_settings()` (`lru_cache`) | `s = Settings()`; `ensure_database_directory(s.database_url)`; `return s`. Es el **único** punto con efecto en disco y solo se alcanza si `Settings()` no lanzó |

**`CORS_ORIGINS`** (entrada = valor crudo de la variable o de `.env`):
- CORS-1 Solo se interpretan cadenas. Otro valor (p. ej. `Settings(cors_origins=[...])`) pasa sin cambios a la validación de `list[str]`.
- CORS-2 Se recorta la cadena (`strip`). Vacía → `[]`: la variable presente y vacía significa "ningún origen"; el defecto solo se aplica si la variable no existe.
- CORS-3 Si empieza por `[` es una lista JSON (`json.loads`). JSON inválido → `ValueError("CORS_ORIGINS no es una lista JSON válida")` sin incluir el valor en el texto; pydantic lo informa como `ValidationError` del campo `cors_origins` y el arranque aborta. Los elementos que no sean `str` los rechaza la validación de `list[str]`. Los elementos de una lista JSON no se recortan.
- CORS-4 En otro caso es una lista separada por comas: se parte por `,`, se recorta cada elemento y se descartan los vacíos.
- CORS-5 No se normaliza ni se valida cada origen (barra final, mayúsculas, `*`, esquema): se pasan tal cual a `CORSMiddleware`, como hoy.

**`DATABASE_URL`:**
- DB-1 `sqlite_file_database` devuelve `url.database` (con `sqlalchemy.engine.make_url`) solo si el backend es `sqlite` y `database` no es `None`, `""` ni `":memory:"` y no empieza por `file:` (forma URI). Si `make_url` no puede parsear la cadena (`ArgumentError`) devuelve `None` y **no** lanza: el fallo sigue ocurriendo en `create_engine`, como hoy, sin un camino de error nuevo.
- DB-2 Ruta **absoluta** (`Path(database).is_absolute()` o empieza por `/` o `\`): `resolve_database_url` devuelve la **misma cadena** de entrada, sin volver a renderizarla (así `sqlite:///C:/…` o `sqlite:////tmp/…` y la URL de F-1 quedan idénticas).
- DB-3 Ruta **relativa**: `abs = (base_dir / database).resolve()` (no exige que exista; sin `expanduser`; `..` permitido). La URL devuelta es la misma con `database` sustituida por `abs.as_posix()`, conservando driver y parámetros de consulta (`render_as_string(hide_password=False)`). El resultado no depende del cwd.
- DB-4 Sin fichero SQLite (no SQLite, `:memory:`, `sqlite://`, URI `file:` o no parseable): se devuelve la misma cadena y no se crea ningún directorio.
- DB-5 Vacía: se aplica el defecto de `_apply_defaults` (ruta absoluta bajo `DATA_DIR`), que pasa por DB-2.
- DB-6 Ningún texto de excepción o aviso nuevo incluye valores de variables (una URL puede llevar credenciales).

**Efectos y compatibilidad:**
- FX-A `Settings()` y las funciones puras no crean directorios ni ficheros.
- FX-B El único `mkdir` es `ensure_database_directory`, llamado solo desde `get_settings()` tras construir `Settings` sin error. Cualquier fallo de configuración (`SECRET_KEY` ausente con `DEBUG=false`, JSON de CORS inválido, `PORT` no numérico…) deja el sistema de ficheros intacto: ni `api/data/` ni otro directorio ni fichero.
- FX-C Con variables ya válidas el comportamiento no cambia: mismos defectos y avisos, `api/data/` se crea como hoy con `DATABASE_URL` vacía y las URL absolutas conservan la misma cadena. El `api/.env` local con `CORS_ORIGINS` en JSON sigue funcionando y `.env.example` (comas, `sqlite:///./data/app.db`) pasa a funcionar sin editarlo.
- FX-D `settings = get_settings()` sigue evaluándose al importar `app.core.config`, así que importar el módulo puede crear el directorio del SQLite (de ahí F-1).

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
Los demás esquemas no cambian. Las diferencias frente a lo generado son un defecto. US-03 (OPS-002) no modifica el OpenAPI.

## 6. Front (Angular)
No aplica: la épica no toca la Web (tampoco el origen CORS: el Front sigue en `http://localhost:4200`). Nota para el futuro registro Web: medir bytes con `TextEncoder` (no `maxlength`) y tratar `detail[].type == "password_too_long"` (ADR-004).

## 7. Criterios de verificación (para QA)
Notación: **U** = test unitario (Developer, `api/tests/unit/`), **I** = integración (QA, `api/tests/integration/`). `ñ` ocupa 2 bytes y `😀` 4. Comprobar siempre `status_code` y, en los 422, `detail[0].loc == ["body", "password"]`, `detail[0].type` y que `detail[0].msg` contiene "72 bytes"; no se comprueba `ctx` ni el texto exacto del envelope.

### 7.1 US-01 · infraestructura (OPS-001)
- Tras `pip install -r requirements.txt`, `python -m pytest` desde `api/` pasa en verde sin `api/.env` (también con él presente). `requirements.txt` incluye `pytest>=…` y `httpx2>=2.0.0` y **no** incluye `httpx` (EP-01-D4).
- Sin avisos de obsolescencia del cliente: la salida de `python -m pytest` no contiene `StarletteDeprecationWarning` ni el `RuntimeError` de `starlette.testclient`; `python -c "import httpx2"` funciona; ningún fichero de `api/tests/` importa `httpx` ni `httpx2` (búsqueda de texto).
- `entrega-OPS-001.md` registra las versiones instaladas de `starlette`, `fastapi`, `httpx2` y `pytest` (riesgo R-06 del plan).
- Los unitarios de configuración de §7.6.1 (`api/tests/unit/test_config.py`) pasan en verde.
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

### 7.6 US-03 · arranque con la configuración documentada (OPS-002)
Niveles: **U** = unitario (Developer, `api/tests/unit/test_config.py`, entregado en OPS-001; EP-01-D8), **S** = subproceso sobre copia temporal de `api/` (QA). Ningún caso lee ni modifica `api/.env` ni `api/data/app.db`.

#### 7.6.1 Unitarios (U)
Las piezas son las de §4.3; `Settings` se construye con `Settings(_env_file=None)`. Cada caso parte de un entorno limpio: `monkeypatch.delenv(..., raising=False)` de `DATABASE_URL`, `CORS_ORIGINS`, `DEBUG` y `SECRET_KEY` (el conftest de F-1 fija tres de ellas) y fija solo lo que el caso indica; salvo que diga otra cosa, `DEBUG=true` y una `SECRET_KEY` válida. `base_dir` = `tmp_path`.

| ID | Entrada | Esperado | Nivel |
|----|---------|----------|-------|
| CO-01 | `CORS_ORIGINS` ausente | `["http://localhost:4200"]` | U, S |
| CO-02 | `http://localhost:4200` (formato de `.env.example`) | `["http://localhost:4200"]` | U, S |
| CO-03 | `http://a:4200,http://b:4200` | `["http://a:4200", "http://b:4200"]` | U |
| CO-04 | `" http://a:4200 , http://b:4200 ,, "` | las dos URL, sin espacios ni elementos vacíos | U |
| CO-05 | `["http://localhost:4200"]` (formato JSON del `api/.env` local) | `["http://localhost:4200"]` | U, S |
| CO-06 | `[ "http://a:4200" , "http://b:4200" ]` | las dos URL | U |
| CO-07 | `""`, `"   "`, `","` y `"[]"` | `[]` | U |
| CO-08 | `["http://a:4200"` (JSON roto) | `ValidationError` sobre `cors_origins` cuyo `errors()[0]["msg"]` termina en "CORS_ORIGINS no es una lista JSON válida" | U, S |
| CO-09 | `[1, 2]` | `ValidationError` (elementos no `str`) | U |
| CO-10 | `parse_cors_origins(["http://a"])` (ya es lista) | la misma lista | U |
| DB-01 | `Settings` sin `DATABASE_URL` (el defecto se aplica en `_apply_defaults`, antes de `resolve_database_url`) | `database_url == "sqlite:///" + (DATA_DIR / "app.db").as_posix()`, igual que hoy | U |
| DB-02 | `sqlite:///./data/app.db` | `sqlite:///<base>/data/app.db` (ruta absoluta POSIX) | U, S |
| DB-03 | `sqlite:///data/app.db`, `sqlite:///app.db` y `sqlite:///./a/b/../c/app.db` | bajo `<base>`; el último normalizado a `<base>/a/c/app.db` | U |
| DB-04 | los casos DB-02 y DB-03 con `monkeypatch.chdir(<otro dir>)` | resultado idéntico al de DB-02 y DB-03 (no depende del cwd) | U, S |
| DB-05 | URL absoluta (`sqlite:///<tmp>/x/app.db`; en Windows con unidad) | **la misma cadena** exacta | U, S |
| DB-06 | `sqlite://`, `sqlite:///:memory:`, `sqlite:///file:x?mode=memory&uri=true` | la misma cadena | U |
| DB-07 | `postgresql+psycopg://u:p@h/db` | la misma cadena | U |
| DB-08 | `sqlite:///./data/app.db?timeout=30` | ruta absoluta conservando `?timeout=30` | U |
| DB-09 | `no-es-una-url` | la misma cadena; no lanza | U |
| DB-10 | `ensure_database_directory` con la URL resuelta de `sqlite:///./deep/er/app.db` | crea `<base>/deep/er`; no crea `app.db`; una segunda llamada no falla | U |
| DB-11 | `ensure_database_directory` con DB-06, DB-07 y DB-09 | no crea nada (`tmp_path` sigue vacío) | U |
| FX-01 | `Settings(_env_file=None)` con `DEBUG=false`, sin `SECRET_KEY`, `DATABASE_URL` vacía y `config.DATA_DIR` apuntando a `tmp_path / "data"` (`monkeypatch.setattr`) | `ValidationError` con "SECRET_KEY es obligatoria"; `tmp_path / "data"` no existe | U |
| FX-02 | el mismo `Settings` pero válido (`DEBUG=true`) | no crea `tmp_path / "data"` (la validación es pura) | U |
| FX-03 | `DEBUG=true` sin `SECRET_KEY` | `RuntimeWarning` y clave generada no vacía (sin cambios) | U |

#### 7.6.2 Subproceso sobre copia temporal (S, QA)
Preparación común:
- Copia de `api/` con `shutil.copytree(..., ignore=shutil.ignore_patterns(".env", "data", "__pycache__", ".pytest_cache", "tests", ".venv"))`: la copia no contiene `.env` ni `data/`, y el `api/.env` real no se abre. Los `.env` de estos casos se crean **en la copia** (p. ej. `.env.example` copiado como `.env`).
- Subproceso `[sys.executable, "-c", <script>]` con `cwd` = un directorio temporal vacío distinto de la copia, `PYTHONPATH=<copia>` y un entorno derivado de `os.environ` sin ninguna variable que sea campo de `Settings` (`DEBUG`, `SECRET_KEY`, `DATABASE_URL`, `CORS_ORIGINS`, `HOST`, `PORT`, `APP_NAME`, `API_PREFIX`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`), añadiendo solo las que cada caso indique.
- El script importa `app.core.config` (y `app.core.database` + `init_db()` donde se indica), no `main`: así no se ejecuta `bootstrap`/pip. Se imprime `cors_origins` y `database_url`, nunca `secret_key`.
- Tras cada caso se comprueba el código de salida, la salida de error y el contenido de la copia y del `cwd`.

| ID | Escenario | Esperado |
|----|-----------|----------|
| ST-01 | `.env` en la copia = `.env.example` (comas, `DATABASE_URL=sqlite:///./data/app.db`, `DEBUG=true`, `SECRET_KEY` vacía); script con `init_db()` | salida 0; `cors_origins == ["http://localhost:4200"]` (CO-02); `database_url == "sqlite:///<copia>/data/app.db"` (DB-02, DB-04); existen `<copia>/data/` y `app.db`; el `cwd` sigue vacío |
| ST-02 | `.env` en la copia con `CORS_ORIGINS=["http://a:4200","http://b:4200"]` y resto válido | salida 0; dos orígenes (CO-05) |
| ST-03 | Lo mismo que ST-01 y ST-02 pasando `CORS_ORIGINS` como variable de entorno y sin `.env` | mismo resultado que desde `.env` (CO-02, CO-05): el origen de la variable no cambia el parseo |
| ST-04 | Sin `.env`, `DEBUG=false`, sin `SECRET_KEY`, `DATABASE_URL` vacía | salida ≠ 0; el error contiene "SECRET_KEY es obligatoria"; **no existe** `<copia>/data/` |
| ST-05 | Como ST-04 con `DATABASE_URL=sqlite:///./sub/dir/app.db` | salida ≠ 0; no existe `<copia>/sub`; `cwd` vacío |
| ST-06 | `DEBUG=true`, `CORS_ORIGINS=["x"` (JSON roto) y `DATABASE_URL` relativa | salida ≠ 0 (CO-08); no se crea ningún directorio (ni `<copia>/data/` ni el de la ruta relativa) |
| ST-07 | `DEBUG=true`, `DATABASE_URL=sqlite:///./deep/er/app.db`, `cwd` ≠ copia; script con `init_db()` | salida 0; existen `<copia>/deep/er/app.db`; el `cwd` sigue vacío (DB-04, DB-10) |
| ST-08 | `DATABASE_URL` absoluta en otro directorio temporal (`sqlite:///<tmp>/abs/dir/app.db`) | `database_url` idéntica a la entrada (DB-05); se crea `<tmp>/abs/dir`; no existe `<copia>/data/` |
| ST-09 | `DATABASE_URL=sqlite:///:memory:` y otro caso con `postgresql+psycopg://u:p@localhost/db` (solo `import app.core.config`) | salida 0; `database_url` idéntica; no existe `<copia>/data/` |
| ST-10 | Regresión con variables válidas (script con `-W error::RuntimeWarning`): `DEBUG=true`, `SECRET_KEY` de 40 caracteres, `DATABASE_URL` absoluta temporal, `CORS_ORIGINS` JSON | salida 0 (no se genera clave efímera, así que no hay `RuntimeWarning`); `secret_key` sin cambios; `database_url` y `cors_origins` como en la entrada |

#### 7.6.3 Responsabilidades y comprobaciones finales
- **Developer (OPS-002):** implementa §4.3 sin ficheros de test. En `entrega-OPS-002.md` incluye la salida (truncada) de ST-01, ST-02, ST-04 y ST-07 ejecutados con un script de usar y tirar fuera del repo (solo biblioteca estándar) y declara que los unitarios llegan con OPS-001. Registra las versiones de `pydantic-settings` y `sqlalchemy` usadas.
- **Developer (OPS-001):** `api/tests/unit/test_config.py` con los casos U de §7.6.1.
- **QA (OPS-002):** ejecuta todos los ST-xx con un script de usar y tirar fuera del repo (pytest aún no existe) y comprueba que `git status --porcelain -- api` solo muestra `api/app/core/config.py` y `api/requirements.txt` modificados. Antes y después comprueba que `api/data/app.db` conserva existencia y fecha de modificación.
- **QA (QA-001):** persiste los ST-xx como regresión en `api/tests/integration/test_config_startup.py` (stdlib más `pytest`, sin `client` ni BD temporal de la fixture).
- **PM (cierre de la épica):** con el `api/.env` real sin tocar, desde `api/`: `python -c "from app.core.config import settings as s; print(type(s.cors_origins).__name__, len(s.cors_origins), s.database_url.startswith('sqlite'))"` termina con código 0 e imprime `list <n> True` (no imprime `secret_key`); `api/data/app.db` conserva su fecha de modificación.

## 8. Fuera de alcance y preguntas abiertas
- ADR-001 (envelope de los 422). Entrada para ese ADR: el 422 por defecto devuelve `detail[].input` con la contraseña rechazada; debería omitirse para `password`.
- Contraseñas con caracteres no codificables en UTF-8 (sustitutos aislados) en `register`: no se garantiza el 422; solo `login` se garantiza sin 500 (vía `verify_password`).
- Linter, CI, tests de otros endpoints de `auth`, cambios en la Web, rate limiting de `login`, reglas de complejidad de contraseña y migraciones.
- Fuera de alcance de US-03: validar o normalizar cada origen CORS (barra final, `*` junto con `allow_credentials=True`), soporte de URI `file:` o de rutas relativas en otros motores, preparar el almacenamiento de motores no SQLite, fijar versiones exactas de dependencias (backlog, riesgo R-06 del plan) y cambiar el comportamiento de `DEBUG` o `SECRET_KEY`.
- Tras API-001, el PM actualiza el hueco conocido de `AGENTS.md` y el caso conocido de `qa.agent.md` sobre `max_length=72`.
- Observación para ADR-001 / backlog: cuando la configuración es inválida, el `ValidationError` de pydantic puede mostrar `input_value` con el contenido de las variables leídas (incluidas credenciales de `DATABASE_URL` o `SECRET_KEY`); candidato `hide_input_in_errors=True` en `model_config`. No se hace aquí para no cambiar el formato de error existente.
- Supuestos de OPS-002: `api/.env.example` **no cambia** (si el PM quiere documentar en él los dos formatos de `CORS_ORIGINS`, es un cambio de comentarios sin efecto funcional y decisión suya); el `api/.env` local usa `CORS_ORIGINS` en JSON y no se lee en ninguna prueba; el SQLite local `api/data/app.db` ya existe y su ruta no cambia.
- Impacto en el plan (para el PM, que es quien edita `tasks/`): (1) criterio de US-01 y descripción de OPS-001: `httpx` → `httpx2`; (2) OPS-001: añadir `api/tests/unit/__init__.py` y `api/tests/unit/test_config.py`, `depends_on` OPS-002 y un punto de DoD (unitarios de §7.6.1 en verde); (3) OPS-002: añadir `api/requirements.txt` a `files` y precisar "sin tests; entrega con ST-01, ST-02, ST-04 y ST-07"; (4) QA-001: añadir los ST-xx de regresión en `api/tests/integration/`; (5) riesgo R-06 del plan: indicar `httpx2`.
- Preguntas de negocio: ninguna.
