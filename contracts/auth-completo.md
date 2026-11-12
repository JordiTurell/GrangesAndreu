# Contrato · auth-completo (EP-02)
**Estado:** aprobado (API y Front, revisado por el PM el 2026-11-11; el cambio del 422 está marcado como **ADR-001/API-005** en §3, §5 y §7)   **Alcance:** Ambos (API: diseño de ARQ-003; Front: diseño de ARQ-004)
**Historias:** US-01, US-02, US-03, US-04   **Tareas que desbloquea:** OPS-003, API-002, API-004, API-003, API-005, QA-003 (la "QA de API" de §9), WEB-001 a WEB-004 y QA-002 (§9.1)

> Épica: recuperación de contraseña (forgot/reset) en modo desarrollo, roles globales `admin` y `user`, primer administrador por variables de entorno y cambio de esquema de `users` sin perder datos. El comportamiento ya implementado del módulo sigue en [auth.md](auth.md), que enlaza aquí. Todo lo de este documento es **objetivo** hasta que las tareas indicadas lo implementen; las diferencias del `/openapi.json` generado frente a §5 son un defecto.
>
> Decisiones ya tomadas por el usuario (requisitos, no se reabren): enlace de reseteo solo en el log en desarrollo y SMTP real en backlog; token de 30 minutos y de un solo uso; registro directo sin verificación de email; dos roles globales (`admin`, `user`), registro público siempre `user` y sin elegir rol; primer admin por variables de entorno; ADR-007 reducido a esos dos roles; esquema de `users` conservando los datos; el diseño Angular es de ARQ-004.

## 1. Decisiones (ADR)
| ID | Decisión | Alternativas | Motivo | Consecuencias |
|----|----------|--------------|--------|---------------|
| [ADR-003](adr/ADR-003-refresh-tokens.md) (aceptado) | Revocación **global** por usuario con `users.token_version` (claim `tv` en access y refresh); `reset-password` la incrementa. Sin rotación por uso ni lista de revocación por `jti` | Aceptar la limitación stateless; tabla de `jti` con rotación y detección de reutilización | Un reseteo existe para recuperar una cuenta comprometida: dejar vivos refresh tokens de 7 días lo anularía; un entero cuesta una columna y un claim, y es determinista de probar | Columna nueva (OPS-003), claim `tv` y comprobación en `get_current_user` y `refresh`; el refresh anterior **sigue válido** tras un `refresh` normal (limitación aceptada, backlog) |
| [ADR-005](adr/ADR-005-migraciones.md) (aceptado) | Migraciones mínimas propias: módulo `core/migrations.py` con pasos aditivos e **idempotentes por inspección del esquema**, ejecutados tras `create_all` en `init_db()` | Alembic; borrar o recrear la BD (descartado) | Un único cambio aditivo, SQLite admite `ADD COLUMN ... NOT NULL DEFAULT` y conserva las filas; evita dependencia, `alembic.ini`, línea base con `stamp` y `fileConfig` que silencia loggers | Criterios de paso a Alembic en el ADR; OPS-003 |
| [ADR-007](adr/ADR-007-roles.md) (aceptado, reducido) | Roles globales `admin` y `user` en `users.role` (cadena + `CHECK`), sin jerarquía implícita; el rol **no** va en el JWT; dependencia `require_role(*roles)` con 403 `forbidden` | Rol en el JWT; tabla de roles; enum nativo | El rol puede cambiar en la vida del token (30 min / 7 días) y `get_current_user` ya lee al usuario en cada petición | Ámbito por granja y roles de granja quedan fuera (nuevo ADR cuando se necesiten) |
| [ADR-011](adr/ADR-011-recuperacion-password.md) (aceptado) | Reseteo con token aleatorio hasheado (SHA-256), 30 min, un solo uso, el último pedido invalida los anteriores; enlace solo en log y solo con `DEBUG=true`; respuesta uniforme con trabajo en segundo plano; rate limiting en backlog | Token JWT firmado; bcrypt del token; enviar siempre; rate limiting ahora | Ver ADR | Entidad `password_reset_tokens`, `shared/mail.py`, 2 endpoints |
| [ADR-001](adr/ADR-001-errores-validacion.md) (aceptado, ARQ-004) | Handler propio del 422 con envelope `{"error": {"code": "validation_error", "message", "fields"}}`, sin `input` ni 500 con sustitutos Unicode; **cambia el formato del 422 de este contrato** (implementa API-005, después de API-003) | Mantener `detail` y normalizar solo en el Front; ambas formas | El Front no puede quitar de la respuesta la contraseña o el token que la API devuelve en `input`; cierra BUG-004 | §3 y §5 (marcados), §6.6, §7.8 |
| [ADR-002](adr/ADR-002-tokens-front.md) (aceptado, ARQ-004) | Access en memoria; refresh en `localStorage` (Recordarme) o `sessionStorage`; restauración con `/refresh` y `/me`; 401 «Token revocado» limpia la sesión | Todo en memoria o `localStorage`; cookies `HttpOnly` con BFF (evolución) | Ver ADR; la API no cambia | §6.5 |
| [ADR-006](adr/ADR-006-rendermode.md) (aceptado, ARQ-004) | `Prerender` solo para `login`, `register` y `forgot-password`; `reset-password` (token en la URL) y el resto en `Client` | Prerender global; Server | Privado por defecto; el token nunca se renderiza | §6.4 |
| EP-02-D1 | El rol **no** va en el JWT; `/me` y `UserRead` lo devuelven | Claim `role` | Un claim queda obsoleto si el rol cambia; leerlo de la BD no cuesta nada (se carga el usuario en cada petición) y no hay riesgo de confiar en un dato caducado | El Front obtiene el rol de `/me` tras el login; la autorización real es siempre de la API |
| EP-02-D2 | `register` **ignora** cualquier campo `role` del body (comportamiento por defecto de Pydantic, `UserCreate` no tiene el campo) y el servicio fija `role = user` | Rechazar con 422 (`extra="forbid"`) | La propiedad de seguridad es estructural (no hay campo ni lectura del rol); no rompe clientes que envíen campos de más ni cambia el contrato de `register`; el 201 muestra `role: "user"` | QA verifica body con `role: "admin"` → 201 con `user`, y que `UserCreate` y su OpenAPI no tienen `role` |
| EP-02-D3 | Primer admin por variables `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_USERNAME` e `INITIAL_ADMIN_PASSWORD` (§4.1) | Endpoint de alta; script aparte | Decisión del usuario; sin secretos en el repo | `hide_input_in_errors=True` en `Settings` para que la contraseña no salga en errores de configuración |
| EP-02-D4 | `forgot-password` responde 202 de inmediato y el trabajo (buscar usuario, token, envío) va a `BackgroundTasks` con una sesión propia sobre el **mismo `bind`** que la sesión de la petición (`db.get_bind()`) | Trabajo síncrono con una rama «falsa» para emails inexistentes | El tiempo de respuesta no depende de si el email existe (sin enumeración por tiempo); usar el `bind` de `get_db` hace que la fixture de tests (que solo sobrescribe `get_db`) vea las filas | §3 y §4.4 |
| EP-02-D5 | Errores del token de reseteo: 400 `invalid_token` (no existe, ya usado o sustituido, o usuario inactivo) y 400 `expired_token` | 404/410; un único código | El token es un secreto de 256 bits: distinguir caducado de inválido no filtra información útil y mejora el mensaje al usuario | `shared/exceptions.py` |
| EP-02-D6 | Rate limiting de `login` y `forgot-password`: **backlog** (ADR-011), condición previa a cualquier despliegue no local | Implementarlo ahora (en memoria o `slowapi`) | No hay envío real de correo en esta épica; bcrypt frena el login; la solución depende de proxies, workers y almacenamiento aún no decididos | Riesgo R-05 aceptado para uso local |

## 2. Modelo de datos
### 2.1 `users` (columnas nuevas; las demás no cambian, ver [auth.md](auth.md) §2)
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `role` | String(10) | NOT NULL, `server_default 'user'`, `default` Python `UserRole.USER.value`, `CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))`. Sin índice (dos valores) |
| `token_version` | Integer | NOT NULL, `server_default 0`, `default` Python `0`. Interno: nunca se serializa |

- `UserRole` es un `enum.StrEnum` (`ADMIN = "admin"`, `USER = "user"`) definido en `modules/auth/entities.py`. La columna es una cadena con `CHECK`, no un `Enum` de SQLAlchemy: el DDL de la entidad y el del `ALTER TABLE` de la migración quedan idénticos.
- DDL de la entidad: `server_default=text("'user'")` y `server_default=text("0")` (no cadenas, para que `PRAGMA table_info` dé `'user'` y `0` en ambas rutas) y `CheckConstraint("role IN ('admin', 'user')", name="ck_users_role")` en `__table_args__`.
- **Migración:** alteración (columnas aditivas). Estrategia de ADR-005 en §2.3. Los usuarios existentes quedan con `role = 'user'` y `token_version = 0` por el `DEFAULT` del `ALTER`.

### 2.2 `password_reset_tokens` (tabla nueva, la crea `create_all`)
| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | Integer | PK, autoincremental |
| `user_id` | Integer | NOT NULL, FK `users.id` `ondelete=CASCADE`, índice |
| `token_hash` | String(64) | NOT NULL, **único** (índice de búsqueda): SHA-256 en hexadecimal del token |
| `created_at` | DateTime(timezone=True) | NOT NULL, por defecto la hora UTC actual |
| `expires_at` | DateTime(timezone=True) | NOT NULL, `created_at + PASSWORD_RESET_EXPIRE_MINUTES` (30) |
| `used_at` | DateTime(timezone=True) | NULL; se rellena al consumir el token |

- Entidad `PasswordResetToken` en `modules/auth/entities.py` (`init_db()` ya importa ese módulo, así que `database.py` no cambia por esta tabla). Relación a `User` sin `backref` obligatorio.
- Invariante: **como máximo una fila por usuario** (cada solicitud borra las anteriores del usuario antes de insertar; ver §3). Sin crecimiento sin límite aunque no haya rate limiting.
- Se guarda el **hash**, nunca el token. El token (`secrets.token_urlsafe(32)`, 256 bits, 43 caracteres) solo existe en memoria y en el enlace del log de desarrollo.
- SQLite devuelve `DateTime(timezone=True)` **sin zona**: al comparar fechas leídas de la BD se tratan como UTC (`dt.replace(tzinfo=timezone.utc)` si `tzinfo is None`). Las comparaciones dentro de SQL (`UPDATE ... WHERE expires_at > :now`) usan `datetime.now(timezone.utc)`, igual que el resto de columnas.

### 2.3 Estrategia de cambio de esquema (ADR-005) y tarea OPS-003
- Fichero nuevo `api/app/core/migrations.py` con `run_migrations(engine: Engine) -> None` y la tupla ordenada `MIGRATIONS` de funciones `(connection) -> None`:
  1. `_add_users_role`: si existe la tabla `users` y no tiene `role` → `ALTER TABLE users ADD COLUMN role VARCHAR(10) NOT NULL DEFAULT 'user' CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))`.
  2. `_add_users_token_version`: si falta `token_version` → `ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0`.
- Cada paso **inspecciona el esquema** (`sqlalchemy.inspect(connection)`) y no hace nada si la columna ya existe: una BD nueva (que `create_all` ya crea con las columnas de la entidad) y una BD anterior pasan por el mismo código. Sin tabla de versiones. Si la tabla `users` no existe, el paso no hace nada.
- Carrera entre procesos (dos workers arrancando): si el `ALTER` falla con `OperationalError` y al volver a inspeccionar la columna existe, se ignora; en cualquier otro caso se relanza y el arranque aborta.
- `init_db()` en `core/database.py` pasa a: `Base.metadata.create_all(bind=engine)` y a continuación `run_migrations(engine)`. Un fallo de migración aborta el arranque.
- **No** se añade `alembic` a `requirements.txt` (OPS-003 no toca `requirements.txt`). Criterios para pasar a Alembic en ADR-005.
- **`api/data/app.db` real:** ningún agente lo abre ni lo migra (los tests y QA usan `DATABASE_URL` temporal). La migración se aplicará sola en el primer arranque real de la API del usuario tras integrar el cambio; el `ALTER` es aditivo y conserva las filas, pero el PM debe avisar al usuario antes de ese arranque y recomendarle **copiar `api/data/app.db` antes** (una copia manual, no automática).
- Verificación (U, en `api/tests/unit/test_migrations.py`; criterios MG-xx de §7): BD «anterior» creada con el DDL congelado de abajo y dos usuarios sembrados, y BD nueva con `create_all`. Debe pasar igual **antes** de API-002 (la entidad aún sin las columnas: la migración las añade) y **después** (la entidad ya las tiene: la migración no hace nada).

DDL congelado de la tabla `users` anterior (tal como lo emitió `create_all` con la entidad de EP-01):
```sql
CREATE TABLE users (
    id INTEGER NOT NULL, username VARCHAR(80) NOT NULL, email VARCHAR(120) NOT NULL,
    hashed_password VARCHAR(255) NOT NULL, is_active BOOLEAN NOT NULL, created_at DATETIME NOT NULL,
    PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE UNIQUE INDEX ix_users_email ON users (email);
```

## 3. API
Prefijo `/api/auth`. JSON en `snake_case`. Los errores de dominio usan `{"error": {"code", "message"}}`. **ADR-001 (API-005):** los 422 de validación pasan a `{"error": {"code": "validation_error", "message", "fields": [...]}}` sin `input` (ver «Formato del 422» al final de esta sección); **hasta que API-005 esté implementada la API sigue devolviendo el `{"detail": [...]}` por defecto de FastAPI** y el Front acepta ambas formas. Los errores de dominio no se declaran en OpenAPI (como hoy); el 422 sí (§5).

### POST /api/auth/forgot-password (nuevo)
- **Auth:** pública
- **Request:** `ForgotPasswordRequest` — `{email}` (`EmailStr`)
- **Response 202:** `MessageResponse` — `{"message": "Si el email está registrado, recibirás un enlace para restablecer la contraseña."}`. **Idéntica** (estado, cuerpo y cabeceras) exista o no el email, esté o no activa la cuenta.
- **Errores:** 422 validación (**ADR-001/API-005:** `error.code == "validation_error"`, `fields[]`) si el email no tiene formato válido o falta. Ningún otro error previsto: los fallos internos del trabajo en segundo plano se registran (sin token ni email) y no cambian la respuesta.
- **Reglas de negocio:**
  1. El controlador **no consulta la BD** antes de responder: añade a `BackgroundTasks` la llamada `services.process_forgot_password(db.get_bind(), str(payload.email))` y devuelve el 202 (EP-02-D4).
  2. La tarea abre `Session(bind=bind, expire_on_commit=False)` y busca el usuario por email sin distinguir mayúsculas. Si **no existe o está inactivo**, termina sin hacer nada.
  3. Si existe y está activo: **borra todos los tokens del usuario** (el último pedido invalida los anteriores; los enlaces viejos darán `invalid_token`), genera `secrets.token_urlsafe(32)`, guarda `sha256(token)` con `expires_at = now + 30 min` y hace `commit`. Solo después llama al servicio de envío (§4.3) con el enlace `{FRONTEND_BASE_URL}/reset-password?token=<token>`.
  4. Cualquier excepción de la tarea se captura y se registra con el nombre de su clase (sin mensaje, token ni email) y sin propagarse.
  5. El token nunca aparece en ninguna respuesta de la API ni se guarda en claro; fuera de `DEBUG=true` tampoco se escribe en el log (§4.3).

### POST /api/auth/reset-password (nuevo)
- **Auth:** pública (el token de un solo uso es la credencial)
- **Request:** `ResetPasswordRequest` — `{token, new_password}`; `token`: cadena de 1 a 256 caracteres; `new_password`: **mismas reglas que `register`** (mínimo 8 caracteres y máximo 72 bytes UTF-8, ADR-004)
- **Response 200:** `MessageResponse` — `{"message": "Contraseña actualizada. Ya puedes iniciar sesión."}`. No inicia sesión ni devuelve tokens.
- **Errores:**
  - 400 `invalid_token` — «El enlace de recuperación no es válido o ya se ha utilizado»: el hash no existe, el token ya se usó o fue sustituido por una solicitud posterior, el usuario está inactivo o se pierde la carrera de consumo.
  - 400 `expired_token` — «El enlace de recuperación ha caducado»: `expires_at <= ahora` (el instante exacto de caducidad ya es caducado).
  - 422 validación (**ADR-001/API-005:** `fields[]`, antes `detail[]`): `token` vacío o de más de 256 caracteres; `new_password` de menos de 8 caracteres (`code == "string_too_short"`) o de más de 72 bytes UTF-8 (`code == "password_too_long"`, `loc == ["body", "new_password"]`, `ctx == {"max_bytes": 72}`, ADR-004). La validación del esquema ocurre **antes** de tocar el token: una contraseña inválida **no consume** el token.
- **Reglas de negocio** (en este orden; una sola transacción):
  1. Calcular `sha256(token)` y buscar la fila por `token_hash`. No existe o `used_at` no es nulo → `invalid_token`. `expires_at <= now` → `expired_token`. Usuario inexistente o inactivo → `invalid_token`.
  2. **Consumo atómico:** `UPDATE password_reset_tokens SET used_at = :now WHERE id = :id AND used_at IS NULL AND expires_at > :now`. Si `rowcount != 1` (otra petición lo consumió antes) → rollback y `invalid_token`. Garantiza el un solo uso con peticiones concurrentes.
  3. `user.hashed_password = hash_password(new_password)` y `user.token_version = User.token_version + 1` (incremento en SQL) → **revoca todos los access y refresh tokens emitidos** (ADR-003). Commit.
  4. Un token consumido o caducado no se borra al usar: queda con `used_at` hasta que la siguiente solicitud del usuario borre sus filas.

### POST /api/auth/register (cambia)
- Sin cambios de entrada: `UserCreate` **no admite rol**; cualquier campo `role` (o cualquier otro desconocido) del body se ignora (EP-02-D2).
- **Response 201:** `UserRead`, ahora con `role` (siempre `"user"`).
- El servicio crea el usuario con `role = UserRole.USER` explícito, nunca leído del payload.

### GET /api/auth/me (cambia)
- Devuelve `UserRead` con `role` (`"admin"` | `"user"`), leído de la BD en cada petición (no del token).
- Errores 401 como hoy, más «Token revocado» (ver abajo).

### POST /api/auth/login y POST /api/auth/refresh (cambian internamente)
- Los tokens emitidos llevan el claim `tv` (versión del usuario). Sin cambios de entrada ni de respuesta.
- `refresh` y `get_current_user` (usado por `/me` y por cualquier endpoint protegido) rechazan con **401** `unauthorized` «Token revocado» un token cuyo `tv` (ausente = `0`) no coincide con `user.token_version`. Los tokens anteriores a esta épica, sin `tv`, siguen valiendo mientras `token_version == 0`.
- Un `refresh` normal sigue devolviendo un par nuevo **sin invalidar** el refresh token anterior (limitación aceptada, ADR-003).

### Dependencia `require_role(*roles: UserRole)` (en `core/security.py`)
- Fábrica de dependencias: `require_role(UserRole.ADMIN)` resuelve `get_current_user` y, si `user.role` no está en `roles`, lanza `PermissionDeniedError("No tienes permisos para realizar esta acción")` → **403** `{"error": {"code": "forbidden", "message": "No tienes permisos para realizar esta acción"}}` (sin `WWW-Authenticate`). Sin token o token inválido sigue siendo 401 (el 401 precede al 403). `require_role()` sin roles lanza `ValueError` al declararla. Sin jerarquía: un endpoint que admita a ambos roles los lista.
- Esta épica **no** añade ningún endpoint de producción solo-admin (la gestión de usuarios está fuera de alcance). La dependencia se verifica con una ruta de prueba montada por el propio test (patrón P-1 de §7).

### Formato del 422 (ADR-001, tarea API-005; sustituye al `detail` por defecto de FastAPI)
- **Estado** 422. **Cuerpo** (`ValidationErrorResponse`): `{"error": {"code": "validation_error", "message": "Los datos enviados no son válidos", "fields": [{"loc": ["body", "new_password"], "code": "password_too_long", "message": "La contraseña no puede superar los 72 bytes en UTF-8", "ctx": {"max_bytes": 72}}]}}`.
- `fields[i]` equivale al `detail[i]` de Pydantic con `type → code` y `msg → message`, y **sin `input`** (ni `url` ni objetos de error). `ctx` es opcional (se omite si queda vacío) y solo conserva valores `str`, `int`, `float`, `bool` o `None` (nunca la clave `error`).
- Toda cadena emitida (`message`, elementos de `loc`) se sanea con `s.encode("utf-8", "replace").decode("utf-8")`: ningún contenido del usuario produce un 500 (BUG-004). En campos sensibles (último elemento de `loc` en `password`, `new_password`, `token`, `refresh_token`) el `message` solo es el de Pydantic para `code` ∈ {`missing`, `string_type`, `string_too_short`, `string_too_long`, `password_too_long`}; en otro caso es «Valor no válido».
- Aplica a **todos** los endpoints con cuerpo (`register`, `login`, `refresh`, `forgot-password`, `reset-password`) y a cualquier `FastAPI()` que llame a `register_exception_handlers` (también las de test). Los 404/405 del framework (`{"detail": "Not Found"}`) y el 500 no cambian (backlog).
- Equivalencias de los criterios de EP-01: `detail[0]["type"]` → `error.fields[0]["code"]`, `detail[0]["msg"]` → `error.fields[0]["message"]`, `detail[0]["loc"]` → `error.fields[0]["loc"]`, `detail[0]["ctx"]` → `error.fields[0]["ctx"]`.

## 4. Esquemas Pydantic y piezas internas
Los nombres y firmas son contractuales; el cuerpo es del Developer.

### 4.1 Configuración (`core/config.py`)
| Variable | Campo de `Settings` | Defecto | Reglas |
|----------|---------------------|---------|--------|
| `INITIAL_ADMIN_EMAIL` | `initial_admin_email: str` | `""` | Se valida al arrancar con `UserCreate` (§4.5), no en `Settings` |
| `INITIAL_ADMIN_USERNAME` | `initial_admin_username: str` | `""` | Ídem |
| `INITIAL_ADMIN_PASSWORD` | `initial_admin_password: SecretStr` | `SecretStr("")` | `SecretStr`: no aparece en `repr`. Se lee solo con `get_secret_value()` en `main.py` |
| `FRONTEND_BASE_URL` | `frontend_base_url: str` | `"http://localhost:4200"` | `field_validator`: debe empezar por `http://` o `https://` (si no, `ValueError("FRONTEND_BASE_URL debe empezar por http:// o https://")`) y se le quita la `/` final |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `password_reset_expire_minutes: int` | `30` | `Field(gt=0, le=1440)`. 30 es la decisión del usuario; la variable existe para operación, los tests no dependen de ella |

- `Settings.model_config` añade `hide_input_in_errors=True`: un `ValidationError` de configuración (p. ej. `SECRET_KEY` ausente fuera de debug) no debe incluir `input_value` con `INITIAL_ADMIN_PASSWORD`. Puede cambiar el texto de esos errores; el Developer comprueba `tests/unit/test_config.py`.
- La contraseña del admin **no se valida dentro de `Settings`** (un error de validador de modelo mostraría el diccionario de entrada) y **nunca** se escribe en logs, mensajes de error ni informes.
- `api/tests/conftest.py` (API-002) fija `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_USERNAME` e `INITIAL_ADMIN_PASSWORD` a `""` junto a `DEBUG`, `SECRET_KEY` y `DATABASE_URL`, antes de importar `app.*`: una variable del shell o del `api/.env` del usuario no debe colarse en la suite.
- Las variables no se añaden a `api/.env` ni a ningún fichero con secretos; documentarlas (comentadas y sin valores) en `api/.env.example` y en el README es opcional (decisión del PM, §9).

### 4.2 Esquemas (`modules/auth/schemas.py`)
| Esquema | Campos y restricciones |
|---------|------------------------|
| `UserRole` (`StrEnum`, en `entities.py`) | `admin`, `user` |
| `UserRead` | como hoy más `role: UserRole`. **No** incluye `token_version` ni `hashed_password` |
| `UserCreate` | sin cambios de campos (no hay `role`). `password` pasa a usar el tipo compartido `NewPassword` |
| `NewPassword` (alias `Annotated`) | `str` con `AfterValidator(_check_password_bytes)` y `Field(min_length=8, description=<la actual de UserCreate.password>)`. Lo comparten `UserCreate.password` y `ResetPasswordRequest.new_password`; el OpenAPI de `UserCreate.password` **no cambia** |
| `ForgotPasswordRequest` | `email: EmailStr` |
| `ResetPasswordRequest` | `token: str` (`min_length=1`, `max_length=256`); `new_password: NewPassword` |
| `MessageResponse` | `message: str` |

`LoginRequest`, `RefreshRequest` y `TokenResponse` no cambian (el claim `tv` es interno al JWT).

### 4.3 Servicio de envío en modo desarrollo (`api/app/shared/mail.py`, nuevo)
```python
class MailSender(Protocol):
    def send_password_reset(self, to_email: str, reset_url: str) -> None: ...

class LogMailSender:   # modo desarrollo
class NullMailSender:  # el resto de casos: no hace nada

def get_mail_sender() -> MailSender
def build_password_reset_url(token: str) -> str   # f"{settings.frontend_base_url}/reset-password?token={token}"
```
- **Mecanismo de activación (garantía):** `get_mail_sender()` devuelve `LogMailSender()` **solo si `settings.debug is True`** y `NullMailSender()` en cualquier otro caso. Es la única condición: no hay una variable propia que pueda quedar activada por error. Se evalúa **en cada llamada** (no se cachea ni se decide al importar), de modo que los tests pueden alternar `settings.debug` con `monkeypatch`. Defensa en profundidad: `LogMailSender.send_password_reset` vuelve a comprobar `settings.debug` y no emite nada si es falso.
- `LogMailSender` escribe **una** línea de nivel INFO en el logger `app.mail`: `[DEV] Recuperación de contraseña para <email>: <reset_url>`. El módulo configura el logger `app.mail` (nivel INFO y un `StreamHandler` a stderr si no tiene manejadores, con `propagate` activo) porque uvicorn solo configura sus propios loggers y un INFO de otro logger no saldría por consola.
- Fuera de `DEBUG=true` la recuperación de contraseña **no entrega ningún enlace** (no hay SMTP: backlog) pero la API responde igual y crea el token; el token no puede usarse porque nadie lo conoce. No se escribe nada en el log.
- `services.py` debe llamar a `mail.get_mail_sender()` a través del **módulo** (`from app.shared import mail`), no con `from ... import get_mail_sender`, para que un test pueda sustituirlo con `monkeypatch`.
- El interfaz es el punto de extensión de un SMTP real (backlog): una clase nueva con el mismo método y la selección en `get_mail_sender()`.

### 4.4 Servicios y seguridad
| Pieza | Contrato |
|-------|----------|
| `services.register_user(db, payload)` | Crea con `role=UserRole.USER`, nunca desde el payload |
| `services.process_forgot_password(bind, email) -> None` | Envoltorio de la tarea en segundo plano: abre la sesión, llama a `create_password_reset(db, email)`, captura todo `Exception` y lo registra con `type(exc).__name__` |
| `services.create_password_reset(db, email, *, now=None) -> None` | Lógica de §3 (buscar, borrar anteriores, insertar hash, commit, enviar). `now` opcional para los tests (por defecto `datetime.now(timezone.utc)`) |
| `services.reset_password(db, token, new_password, *, now=None) -> None` | Lógica de §3; lanza `InvalidTokenError` o `ExpiredTokenError` |
| `services.hash_reset_token(token) -> str` | `hashlib.sha256(token.encode("utf-8")).hexdigest()` |
| `services.FORGOT_PASSWORD_MESSAGE` | Constante del texto de §3 |
| `shared/exceptions.py` | `InvalidTokenError(AppError)`: 400, `code = "invalid_token"`; `ExpiredTokenError(AppError)`: 400, `code = "expired_token"`. Se reutilizarán en otros flujos de token |
| `core/security.py` | `create_access_token(subject, token_version: int = 0)` y `create_refresh_token(...)` añaden el claim `tv`; `ensure_token_is_current(payload, user)` (`payload.get("tv", 0) != user.token_version` → `AuthenticationError("Token revocado")`) lo usan `get_current_user` y `refresh_tokens`; `require_role(*roles)`. `services.build_tokens(user)` pasa `user.token_version` |
| `main.py` (`lifespan`) | `init_db()` y a continuación `ensure_initial_admin` con una sesión de `SessionLocal` (§4.5) |
| `shared/validation.py` (nuevo, ADR-001/API-005) | `validation_error_response(exc: RequestValidationError) -> JSONResponse` y los modelos `ValidationFieldError`, `ValidationErrorBody`, `ValidationErrorResponse` (solo para OpenAPI); `register_exception_handlers` registra el handler. Reglas en §3 «Formato del 422» |

### 4.5 Primer administrador (`services.ensure_initial_admin`)
`ensure_initial_admin(db, *, email: str, username: str, password: str) -> Literal["created", "promoted", "unchanged"]`. `main.py` lo llama con los valores de `settings` (`password` = `get_secret_value()`). Reglas, en este orden:
1. Con `strip()`, las **tres** vacías → `"unchanged"` sin acceder a la BD (no configurado).
2. Solo algunas definidas → `RuntimeError` «INITIAL_ADMIN_EMAIL, INITIAL_ADMIN_USERNAME e INITIAL_ADMIN_PASSWORD deben definirse juntas (faltan: ...)» con los **nombres** de las que faltan. El arranque aborta.
3. Se valida con `UserCreate(username, email, password)` (mismas reglas que el registro: email válido, usuario de 3 a 80 caracteres, contraseña de mínimo 8 caracteres y máximo 72 bytes). Si falla: `RuntimeError` con los **nombres de variable** y el `type` del error (p. ej. «INITIAL_ADMIN_PASSWORD no es válida (password_too_long)»), lanzado con `from None`; nunca el valor ni el `ValidationError` original (su texto incluye la entrada).
4. Si **ya existe algún usuario con `role = admin`** → `"unchanged"` (se ignoran las variables; INFO sin datos sensibles). Esto hace el arranque idempotente y evita que una variable olvidada re-promueva a alguien tras degradarlo; si algún día no queda ningún admin, el siguiente arranque con las variables lo restaura.
5. Si existe un usuario con ese email (sin distinguir mayúsculas) → se **promueve** a `admin` cambiando solo `role` (no cambia contraseña, usuario ni `is_active`; si está inactivo, WARNING) → `"promoted"`. La contraseña de la variable se valida pero no se aplica.
6. Si existe un usuario con ese `username` pero otro email → `RuntimeError` («INITIAL_ADMIN_USERNAME ya pertenece a otro usuario»); sin cambios en la BD.
7. En otro caso se crea `User(username, email.lower(), hash_password(password), role=admin, is_active=True)` → `"created"`.
- Se hace `commit` una sola vez. Logs (INFO): resultado, `id` y `username`; **nunca** la contraseña, su hash ni el valor de la variable. Se recomienda al operador retirar `INITIAL_ADMIN_PASSWORD` del entorno tras el primer arranque.
- No hay endpoint de alta de admin ni de cambio de rol en esta épica: el único camino a `admin` es esta variable.

## 5. Fragmento OpenAPI 3.1
Fuente de verdad: `/openapi.json` generado. Debe coincidir con lo siguiente en lo relevante (el resto de rutas y esquemas de [auth.md](auth.md) no cambia salvo `UserRead`):

```yaml
paths:
  /api/auth/forgot-password:
    post:
      tags: [auth]
      operationId: forgot_password_api_auth_forgot_password_post
      requestBody: { required: true, content: { application/json: { schema: { $ref: "#/components/schemas/ForgotPasswordRequest" } } } }
      responses:
        "202": { content: { application/json: { schema: { $ref: "#/components/schemas/MessageResponse" } } } }
        "422": { content: { application/json: { schema: { $ref: "#/components/schemas/ValidationErrorResponse" } } } }   # ADR-001/API-005 (antes HTTPValidationError)
  /api/auth/reset-password:
    post:
      tags: [auth]
      operationId: reset_password_api_auth_reset_password_post
      requestBody: { required: true, content: { application/json: { schema: { $ref: "#/components/schemas/ResetPasswordRequest" } } } }
      responses:
        "200": { content: { application/json: { schema: { $ref: "#/components/schemas/MessageResponse" } } } }
        "422": { content: { application/json: { schema: { $ref: "#/components/schemas/ValidationErrorResponse" } } } }   # ADR-001/API-005 (antes HTTPValidationError)
components:
  schemas:
    UserRole: { type: string, enum: [admin, user], title: UserRole }
    UserRead:
      required: [id, username, email, role, is_active, created_at]   # role es nuevo
      properties:
        id: { type: integer }
        username: { type: string }
        email: { type: string, format: email }
        role: { $ref: "#/components/schemas/UserRole" }
        is_active: { type: boolean }
        created_at: { type: string, format: date-time }
    ForgotPasswordRequest:
      required: [email]
      properties:
        email: { type: string, format: email }
    ResetPasswordRequest:
      required: [token, new_password]
      properties:
        token: { type: string, minLength: 1, maxLength: 256 }
        new_password:
          type: string
          minLength: 8            # sin maxLength: el máximo es en bytes (ADR-004)
          description: "<texto que menciona el límite de 72 bytes UTF-8>"
    MessageResponse:
      required: [message]
      properties:
        message: { type: string }
    # ADR-001/API-005: sustituyen a HTTPValidationError y ValidationError, que dejan de existir en /openapi.json
    ValidationErrorResponse:
      required: [error]
      properties:
        error: { $ref: "#/components/schemas/ValidationErrorBody" }
    ValidationErrorBody:
      required: [code, message, fields]
      properties:
        code: { type: string, default: validation_error }
        message: { type: string }
        fields: { type: array, items: { $ref: "#/components/schemas/ValidationFieldError" } }
    ValidationFieldError:
      required: [loc, code, message]
      properties:
        loc: { type: array, items: { anyOf: [{ type: string }, { type: integer }] } }
        code: { type: string }
        message: { type: string }
        ctx: { description: "opcional; objeto con valores escalares" }
```
- **ADR-001/API-005:** las operaciones con cuerpo (`register`, `login`, `refresh`, `forgot-password`, `reset-password`) declaran `responses={422: {"model": ValidationErrorResponse}}` (en `controllers.py`); `/me` y `/health` siguen sin 422. Ningún esquema de 422 tiene `input`.
- `UserCreate` **no** tiene `role` ni `is_active`; `UserRead` no tiene `token_version` ni `hashed_password`; ningún esquema de respuesta tiene un campo de token de reseteo o hash.
- Los errores 400 (`invalid_token`, `expired_token`), 401 y 403 no aparecen en OpenAPI (se documentan en §3).

## 6. Front (Angular)
**Diseño de ARQ-004 (2026-11-11), listo para aprobar por el PM.** Resuelve [ADR-001](adr/ADR-001-errores-validacion.md), [ADR-002](adr/ADR-002-tokens-front.md) y [ADR-006](adr/ADR-006-rendermode.md) (los tres aceptados) y desbloquea WEB-001 a WEB-004 (§9.1). La API que consume el Front es la de §3; ARQ-004 solo cambia en ella el formato del 422 (ADR-001, tarea API-005, §3 y §5 marcados).

### 6.1 Hechos del código actual que condicionan el diseño
- **Sin zone.js** (no está en `package.json` ni se configura): detección de cambios sin zona. Todo estado que cambie de forma asíncrona (HTTP, timers) debe ser un `signal`; asignar un campo plano tras una respuesta no repinta. El `LoginComponent` actual usa campos planos (`loading`) y `setTimeout`: debe pasar a `signal`.
- `app.html` conserva la plantilla de bienvenida de Angular (`<h1>Hello, {{ title() }}</h1>`, estilos y logos) con el `<router-outlet />` **al final**: se vería en todas las rutas. `app.spec.ts` espera `Hello, web`. WEB-001 deja `app.html` solo con `<router-outlet />`, quita `title` de `app.ts`, vacía `app.css` y reescribe `app.spec.ts` (la app se crea; sin `h1`).
- `app.config.ts` no tiene `provideHttpClient`; `app.routes.ts` está vacío; `app.routes.server.ts` prerenderiza `**`; `index.html` tiene `lang="en"` y `<title>Web</title>`; `outputMode: "server"` con `server.ts` (Express + `AngularNodeAppEngine`, sin log de peticiones). No existe `core/`.
- `LoginComponent` (standalone, constructor + `FormsModule`/`ngModel`) simula la llamada y navega a `/dashboard` (no existe); «¿Olvidaste tu contraseña?» y «Regístrate aquí» son `href="#"`.
- TS sin `strict`, con `noPropertyAccessFromIndexSignature` (índices con corchetes: `ctx['max_bytes']`), `noImplicitReturns` y `noImplicitOverride`. Prettier (100 columnas, comillas simples) y Vitest (`ng test`, jsdom).

### 6.2 Decisiones
| ID | Decisión | Alternativas | Motivo |
|----|----------|--------------|--------|
| ADR-001 (aceptado) | La API pasa a un handler propio del 422 con envelope `{"error": {"code": "validation_error", "message", "fields": [...]}}` **sin `input`** y sin 500 con sustitutos Unicode (API-005). El Front tiene **un único normalizador** (`normalizeApiError`) que acepta el envelope, el `detail` por defecto (transición y 404/405 del framework) y fallos de red | Mantener `detail` y solo normalizar en el Front; respuesta con ambas formas | El Front no puede quitar de la respuesta lo que la API ya envía (contraseña o token en `input`, BUG-004); el normalizador hace falta igualmente para 404/405, 5xx y red |
| ADR-002 (aceptado) | Access token **solo en memoria**; refresh token en `localStorage` (con «Recordarme») o `sessionStorage` (sin él); `/me` en cada carga; ni el usuario ni el access token se persisten. En el servidor no hay sesión | Todo en memoria; todo en `localStorage`; cookies `HttpOnly` con BFF | Ver ADR-002 |
| ADR-006 (aceptado) | `RenderMode.Prerender` solo para `login`, `register` y `forgot-password`; `reset-password` y todo lo demás (`**`) en `Client` | Prerender global; Server | Privado por defecto; el token de la URL nunca se renderiza |
| EP-02-F1 | Destino tras el login: el `returnUrl` saneado o `/inicio`. `/inicio` es una **pantalla privada mínima** (usuario, correo, rol y «Cerrar sesión») del módulo `inicio`, a sustituir por el panel real | Ruta `/dashboard` vacía; preguntar al usuario | Existe una ruta privada real con la que probar el guard sin inventar pantallas de dominio; reversible (un `loadComponent`) |
| EP-02-F2 | Tras el registro (201 sin tokens): **login automático** encadenando `login` con las mismas credenciales y sin «Recordarme». Si el login falla, ir a `/login?motivo=registrada` | Redirigir siempre a `/login` | Sin verificación de email no hay motivo para exigir otro paso; la contraseña ya está en el formulario; el fallo del segundo paso tiene salida limpia |
| EP-02-F3 | Pantallas nuevas con **Reactive Forms** tipados (`inject(FormBuilder).nonNullable`) y `signal` para el estado; el login conserva `FormsModule`/`ngModel` (cambia `inject()` y los `signal`, no el formulario) | Refactorizar el login; signal forms (experimentales) | Los validadores propios (bytes, coincidencia) encajan en Reactive Forms; el login solo se toca lo necesario |
| EP-02-F4 | `''` → `login`; `**` → `''`. Un usuario con sesión que va a `/login` pasa por `guestGuard` a `/inicio` | `''` → `inicio` | Un anónimo en `/` no ve `?returnUrl=%2Finicio` |
| EP-02-F5 | **Sin guard de rol** en esta épica: el rol solo se expone (`AuthService.role`, pantalla `inicio`). La autorización real es siempre de la API | Crear `roleGuard` ya | No hay pantallas de admin (backlog) |
| EP-02-F6 | `/reset-password` **sin `guestGuard`**: quien tiene sesión también puede usar el enlace; tras un reseteo correcto el Front descarta la sesión local (el token ya está revocado, ADR-003) | Redirigir a `/inicio` | El enlace puede abrirse en un navegador con otra cuenta |
| EP-02-F7 | URL base de la API: `environment.apiBaseUrl = 'http://127.0.0.1:8000/api'` en `web/src/environments/environment.ts` (un solo fichero, sin `fileReplacements` hasta que exista un entorno de despliegue) | `environment.prod.ts` ahora; URL relativa con proxy | Un solo entorno real; la URL absoluta funciona igual en el navegador y en el servidor SSR |
| EP-02-F8 | «Cerrar sesión» es **solo local** (no hay endpoint de logout): se borran tokens y estado; el refresh token sigue siendo válido en la API hasta caducar (limitación de ADR-003) | — | Sin endpoint; backlog junto con la rotación |
| EP-02-F9 | `core/` nace en WEB-001 con lo transversal (URL base, interceptores, guards, normalizador de errores). `AuthService` y `TokenStorageService` viven en `modules/auth/services/` y `core/` los importa (sin ciclos de ficheros) | Todo en `core/auth` | Convención «servicios HTTP en `<modulo>/services/`» |

### 6.3 Ficheros (`web/`)
```
src/index.html                      lang="es", <title>, <meta name="referrer" content="no-referrer">
src/environments/environment.ts     { apiBaseUrl: 'http://127.0.0.1:8000/api' }
src/app/app.config.ts               provideHttpClient(withFetch(), withInterceptors([apiErrorInterceptor, authInterceptor]))
src/app/app.routes.ts · app.routes.server.ts
src/app/app.ts · app.html · app.css · app.spec.ts       (cascarón: solo <router-outlet />)
src/app/core/config/api-base-url.ts          API_BASE_URL (InjectionToken, providedIn root, factory → environment.apiBaseUrl)
src/app/core/http/api-error.ts               ApiError, FieldError, normalizeApiError()
src/app/core/http/validation-messages.ts     tabla (campo, code) → texto en español
src/app/core/http/api-error.interceptor.ts   apiErrorInterceptor (fuera): HttpErrorResponse → ApiError
src/app/core/auth/auth-context.ts            HttpContextToken PUBLIC_ENDPOINT y RETRIED
src/app/core/auth/auth.interceptor.ts        authInterceptor (dentro): Authorization y refresco/reintento
src/app/core/auth/auth.guard.ts              authGuard y guestGuard
src/app/core/auth/return-url.ts              sanitizeReturnUrl()
src/app/modules/auth/models/auth.models.ts   interfaces espejo del contrato (§6.7)
src/app/modules/auth/services/auth.service.ts · token-storage.service.ts
src/app/modules/auth/validators/password.validators.ts   passwordMinLength, passwordMaxBytes, passwordsMatch
src/app/modules/auth/login/ (existente) · register/ · forgot-password/ · reset-password/   <pantalla>.component.{ts,html,css}
src/app/modules/inicio/inicio/inicio.component.{ts,html,css}
```
Cada pieza lleva su `*.spec.ts` al lado. Los componentes de pantalla importan `RouterLink` y `ReactiveFormsModule` (o `FormsModule` el login) y son `standalone` con `inject()`.

### 6.4 Rutas, guards y `RenderMode`
| Path | Componente (`loadComponent`) | Guard | `title` | `RenderMode` |
|------|------------------------------|-------|---------|--------------|
| `''` (`pathMatch: 'full'`) | `redirectTo: 'login'` | — | — | `Client` (cubierta por `**`) |
| `login` | `LoginComponent` | `guestGuard` | Iniciar sesión | `Prerender` |
| `register` | `RegisterComponent` | `guestGuard` | Crear cuenta | `Prerender` |
| `forgot-password` | `ForgotPasswordComponent` | `guestGuard` | Recuperar contraseña | `Prerender` |
| `reset-password` | `ResetPasswordComponent` | — (EP-02-F6) | Nueva contraseña | `Client` + cabeceras |
| `inicio` | `InicioComponent` | `authGuard` | Inicio | `Client` (cubierta por `**`) |
| `**` | `redirectTo: ''` | — | — | `Client` |

`app.routes.server.ts` (ADR-006): `login`, `register` y `forgot-password` → `Prerender`; `reset-password` → `Client` con `headers: { 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store' }`; `**` → `Client` (privado por defecto: cualquier ruta futura es CSR hasta que se decida otra cosa). Si `ServerRoute.headers` no se emite en una ruta `Client` (QA lo comprueba con `serve:ssr:web`), el Developer añade un middleware de Express en `server.ts` que fije esas cabeceras para la ruta `/reset-password`.

**Guards** (funcionales, `CanActivateFn`, asíncronos; en el navegador esperan `await auth.restoreSession()`):
- `authGuard`: en el navegador, autenticado → `true`; si no → `UrlTree('/login', { queryParams: { returnUrl: state.url } })`. **En el servidor nunca concede** (devuelve `UrlTree('/login')`): fail-closed; no llega a ejecutarse mientras las rutas privadas sean `Client`.
- `guestGuard`: en el navegador, autenticado → `UrlTree('/inicio')`; si no, `true`. En el servidor siempre `true` (no hay sesión que consultar; el formulario es idéntico para todos).
- `sanitizeReturnUrl(value: string | null): string | null` acepta solo rutas internas: empieza por `/`, no por `//` ni `/\`, sin esquema ni caracteres de control y sin `://`; además no puede apuntar a `/login`, `/register`, `/forgot-password` ni `/reset-password`. Si no cumple, se ignora y el destino es `/inicio`. Se aplica **siempre** antes de `navigateByUrl`.
- Sin guard de rol (EP-02-F5).

### 6.5 Sesión, tokens e interceptores (ADR-002)
**`TokenStorageService`** (`providedIn: 'root'`; cada acceso protegido con `isPlatformBrowser(inject(PLATFORM_ID))` y `try/catch`: Safari privado, cuota o almacenamiento deshabilitado degradan a «sin persistencia» sin lanzar). Nada en el constructor.
| Método | Comportamiento |
|--------|----------------|
| `get(): string \| null` | Lee `sessionStorage` y, si no está, `localStorage` (clave `auth.refresh_token`); `null` en el servidor |
| `set(token, persistent)` | Escribe en `localStorage` (persistent) o `sessionStorage` y borra la clave del otro |
| `update(token)` | Reescribe el token en el **mismo** almacén en el que estaba (el refresco conserva la elección de «Recordarme») |
| `clear()` | Borra la clave en ambos |

**`AuthService`** (`providedIn: 'root'`, en `modules/auth/services/`). Estado en memoria; no se persiste ni el usuario ni el access token.
| Miembro | Contrato |
|---------|----------|
| `status` | `signal<'unknown' \| 'anonymous' \| 'authenticated'>('unknown')` |
| `user` | `signal<UserRead \| null>(null)` |
| `isAuthenticated` / `role` | `computed`: `status() === 'authenticated'` / `user()?.role ?? null` |
| `accessToken(): string \| null` | Access token en memoria (campo privado; el interceptor lo lee) |
| `login(c: LoginRequest, remember: boolean): Observable<UserRead>` | `POST /auth/login` (público) → guarda el access en memoria y el refresh con `set(token, remember)` → `me()` → `status = 'authenticated'`. Si `me()` falla se descarta la sesión y se propaga el error |
| `register(p: UserCreate): Observable<UserRead>` | `POST /auth/register` (público); no inicia sesión |
| `refresh(): Observable<TokenResponse>` | `POST /auth/refresh` (público) con el token del almacén; **una sola petición en vuelo** (el mismo `Observable` compartido con `shareReplay`, liberado en `finalize`); guarda el par nuevo (`update`). Sin refresh token → `ApiError(401, 'no_refresh_token')` sin llamar a la API |
| `me(): Observable<UserRead>` | `GET /auth/me` (con `Authorization`); fija `user` |
| `forgotPassword(email): Observable<MessageResponse>` | `POST /auth/forgot-password` (público) |
| `resetPassword(token, newPassword): Observable<MessageResponse>` | `POST /auth/reset-password` (público) |
| `logout(): void` | Local (EP-02-F8): `clearSession()` |
| `clearSession(motivo?: 'expirada' \| 'revocada'): void` | Borra access y refresh, `user = null`, `status = 'anonymous'`. Idempotente |
| `restoreSession(): Promise<void>` | Memoizada (una sola ejecución). Servidor: no hace nada. Navegador: sin refresh token → `anonymous`; con él → `refresh()` + `me()` → `authenticated`; fallo **401** → `clearSession()`; fallo de red/5xx → `anonymous` **sin borrar** el token (se reintenta al volver a entrar) |

**Sin lecturas de almacenamiento ni de la URL en el primer pase de render** (SSR/hidratación): todo lo que dependa del navegador (query `motivo`, `returnUrl`, token de la URL) se fija en `afterNextRender` o en una guarda/handler, nunca en el constructor ni en la plantilla del primer pase, para no producir `NG0500`.

**Refresco y reintento (`authInterceptor`)**, funcional, `inject(AuthService)` e `inject(Router)` en el cuerpo de la función:
1. Pasa sin tocar si la petición lleva `PUBLIC_ENDPOINT` (login, register, refresh, forgot, reset: los fija `AuthService` con `HttpContext`) o si su URL no empieza por `API_BASE_URL` (nunca se envía el token a otro origen).
2. Si hay access token, clona la petición con `Authorization: Bearer <token>`.
3. Ante `HttpErrorResponse` **401** y sin `RETRIED`: llama a `auth.refresh()` (compartido: N 401 concurrentes provocan **un** `/refresh`) y reintenta **una vez** con el token nuevo y `RETRIED = true` (un 401 tras el reintento no vuelve a refrescar: sin bucles).
4. Si el refresco falla con `ApiError` 401 (incluye «Token revocado» y `no_refresh_token`): `auth.clearSession(motivo)` con `motivo = 'revocada'` si el mensaje del 401 (de la petición o del refresco) es exactamente «Token revocado» y `'expirada'` en otro caso; navega a `/login` con `queryParams { returnUrl: <ruta actual>, motivo }` salvo que ya esté en una ruta pública (`/login`, `/register`, `/forgot-password`, `/reset-password`); propaga el error original. Un fallo del refresco que no sea 401 (red, 5xx) se propaga **sin cerrar la sesión**.
5. 403 y demás estados pasan tal cual (mensaje de permisos en la pantalla que lo use).

**`apiErrorInterceptor`** (el primero de `withInterceptors`, es decir, el más externo): `catchError(e => throwError(() => normalizeApiError(e)))`. Los consumidores reciben siempre un `ApiError`. El orden es `[apiErrorInterceptor, authInterceptor]`: `authInterceptor` ve el `HttpErrorResponse` crudo y `apiErrorInterceptor` normaliza lo que sale.

### 6.6 Errores: `ApiError` y `normalizeApiError` (ADR-001)
```typescript
export interface FieldError { field: string | null; code: string; message: string; ctx?: Record<string, unknown>; }
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string, readonly fields: FieldError[] = []) { super(message); }
}
export function normalizeApiError(err: unknown): ApiError;   // total: nunca lanza
```
Reglas (en este orden; la primera que aplica):
| Entrada | `status` · `code` · `message` |
|---------|-------------------------------|
| `HttpErrorResponse` con `status === 0` | `0` · `network_error` · «No se pudo conectar con el servidor. Inténtalo de nuevo más tarde.» |
| Cuerpo `{error: {code, message, fields?}}` (dominio y 422 de ADR-001) | el estado HTTP · `error.code` · `error.message` (español, tal cual); `fields` mapeados con `field` |
| Cuerpo `{detail: [...]}` (422 por defecto: transición hasta API-005) | `422` · `validation_error` · «Los datos enviados no son válidos»; `fields` de `loc` y `type` (`msg` e `input` **se ignoran siempre**) |
| Cuerpo `{detail: "..."}` (404 y 405 de Starlette) | el estado · `http_<estado>` · «La operación solicitada no está disponible.» |
| Estado ≥ 500 o cuerpo no JSON | el estado · `server_error` · «Error del servidor. Inténtalo de nuevo más tarde.» |
| Cualquier otra cosa (no `HttpErrorResponse`, cuerpo vacío) | `0` · `unexpected_error` · «Se ha producido un error inesperado.» |
- **`field`** de un `FieldError`: de `loc` se quita el primer elemento si es `body`, `query`, `path`, `header` o `cookie`, y el resto se une con `.`; si queda vacío es `null` (error de formulario, p. ej. JSON mal formado).
- **`message`** de un `FieldError` es **siempre el texto del Front** (`validation-messages.ts`, no el `message`/`msg` de la API): se busca por `(field, code)` y luego por `code`; si no existe, «Valor no válido.». Textos mínimos: `password_too_long` → «La contraseña no puede superar los 72 bytes (UTF-8); caracteres como ñ o las tildes ocupan más de uno.»; `string_too_short` en `password`/`new_password` → «La contraseña debe tener al menos 8 caracteres.» y en `username` → «El usuario debe tener al menos 3 caracteres.»; `string_too_long` en `username` → «El usuario no puede superar los 80 caracteres.»; error de `email` (`value_error`) → «Introduce un correo electrónico válido.»; `missing` → «Campo obligatorio.».
- El normalizador no copia ni registra el cuerpo de la petición ni `input`; **ninguna contraseña ni token va a `console`**.

### 6.7 Modelos TS (`modules/auth/models/auth.models.ts`, espejo exacto del contrato, sin capa de mapeo)
```typescript
export type UserRole = 'admin' | 'user';
export interface UserCreate { username: string; email: string; password: string; }      // sin rol (EP-02-D2)
export interface LoginRequest { email: string; password: string; }
export interface RefreshRequest { refresh_token: string; }
export interface ForgotPasswordRequest { email: string; }
export interface ResetPasswordRequest { token: string; new_password: string; }
export interface UserRead { id: number; username: string; email: string; role: UserRole; is_active: boolean; created_at: string; }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: 'bearer'; expires_in: number; }
export interface MessageResponse { message: string; }
// Errores (ADR-001): cuerpo de la API; el Front los consume ya normalizados (ApiError, §6.6)
export interface ApiFieldError { loc: (string | number)[]; code: string; message: string; ctx?: Record<string, unknown>; }
export interface ApiErrorBody { error: { code: string; message: string; fields?: ApiFieldError[] } }
```
Utilidades de sesión (no son del contrato de la API): `type SessionNotice = 'expirada' | 'revocada' | 'registrada' | 'restablecida'` (valores permitidos del query `motivo` del login).

### 6.8 Contrato de errores de la API para el Front
| Situación | Respuesta | Tratamiento esperado |
|-----------|-----------|----------------------|
| Campo con formato inválido en cualquier formulario | 422 `error.code == "validation_error"` con `error.fields[]` (antes de API-005: `detail[]`, el normalizador acepta ambos) | Error bajo el campo (`FieldError.field`); sin `input` en ninguna forma |
| Forgot (cualquier email válido) | 202 `MessageResponse` | Mismo mensaje de confirmación siempre; no decir si la cuenta existe |
| Reset con enlace usado, sustituido o de usuario inactivo | 400 `error.code == "invalid_token"` | Pedir un enlace nuevo; el formulario deja de ser utilizable |
| Reset con enlace caducado | 400 `error.code == "expired_token"` | Ídem |
| Contraseña nueva < 8 caracteres o > 72 bytes | 422 con `fields[0].loc == ["body","new_password"]` y `code` `string_too_short` o `password_too_long` | Error de campo; el enlace sigue vigente (el token no se consume) |
| Registro duplicado | 409 `error.code == "conflict"`, `message` «El email ya está registrado» o «El nombre de usuario ya está registrado» | Error bajo el campo correspondiente (por el texto exacto); otro texto → aviso general |
| Login erróneo | 401 `unauthorized`, «Credenciales inválidas» o «La cuenta está desactivada» | Aviso en el formulario con el mensaje de la API |
| Access o refresh tras un reseteo | 401 `unauthorized`, `message == "Token revocado"` | `clearSession('revocada')` y volver al login con el aviso |
| Access caducado | 401 `unauthorized` | Refresco y reintento (§6.5); si el refresco falla, `clearSession('expirada')` |
| Rol insuficiente | 403 `forbidden` | Mensaje de permisos (sin pantallas que lo usen en esta épica) |
| API caída / CORS / red | `status 0` | «No se pudo conectar con el servidor…»; la sesión no se cierra |
| 404/405 del framework (`detail` texto), 5xx, cuerpo no JSON | — | Mensaje genérico (§6.6) |

### 6.9 Pantallas (componentes `standalone` en `modules/auth/<pantalla>/<pantalla>.component.{ts,html,css}`)
**Comunes.** Estilo del login existente (mismo contenedor `bg-gradient-to-br`, tarjeta `rounded-2xl shadow-xl max-w-md`, cabecera `bg-indigo-600`, mismas clases de `input` y botón); sin componente de maquetación compartido (cuatro usos, clases idénticas). Estado asíncrono en `signal`. Accesibilidad mínima: cada `input` con `<label for>`, `autocomplete` correcto, `aria-invalid` y `aria-describedby` hacia su mensaje (`id="<campo>-error"`); aviso de error del formulario con `role="alert"` y avisos informativos con `role="status"` (`aria-live="polite"`); botón de envío `disabled` y `aria-busy` mientras `loading`; tras un envío fallido el foco va al primer campo inválido o al aviso (`tabindex="-1"`). Los errores de campo se muestran con el control `touched` o tras intentar enviar, y los de servidor se limpian al editar el campo. **Las contraseñas nunca se recortan (`trim`), se registran ni se guardan**; el correo y el usuario sí se recortan antes de validar y enviar.

**Validación espejo de la API (`validators/password.validators.ts`, funciones puras con `spec`):**
- `passwordMinLength(8)`: cuenta **puntos de código** (`Array.from(value).length`), no unidades UTF-16 (como Pydantic).
- `passwordMaxBytes(72)`: `new TextEncoder().encode(value).length > 72` → error `password_too_long`. **Nada de `maxlength`** (cuenta caracteres, no bytes, ADR-004). 72 bytes exactos son válidos y 73 no (`"a".repeat(71) + "ñ"` falla, `"a".repeat(70) + "ñ"` pasa).
- `passwordsMatch(a, b)` (validador de grupo, error `mismatch`; el campo de confirmación no se envía).
- `username`: 3 a 80 caracteres; `email`: obligatorio y `Validators.email`.

| Pantalla (ruta) | Campos y reglas | Flujo y estados |
|-----------------|-----------------|-----------------|
| **`login`** (existente, `/login`) | `email`, `password` (obligatorios, sin mínimo ni máximo), `rememberMe`. Mantiene `FormsModule`/`ngModel`. Cambios: `inject()` en lugar del constructor, `loading` y `errorMessage` como `signal`, llamada real, `routerLink` en los dos enlaces (`/forgot-password` y `/register`), `autocomplete="email"` y `"current-password"`, texto de ayuda de «Recordarme» («Mantiene la sesión iniciada en este dispositivo»). | Envía `auth.login({email: email.trim(), password}, rememberMe)`. Éxito → `navigateByUrl(sanitizeReturnUrl(query returnUrl) ?? '/inicio')`. Error: 401 → mensaje de la API; 422 → email inválido bajo el campo, otros → «Credenciales inválidas»; red/5xx → mensaje del normalizador. Aviso informativo por `motivo` (tabla cerrada; valor desconocido se ignora): `expirada` «Tu sesión ha caducado. Inicia sesión de nuevo.», `revocada` «Tu sesión se ha cerrado porque la contraseña cambió. Inicia sesión de nuevo.», `registrada` «Cuenta creada. Inicia sesión para continuar.», `restablecida` «Contraseña actualizada. Inicia sesión con la nueva.»; se lee en `afterNextRender` (la página se prerenderiza sin query). |
| **`register`** (`/register`) | `username` (3-80), `email`, `password` (≥ 8 puntos de código, ≤ 72 bytes), `confirm_password` (igual a `password`). No hay campo de rol. | Envía `auth.register({username, email, password})`. 201 → `auth.login({email, password}, false)` → `/inicio` (EP-02-F2); si ese login falla → `/login?motivo=registrada`. 409 → bajo `email` o `username` según el texto exacto (otro texto: aviso general). 422 → `fields` bajo su campo (`password_too_long` bajo la contraseña). Enlace «¿Ya tienes cuenta? Inicia sesión». |
| **`forgot-password`** (`/forgot-password`) | `email` (obligatorio, formato). | Envía `auth.forgotPassword(email.trim())`. 202 → oculta el formulario y muestra el `message` de la API en un aviso `role="status"` con enlace «Volver a iniciar sesión»: **idéntico exista o no la cuenta** (no hay otra rama que dependa de la existencia). 422 → error del campo; red/5xx → aviso general y el formulario sigue activo. |
| **`reset-password`** (`/reset-password?token=…`) | `new_password` (mismas reglas que el registro) y `confirm_password`. El token no es un campo. | En `afterNextRender` lee `queryParamMap.get('token')` a un `signal` y **lo quita de la URL** con `router.navigate([], { queryParams: { token: null }, queryParamsHandling: 'merge', replaceUrl: true })`. Sin token (o vacío) → estado `enlace_no_valido` («El enlace no es válido o ya se ha utilizado. Solicita uno nuevo.») con botón a `/forgot-password`, sin llamar a la API; recargar la página tras quitarlo lleva a este estado. Envía `auth.resetPassword(token, new_password)`. 200 → estado `hecho` (mensaje de la API, enlace «Iniciar sesión» → `/login?motivo=restablecida`) y `auth.clearSession()` (sin aviso). 400 `invalid_token`/`expired_token` → panel con el `message` de la API y botón «Solicitar un enlace nuevo»; el formulario se oculta. 422 → error bajo `new_password` y **el token se conserva** para reintentar. Red/5xx → aviso general. |
| **`inicio`** (`/inicio`, privada) | Sin formulario. | Muestra usuario, correo y rol (`admin` → «Administrador», `user` → «Usuario») leídos de `auth.user()`, y el botón «Cerrar sesión» (`auth.logout()` + `/login`). Es un marcador del panel futuro: sin datos de dominio ni opciones por rol. |

### 6.10 SSR, hidratación y seguridad del Front
- **Sin APIs del navegador en el servidor:** `window`, `document`, `localStorage` y `sessionStorage` no existen en Node (`TextEncoder` sí). Todo acceso a almacenamiento pasa por `TokenStorageService` (con `isPlatformBrowser`). Prohibido tocar almacenamiento o la URL en constructores o `ngOnInit` de pantallas prerenderizadas; usar `afterNextRender`.
- Durante `ng build` se prerenderizan `/login`, `/register` y `/forgot-password`: sus componentes, `AuthService` y los guards deben poder ejecutarse en Node sin sesión y **sin llamar a la API**.
- Las rutas `Client` no ejecutan componentes ni guards en el servidor (devuelven el cascarón CSR): `/inicio` y `/reset-password` solo corren en el navegador. La sesión nunca se serializa a HTML ni al estado de transferencia.
- Un usuario con sesión que abre `/login` ve un instante el formulario prerenderizado antes de que `guestGuard` lo lleve a `/inicio` (aceptado: ocurre una vez tras `restoreSession`).
- **XSS:** sin `innerHTML`, `bypassSecurityTrust*` ni terceros en las pantallas de auth (el refresh token en `localStorage` es legible por un script inyectado: riesgo aceptado y mitigado, ver ADR-002). **CSRF:** no aplica (el token va en `Authorization`, la API no usa cookies).
- **Token de reseteo:** solo en memoria tras leerlo; fuera de la URL (`replaceUrl`), de `console`, de `localStorage`/`sessionStorage` y de cualquier log; `Referrer-Policy: no-referrer` (meta global y cabecera de la ruta) y `Cache-Control: no-store`. El Front no añade log de URL ni de query en `server.ts`. Queda el residuo conocido: la petición inicial `GET /reset-password?token=…` llega al servidor del Front (un proxy delante podría registrarla) y el historial global del navegador puede conservarla; se acepta por la caducidad de 30 minutos y el un solo uso. Mover el token al fragmento `#token=` lo eliminaría y exigiría cambiar `build_password_reset_url` (la decisión del usuario fija hoy `?token=`: backlog si quiere endurecerlo).
- **Open redirect:** `returnUrl` solo pasa por `sanitizeReturnUrl` (§6.4).
- **Cabeceras de seguridad** (CSP, `X-Content-Type-Options`, etc.) y sincronización entre pestañas (evento `storage`): backlog; un cierre de sesión en otra pestaña se nota en el siguiente refresco (el refresh token se lee del almacén en cada refresco, no se cachea).

### 6.11 Entradas de ARQ-003 (resueltas)
- Enlace de reseteo `{FRONTEND_BASE_URL}/reset-password?token=<token>`: se **mantiene** la forma con query (decisión del usuario); ruta `reset-password` con el token en el query param `token` (§6.4 y §6.9). Sin cambio en `build_password_reset_url`.
- ADR-006: `/reset-password` en `Client`; el Front quita el token de la URL tras leerlo; `Referrer-Policy: no-referrer`.
- ADR-002: el rol **no** va en el JWT; tras el login el Front llama a `/me`. Un 401 «Token revocado» limpia la sesión (`motivo=revocada`). El reseteo no inicia sesión: el Front va a `/login?motivo=restablecida`.
- ADR-001: el 422 deja de hacer eco de `input` (API-005) y el Front ignora `input`/`msg` en cualquier forma. BUG-004 queda cubierto por el handler (§3, VE-xx de §7.8).
- La pantalla de registro no envía rol (el contrato lo ignora de todos modos).

## 7. Criterios de verificación (para QA y Developer)
Niveles: **U** = unitario del Developer (`api/tests/unit/`, con `engine`, `db_session` o funciones puras); **I** = integración de QA con `TestClient` y las fixtures existentes (`client`, `engine`, `db_session`; `api/tests/conftest.py`); **S** = subproceso de QA con `DATABASE_URL` temporal. Todos los tests usan la BD temporal; **ninguno abre `api/data/app.db`**. Se asertan `status`, `error.code` y claves (y, tras API-005, `error.fields[...]` del 422), no el cuerpo completo. Tokens y contraseñas se truncan en los informes.

**Utilidades de prueba (patrones, sin código de producción):**
- **Token en claro:** nunca lo devuelve la API. Con `DEBUG=true` (así lo fija el conftest) se obtiene de `caplog` (`caplog.set_level(logging.INFO, logger="app.mail")`) con la expresión `token=([A-Za-z0-9_-]+)`; alternativa: `monkeypatch.setattr` de `mail.get_mail_sender` por un espía. `TestClient` ejecuta la tarea en segundo plano antes de devolver la respuesta, así que el token ya existe al volver de `client.post`.
- **Tiempo sin esperar 30 minutos:** en U se pasa `now=` a `create_password_reset` y `reset_password`; en I se reescribe `expires_at` de la fila con `db_session` (`expires_at = ahora - 1 s`) y se hace `commit`. Nunca `sleep`.
- **P-1, ruta solo-admin:** el test crea su propia `FastAPI()`, llama a `register_exception_handlers(app)`, monta el `router` de auth, añade `app.add_api_route("/solo-admin", lambda: {"ok": True}, dependencies=[Depends(require_role(UserRole.ADMIN))])` y sobrescribe `get_db` con la sesión de `engine`. Los usuarios y el rol se siembran con `db_session` o con `ensure_initial_admin`.

### 7.1 Roles (US-04)
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| RL-01 | `register` válido | 201; `role == "user"`; fila con `role = 'user'`; sin `hashed_password` ni `token_version` en el cuerpo | I |
| RL-02 | `register` con `"role": "admin"` (y variantes `"Role"`, `"is_admin": true`, `"is_active": false`) | 201 con `role == "user"` y `is_active == true`; el campo se ignora; la fila es `user` | I |
| RL-03 | Esquema de `register` | `"role" not in UserCreate.model_fields`; en `/openapi.json`, `UserCreate.properties` sin `role` ni `is_active` | U/I |
| RL-04 | El primer usuario registrado en una BD vacía | Es `user`, no `admin` | I |
| RL-05 | `GET /me` | `role` de la BD: `"user"` y, para un admin sembrado, `"admin"` | I |
| RL-06 | Ruta P-1 | Sin token 401 (con `WWW-Authenticate`); `user` → 403 `{"error": {"code": "forbidden", "message": "No tienes permisos para realizar esta acción"}}` sin `WWW-Authenticate`; `admin` → 200; token de `admin` inactivo → 401 | I |
| RL-07 | El rol cambia en la BD (`user` → `admin`) con el **mismo** access token | Pasa de 403 a 200; los claims del JWT no contienen `role` | I |
| RL-08 | `require_role()` sin roles | `ValueError` al declararla | U |
| RL-09 | `CHECK` | `INSERT`/`UPDATE` con `role = 'root'` → `IntegrityError`; insertar sin `role` (SQL crudo) deja `'user'` | U |
| RL-10 | `UserRole` | `StrEnum` con exactamente `admin` y `user` | U |

### 7.2 Migración (ADR-005, OPS-003)
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| MG-01 | BD «anterior» (DDL congelado de §2.3) con 2 usuarios; `run_migrations(engine)` | Mismas filas (`id`, `username`, `email`, `hashed_password`, `is_active`, `created_at` idénticos); `role == 'user'` y `token_version == 0` en ambas; `verify_password` sobre el hash conservado sigue siendo verdadero | U |
| MG-02 | Segunda llamada a `run_migrations` | Sin error ni cambios (idempotente) | U |
| MG-03 | BD nueva (`create_all` + `run_migrations`) | Columnas presentes; `PRAGMA table_info(users)` de `role` y `token_version` (tipo, `notnull`, `dflt_value`) igual al de la BD anterior migrada; los índices únicos de `username` y `email` siguen | U |
| MG-04 | `CHECK` tras migrar | `UPDATE users SET role = 'root'` → `IntegrityError` | U |
| MG-05 | BD sin tabla `users` | `run_migrations` no falla ni crea nada | U |
| MG-06 | Carrera: `ALTER` falla con `OperationalError` pero la columna ya existe | Se ignora; otra causa se relanza | U |
| MG-07 | `init_db()` real sobre una copia temporal de la BD anterior (`DEBUG=true`, `DATABASE_URL` temporal, `cwd` = `api/`) | Salida 0; columnas y filas como MG-01; segunda ejecución sin cambios | S |
| MG-08 | Cierre de épica (PM) | `api/data/app.db` conserva su fecha de modificación | PM |

### 7.3 Primer administrador (`ensure_initial_admin`)
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| AD-01 | Variables vacías | `"unchanged"`; 0 usuarios | U |
| AD-02 | Variables parciales (solo email; email y usuario sin contraseña…) | `RuntimeError` con los nombres que faltan; sin valores; BD sin cambios | U |
| AD-03 | Contraseña de 7 caracteres, de 73 bytes (`"a"*71+"ñ"`), email inválido, usuario de 2 caracteres | `RuntimeError` con el nombre de variable y el `type`; **no** contiene la contraseña; `exc.__cause__ is None` y `exc.__suppress_context__` | U |
| AD-04 | BD sin admin ni ese usuario | `"created"`: `role == admin`, activo, email en minúsculas, `verify_password(contraseña, hash)`; después `login` 200 y `/me` con `role == "admin"` | U/I |
| AD-05 | Segunda llamada con las mismas variables | `"unchanged"`; un solo usuario; el hash no cambia | U |
| AD-06 | Existe un `user` con ese email y no hay admins | `"promoted"`; solo cambia `role`; la contraseña anterior sigue valiendo y la de la variable no; usuario e `is_active` iguales | U |
| AD-07 | Ya hay otro admin y el email de la variable es de un `user` | `"unchanged"`; ese `user` no se promueve | U |
| AD-08 | El `username` es de otro usuario (otro email) | `RuntimeError`; BD sin cambios | U |
| AD-09 | Email de la variable con mayúsculas y usuario previo en minúsculas | Misma cuenta (AD-06 o AD-05 según el caso) | U |
| AD-10 | Secreto | Ni los logs capturados (`caplog` a DEBUG) ni `repr(settings)` contienen la contraseña; `Settings(debug=False, secret_key="", initial_admin_password="Clave-Secreta-123")` lanza `ValidationError` cuyo `str()` no la contiene | U |
| AD-11 | La suite no hereda variables | Con el conftest, `settings.initial_admin_*` están vacías aunque el shell las defina | U |

### 7.4 Recuperación de contraseña (US-03)
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| PR-01 | `forgot` con email de un usuario activo | 202 con el cuerpo exacto de §3; 1 fila del usuario: `token_hash` de 64 hex, `used_at is None`, `expires_at - created_at == 30 min` (±1 s); `sha256(token del log) == token_hash` y `token != token_hash` | I |
| PR-02 | `forgot` con email inexistente, de usuario inactivo y con mayúsculas | 202 igual; 0 filas para inexistente e inactivo; el email con mayúsculas crea la fila del usuario | I |
| PR-03 | Uniformidad | Estado, cuerpo JSON y conjunto de cabeceras idénticos entre email existente, inexistente e inactivo | I |
| PR-04 | Sin enumeración por tiempo (estructural, no se mide el reloj) | `monkeypatch` de `services.process_forgot_password` por un espía: se llama **una vez** con el mismo tipo de argumentos para existente e inexistente y la respuesta no depende de él; con la función real y `create_password_reset` parcheada para lanzar `RuntimeError`, la respuesta sigue siendo 202 y el log solo contiene `RuntimeError` | I |
| PR-05 | Dos `forgot` seguidos del mismo usuario | 1 fila; el token 1 → 400 `invalid_token`; el token 2 → 200 | I |
| PR-06 | Reseteo feliz | 200 `{"message": ...}`; `login` con la nueva 200 y con la antigua 401 `unauthorized`; `used_at` no nulo; `hashed_password` cambiado; sin tokens en la respuesta | I |
| PR-07 | Mismo token dos veces | La segunda: 400 `invalid_token`; la contraseña de la segunda petición no funciona en `login` | I |
| PR-08 | Caducado | Con `expires_at` en el pasado: 400 `expired_token`; contraseña sin cambios; `used_at` sigue nulo. Límite con `now=`: creación + 29 min 59 s válido; creación + 30 min exactos → `expired_token` | I/U |
| PR-09 | Token inválido | `"abc"`, 43 caracteres aleatorios y el token válido con un carácter cambiado → 400 `invalid_token`; `token: ""` o de 257 caracteres → 422; faltan campos → 422 | I |
| PR-10 | Contraseña nueva | 7 caracteres → 422 `string_too_short` (**ADR-001/API-005:** se asierta `error.fields[0].code`, `.loc` y `.ctx`; `detail[0].type/loc/ctx` solo valen antes de API-005); `"a"*71+"ñ"` (73 bytes) y `"ñ"*40` → 422 `password_too_long` (`loc == ["body","new_password"]`, `ctx == {"max_bytes": 72}`, nunca 500); 72 bytes exactos → 200. Tras un 422 **el token sigue siendo válido** (un reseteo correcto posterior funciona) | I |
| PR-11 | Usuario desactivado tras pedir el enlace | `reset` → 400 `invalid_token`; contraseña sin cambios | I |
| PR-12 | Carrera de consumo | Dos sesiones: la 1 lee la fila, la 2 consume el token, la 1 intenta consumir → `InvalidTokenError`; la contraseña no cambia dos veces | U |
| PR-13 | Fugas | Ninguna respuesta de `forgot`/`reset` (202, 200, 400, 422) contiene el token, `token_hash`, su valor ni `$2b$`; `/openapi.json` sin campo de respuesta con token | I |
| PR-14 | Revocación (ADR-003) | Tokens A (access y refresh) del login previo; tras el reseteo `GET /me` con A → 401 «Token revocado» y `POST /refresh` con A → 401; un `login` nuevo da tokens B válidos, con claim `tv == 1`; un token fabricado **sin** `tv` es válido con `token_version == 0` | I |
| PR-15 | Un `refresh` normal | Devuelve par nuevo y el refresh anterior sigue siendo válido (limitación aceptada, ADR-003) | I |
| PR-16 | Sin sesión tras el reseteo | La respuesta de `reset` no contiene `access_token` ni `refresh_token` | I |
| PR-17 | Hash del token | `hash_reset_token` es SHA-256 hex determinista de 64 caracteres; tokens generados de 43 caracteres `[A-Za-z0-9_-]` y distintos entre llamadas | U |

### 7.5 Enlace solo en modo desarrollo (US-03)
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| LK-01 | `settings.debug = True`, `forgot` de un usuario activo | Exactamente 1 registro INFO del logger `app.mail` con `http://localhost:4200/reset-password?token=<43 caracteres>` y el email | I |
| LK-02 | `monkeypatch.setattr(settings, "debug", False)`, mismo caso | 202; la fila existe; **ningún** registro de `app.mail` y `caplog.text` sin `reset-password` ni `token=` | I |
| LK-03 | `get_mail_sender()` | `LogMailSender` con `debug=True`, `NullMailSender` con `False`, evaluado en cada llamada; `LogMailSender().send_password_reset(...)` con `debug=False` no emite nada (defensa en profundidad) | U |
| LK-04 | `FRONTEND_BASE_URL="https://app.example.com/"` | Enlace `https://app.example.com/reset-password?token=...` sin doble barra; `FRONTEND_BASE_URL="ftp://x"` → `ValidationError` de `Settings` | U |
| LK-05 | Contraseñas en logs | Ni `forgot` ni `reset` escriben `new_password` en `caplog` | I |

### 7.6 Seguridad y contrato transversal
- **SC-01** Ninguna respuesta de los endpoints de auth contiene `hashed_password`, `token_version`, `token_hash` ni un hash bcrypt.
- **SC-02** `/openapi.json` coincide con §5 y `UserCreate.password` no cambia (`minLength: 8`, sin `maxLength`, descripción con «72 bytes»).
- **SC-03** Ningún caso devuelve 500 (BUG-004, sustitutos Unicode aislados en el JSON, queda cubierto por ADR-001/API-005: VE-03 de §7.8; hasta API-005 sigue excluido).
- **SC-04** `forgot` y `reset` no requieren `Authorization`; `GET` sobre ellos → 405.
- **SC-05** Preflight `OPTIONS` de `forgot` y `reset` desde `http://localhost:4200` → CORS permitido (el middleware actual).
- **SC-06** Regresión: `python -m pytest` completo en verde (los 189 tests existentes más los nuevos). Si `hide_input_in_errors` obliga a ajustar un test de `test_config.py`, el Developer lo anota en su entrega.

### 7.7 Front (Angular; ARQ-004)
Niveles: **U** = Vitest del Developer (`*.spec.ts` junto a cada pieza; `ng test`, jsdom, `provideHttpClientTesting`); **B** = `npm run build`; **S** = QA con `npm run build` y `npm run serve:ssr:web` en un puerto propio (`PORT`, nunca 4200 ni 8000, que son del usuario); **I** = QA-002 contra la API real con `DEBUG=true` y `DATABASE_URL` temporal; **M** = pasos manuales de QA en el navegador mientras no exista Playwright. Node 26.0.0 (`nvm use 26.0.0`) antes de cualquier `npm`.

**Normalizador de errores (`normalizeApiError`)**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-ER-01 | `HttpErrorResponse` con `status 0` | `ApiError` `0` · `network_error` · «No se pudo conectar con el servidor…» | U |
| FE-ER-02 | Cuerpo `{error:{code,message}}` (401, 409, 400 `invalid_token`) | `status`, `code` y `message` tal cual | U |
| FE-ER-03 | Cuerpo 422 con `error.fields` (`loc ["body","new_password"]`, `code password_too_long`) | `fields[0].field == "new_password"`, `code` correcto y `message` = texto del Front (no el de la API) | U |
| FE-ER-04 | Cuerpo `{detail:[{loc,type,msg,input,ctx}]}` (forma por defecto) | Misma salida que FE-ER-03; `JSON.stringify(apiError)` no contiene el `input` ni la contraseña de prueba | U |
| FE-ER-05 | `{detail:"Not Found"}` (404/405); 500 con texto o HTML; `null`; objeto que no es `HttpErrorResponse` | `http_404`/`http_405`; `server_error`; `unexpected_error`; el normalizador nunca lanza | U |
| FE-ER-06 | `loc ["body"]` y `loc ["body","a",0]` | `field` `null` y `"a.0"` | U |
| FE-ER-07 | `code` sin entrada en la tabla | «Valor no válido.» | U |

**`TokenStorageService`**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-TK-01 | `set(t, true)` y `set(t, false)` | Solo en `localStorage` / solo en `sessionStorage` (clave `auth.refresh_token`); `get` lo devuelve; `clear` vacía ambos | U |
| FE-TK-02 | `update(t)` | Reescribe en el almacén donde estaba | U |
| FE-TK-03 | Plataforma servidor (`PLATFORM_ID = 'server'`) | `get()` es `null`, `set`, `update` y `clear` no lanzan ni tocan `Storage` | U |
| FE-TK-04 | `setItem` lanza (cuota o `SecurityError`) | No se propaga | U |

**`AuthService`**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-SV-01 | `login(c, remember)` | `POST {API_BASE_URL}/auth/login` con `{email, password}` y luego `GET /auth/me`; `user()` con `role`; `status 'authenticated'`; refresh en el almacén de `remember`; el access token no está en ningún `Storage` | U |
| FE-SV-02 | Login 401 «Credenciales inválidas» | `ApiError` 401; `status 'anonymous'`; nada en `Storage` | U |
| FE-SV-03 | Login correcto y `/me` falla | La sesión se descarta y el error se propaga | U |
| FE-SV-04 | `register(p)` | `POST /auth/register` con exactamente `{username, email, password}` (sin rol); no cambia `status` | U |
| FE-SV-05 | `refresh()` con 3 llamadas concurrentes; sin refresh token | **1** `POST /auth/refresh`; guarda el par nuevo en el mismo almacén; sin token → `ApiError` `no_refresh_token` sin HTTP | U |
| FE-SV-06 | `restoreSession()` | Sin token → `anonymous` sin HTTP; con token → `refresh` + `me` → `authenticated`; refresco 401 → almacén vacío; red/5xx → `anonymous` con el token conservado; dos llamadas = una ejecución; en servidor no hace nada | U |
| FE-SV-07 | `logout()` y `clearSession()` | Vacían ambos almacenes, `user()` es `null`, `status 'anonymous'`; idempotentes | U |
| FE-SV-08 | `forgotPassword` y `resetPassword` | `POST /auth/forgot-password` con `{email}` y `POST /auth/reset-password` con `{token, new_password}` | U |
| FE-SV-09 | Las cinco llamadas públicas (login, register, refresh, forgot, reset) | Llevan `PUBLIC_ENDPOINT`; sin `Authorization` | U |

**Interceptores**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-IN-01 | Petición a `API_BASE_URL` con access token; petición a otro origen | `Authorization: Bearer …` solo en la primera | U |
| FE-IN-02 | Endpoint público con 401 | Sin `Authorization` y sin refresco ni reintento | U |
| FE-IN-03 | 401 → refresco correcto → reintento | Se reintenta **una vez** con el token nuevo; un segundo 401 no vuelve a refrescar y se propaga | U |
| FE-IN-04 | Tres peticiones concurrentes con 401 | **1** `/refresh` y 3 reintentos | U |
| FE-IN-05 | El refresco falla con 401 (y con 401 «Token revocado») | `clearSession`, navegación a `/login` con `returnUrl` y `motivo=expirada` (`revocada` si el mensaje es exactamente «Token revocado»); error propagado | U |
| FE-IN-06 | El refresco falla por red o 5xx | La sesión sigue intacta; sin navegación; error propagado | U |
| FE-IN-07 | La ruta actual ya es `/login` | No navega de nuevo (sin bucle) | U |
| FE-IN-08 | Cualquier fallo HTTP llegado a un consumidor | Es un `ApiError` (orden `[apiErrorInterceptor, authInterceptor]`) | U |

**Guards, rutas y validadores**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-GD-01 | `authGuard` | Espera `restoreSession`; anónimo → `UrlTree('/login', {returnUrl})`; autenticado → `true` | U |
| FE-GD-02 | `guestGuard` | Autenticado → `UrlTree('/inicio')`; anónimo → `true` | U |
| FE-GD-03 | Plataforma servidor | `authGuard` nunca devuelve `true` (→ `/login`); `guestGuard` devuelve `true`; ninguno llama a la API | U |
| FE-GD-04 | `sanitizeReturnUrl` | Acepta `/inicio` y `/inicio?x=1`; devuelve `null` con `https://evil.com`, `//evil.com`, `/\evil.com`, `javascript:alert(1)`, cadena vacía, `null`, `/login`, `/reset-password?token=x` y valores con saltos de línea | U |
| FE-RT-01 | `app.routes.ts` | `''` → `login`; `**` → `''`; `inicio` con `authGuard`; `login`, `register` y `forgot-password` con `guestGuard`; `reset-password` sin guard; todas con `loadComponent` | U |
| FE-RT-02 | `app.routes.server.ts` | Exactamente `login`, `register` y `forgot-password` en `Prerender`; `reset-password` en `Client` con `Referrer-Policy: no-referrer` y `Cache-Control: no-store`; `**` en `Client`; `inicio` y `reset-password` nunca en `Prerender` | U |
| FE-VL-01 | `passwordMaxBytes(72)` | 72 bytes válidos y 73 → `password_too_long`: `"a".repeat(70)+"ñ"` pasa, `"a".repeat(71)+"ñ"` falla, `"ñ".repeat(36)` pasa y `"ñ".repeat(37)` falla | U |
| FE-VL-02 | `passwordMinLength(8)` | 7 puntos de código → error; 8 → válido; `"😀".repeat(4)` (4 puntos de código, 8 unidades UTF-16) → error | U |
| FE-VL-03 | `passwordsMatch` y plantillas | Distintas → error `mismatch`; ningún `input` de contraseña tiene `maxlength` | U |

**Pantallas**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-LG-01 | Enviar el login | Llama a `login` con el correo recortado, la contraseña tal cual y `rememberMe`; mientras tanto el botón está deshabilitado con «Iniciando sesión...»; `loading` vuelve a `false` y la vista se repinta (sin zona) | U |
| FE-LG-02 | Destino tras el login | `/inicio`; con `returnUrl=/inicio?x=1` válido va ahí; con `returnUrl=https://evil.com` o `//evil.com` va a `/inicio` | U |
| FE-LG-03 | Errores | 401 «Credenciales inválidas» y «La cuenta está desactivada» en un aviso `role="alert"`; 422 sobre `password` → «Credenciales inválidas»; red → mensaje de red | U |
| FE-LG-04 | Enlaces | «¿Olvidaste tu contraseña?» → `/forgot-password` y «Regístrate aquí» → `/register` (sin `href="#"`) | U |
| FE-LG-05 | `motivo` | `expirada`, `revocada`, `registrada` y `restablecida` muestran su texto; cualquier otro valor (incluido `<script>`) no muestra aviso ni se repite en la página | U |
| FE-RG-01 | Validación de cliente | Usuario de 2 o 81 caracteres, correo inválido, contraseña de 7 caracteres, de 73 bytes (`"a".repeat(71)+"ñ"`) o sin coincidencia → error bajo el campo y **ninguna llamada**; 72 bytes exactos → llamada | U |
| FE-RG-02 | Envío | Cuerpo exacto `{username, email, password}`: sin `confirm_password` ni `role`; la contraseña sin `trim` | U |
| FE-RG-03 | 201 | Login automático con `remember=false` y navegación a `/inicio`; si ese login falla → `/login?motivo=registrada` | U |
| FE-RG-04 | 409 | «El email ya está registrado» bajo `email`; «El nombre de usuario ya está registrado» bajo `username`; otro texto → aviso general | U |
| FE-RG-05 | 422 (envelope y `detail`) | `password_too_long` y `string_too_short` bajo la contraseña; campos desconocidos o `field null` → aviso general | U |
| FE-FP-01 | Email inválido | Error de campo y ninguna llamada | U |
| FE-FP-02 | 202 con dos correos distintos | Formulario oculto y `message` de la API en `role="status"`; el DOM resultante es idéntico para ambos (no depende de la existencia de la cuenta) | U |
| FE-FP-03 | 422 y red | Error del campo / aviso general; el formulario sigue activo | U |
| FE-RS-01 | Entrar con `?token=abc` | Lee el token, lo quita de la URL (`replaceUrl`, sin `token` en `location.search`) y no lo escribe en `Storage`, `console` ni el DOM | U |
| FE-RS-02 | Sin token, token vacío o recarga tras quitarlo | Estado «El enlace no es válido…» con botón a `/forgot-password`; **sin llamada** a la API | U |
| FE-RS-03 | Envío correcto | `POST` con `{token, new_password}`; 200 → mensaje de la API, `clearSession()` y enlace a `/login?motivo=restablecida` | U |
| FE-RS-04 | 400 `invalid_token` y `expired_token` | Panel con el `message` de la API y botón «Solicitar un enlace nuevo»; formulario oculto | U |
| FE-RS-05 | 422 `password_too_long` | Error bajo `new_password`; **el token se conserva**: un segundo envío válido usa el mismo token | U |
| FE-RS-06 | Validación | Igual que el registro (FE-VL-01 a FE-VL-03) | U |
| FE-IO-01 | `inicio` | Muestra usuario, correo y rol (`admin` → «Administrador», `user` → «Usuario»); «Cerrar sesión» llama a `logout()` y navega a `/login` | U |
| FE-A11Y-01 | Todas las pantallas | Cada `input` tiene `label` asociado, `aria-invalid` y `aria-describedby` cuando hay error; avisos con `role="alert"`/`role="status"`; botón `disabled` y `aria-busy` al enviar | U/M |

**SSR, hidratación y seguridad**
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| FE-SSR-01 | `npm run build` y `npm test -- --no-watch` | Sin errores ni avisos de presupuesto; se generan `login`, `register` y `forgot-password` prerenderizados | B |
| FE-SSR-02 | `serve:ssr:web`: `/login`, `/register`, `/forgot-password` | 200 con el HTML del formulario; `/`, `/inicio` y `/reset-password?token=x` devuelven el cascarón CSR (sin `<form`, sin «Hello», sin el valor del token en el HTML) | S |
| FE-SSR-03 | `/reset-password?token=x` | Cabeceras `Referrer-Policy: no-referrer` y `Cache-Control: no-store`; si no salen de `ServerRoute.headers`, middleware en `server.ts` | S |
| FE-SSR-04 | Salida del servidor SSR durante las pruebas | Sin `window is not defined`, `localStorage` ni `ReferenceError`; ninguna línea con `token=`; `server.ts` sin log de URL ni de query | S |
| FE-SSR-05 | Hidratación en el navegador | `/login` sin sesión y `/login?motivo=expirada` no producen `NG0500` ni errores de consola; con sesión guardada, `/login` acaba en `/inicio` | M |
| FE-SSR-06 | Búsqueda en `web/src/app` | `localStorage`, `sessionStorage`, `window.` y `document.` solo aparecen en `token-storage.service.ts` (dentro de `isPlatformBrowser`) y en `*.spec.ts` | U |
| FE-SEG-01 | Tras un login real | El access token no está en `localStorage` ni `sessionStorage`; solo `auth.refresh_token`: con «Recordarme» en `localStorage` (sigue en sesión al cerrar y reabrir el navegador), sin él en `sessionStorage` (una pestaña nueva no tiene sesión; recargar la misma sí la conserva) | M/I |
| FE-SEG-02 | Reseteo de contraseña con la sesión abierta en otra pestaña | La siguiente petición protegida da 401 «Token revocado» y el Front va a `/login` con el aviso `revocada` | I/M |
| FE-SEG-03 | Búsqueda en `web/src/app` | Sin `console.*` que reciba una contraseña o token; sin `innerHTML` ni `bypassSecurityTrust*` | U |
| FE-SEG-04 | Navegador en `http://localhost:4200` contra `http://127.0.0.1:8000/api` | `login`, `register`, `refresh`, `me`, `forgot-password` y `reset-password` sin errores de CORS | I/M |
| FE-SEG-05 | Flujo completo (QA-002) | Registrar → entra en `/inicio` con rol `user` → cerrar sesión → login → «Olvidé» → enlace del log de la API → reseteo → login con la nueva (la antigua falla) → el enlace reutilizado dice «ya se ha utilizado» y uno caducado (simulado en la BD temporal) dice «ha caducado» | I/M |
| FE-SEG-06 | Admin sembrado con `INITIAL_ADMIN_*` en BD temporal | `inicio` muestra «Administrador»; el Front no ofrece nada exclusivo de admin | I/M |

### 7.8 Formato del 422 (ADR-001, API-005)
| ID | Caso | Esperado | Nivel |
|----|------|----------|-------|
| VE-01 | `register` con contraseña de 73 bytes | 422 con `error.code == "validation_error"`; `error.fields[0] == {"loc": ["body","password"], "code": "password_too_long", "message": "La contraseña no puede superar los 72 bytes en UTF-8", "ctx": {"max_bytes": 72}}`; sin clave `detail` | I |
| VE-02 | Cualquier 422 de `register`, `login`, `refresh`, `forgot-password` y `reset-password` | Ninguna clave `input` en el JSON ni el valor enviado de `password`, `new_password` o `token` (cadena de prueba única) en `response.text` | I |
| VE-03 | BUG-004: `"\ud800"` (escape JSON) en `password`, `new_password`, `token`, `refresh_token` y en `email` (`"a\ud800@x.com"`); contraseña de 8 sustitutos aislados en `register` | **Nunca 500**: 422 envelope (mensaje permitido o «Valor no válido» en campos sensibles); `login` con `"\ud800"` como contraseña → 401 «Credenciales inválidas» | I |
| VE-04 | JSON mal formado, cuerpo vacío, `Content-Type` incorrecto | 422 envelope con `fields[0].loc[0] == "body"` y sin `ctx.error` | I |
| VE-05 | Campos ausentes o de tipo erróneo (`password: 123`) | `code` `missing` / `string_type` en `fields[*]` | I |
| VE-06 | Validador que lanza `ValueError` | `fields[*].ctx` sin la clave `error` (solo escalares) | U |
| VE-07 | `/openapi.json` | Las 5 operaciones con cuerpo tienen `422 → ValidationErrorResponse`; `HTTPValidationError` y `ValidationError` no existen; `/me` y `/health` sin 422; ningún esquema con `input` | I |
| VE-08 | `validation_error_response` con un `RequestValidationError` fabricado (input binario, objeto no JSON, sustitutos en `msg` y en `loc`) | Resultado serializable a UTF-8; cadenas saneadas con `?` | U |
| VE-09 | `FastAPI()` de test con `register_exception_handlers(app)` y una ruta con cuerpo (patrón P-1) | Mismo envelope | U |
| VE-10 | 404 y 405 del framework, y errores de dominio 400/401/403/409 | Sin cambios (`{"detail": ...}` y `{"error": {"code","message"}}`) | I |
| VE-11 | Regresión | `python -m pytest` completo en verde con los 3 ficheros de EP-01 ajustados (equivalencias de §3) | I |

## 8. Fuera de alcance y preguntas abiertas
- **Fuera de alcance:** envío real (SMTP) y colas de correo; verificación de email; cambio de contraseña con sesión iniciada, 2FA y bloqueo de cuentas; endpoints de logout, de gestión de usuarios y de cambio de rol; roles por granja; **rate limiting** de `login` y `forgot-password` (backlog, condición previa a un despliegue no local: por IP y por email, 429 con `Retry-After`, código `too_many_requests`, almacenamiento y cabeceras de proxy por decidir); rotación de refresh tokens con detección de reutilización (backlog de ADR-003); envelope para 404/405/500 del framework (backlog de ADR-001); cookies `HttpOnly` con BFF, CSP y cabeceras de seguridad del Front, evento `storage` entre pestañas, `roleGuard` y pantallas de admin, `environment` de producción (backlog de ADR-002 y EP-02-F5/F7); logout en la API (EP-02-F8).
- **Preguntas abiertas de negocio:** ninguna. Supuestos de producto/UX que ARQ-004 fija y el PM puede confirmar al cerrar la épica (reversibles, sin bloquear): «Recordarme» = sesión persistente hasta que caduque el refresh token de la API (7 días) frente a sesión de pestaña (ADR-002); destino `/inicio` (pantalla privada mínima, EP-02-F1); login automático tras el registro sin «Recordarme» (EP-02-F2).
- **ADR-001 (resuelto por ARQ-004):** handler propio del 422 con envelope y sin `input` (§3 «Formato del 422», §7.8 y [ADR-001](adr/ADR-001-errores-validacion.md)); implementa API-005. Cierra BUG-004 para el handler; queda abierto el 500 por un `username` con sustitutos aislados en el `INSERT` (backlog).
- **Riesgos nuevos:** R-10 la migración se aplica sola en el primer arranque real sobre `api/data/app.db` (aditiva, conserva filas; copia manual recomendada); R-11 `INITIAL_ADMIN_PASSWORD` en `api/.env` o en el entorno es un secreto en claro (retirar tras el primer arranque; no commitear `.env`); R-12 el mini-migrador no cubre borrados, renombrados ni cambios de tipo (criterios de paso a Alembic en ADR-005); R-13 el token va en la URL del enlace (Referer, historial y logs del servidor SSR): mitigado por ARQ-004 con `Client`, `Referrer-Policy`, `Cache-Control: no-store` y quitar el token de la URL (residuo: la petición inicial y el historial del navegador; ver §6.10); R-14 el reseteo no es utilizable fuera de `DEBUG=true` hasta que exista SMTP; **R-15** (ARQ-004) el refresh token en `localStorage`/`sessionStorage` es legible por XSS (ADR-002, mitigaciones y backlog de cookies `HttpOnly`); **R-16** (ARQ-004) la plantilla de bienvenida de `app.html` y el componente `App` actual rompen todas las rutas y `app.spec.ts` hasta que WEB-001 los limpie (§6.1); **R-17** (ARQ-004) API-005 cambia el contrato aprobado del 422 y toca 3 ficheros de tests de EP-01 (QA los revisa en QA-003); **R-18** (ARQ-004) la aplicación es sin zona: el estado asíncrono en campos planos no repinta (§6.1).
- **Supuestos registrados:** el motor es SQLite (`ALTER TABLE ... ADD COLUMN` con `NOT NULL DEFAULT` y `CHECK` de columna; el Developer comprueba `sqlite3.sqlite_version` y lo anota); un `DEBUG=true` en un entorno compartido también escribe enlaces en el log.

## 9. Replanificación (para el PM, que edita `tasks/`)
**Orden propuesto:** ARQ-003 → OPS-003 → API-002 → API-004 → API-003 → QA de API → (ARQ-004 en paralelo) → WEB-001..003 → QA-002.

| Tarea | Ficheros nuevos | Ficheros modificados | Depende de | Tamaño |
|-------|-----------------|----------------------|------------|--------|
| **OPS-003** migraciones (ADR-005) | `api/app/core/migrations.py`, `api/tests/unit/test_migrations.py` | `api/app/core/database.py` (`init_db` llama a `run_migrations`). **Sin `requirements.txt`** | ARQ-003 | S |
| **API-002** roles y primer admin | `api/tests/unit/test_roles.py`, `api/tests/unit/test_initial_admin.py` | `api/app/modules/auth/entities.py` (`UserRole`, `role`, `token_version`, `CheckConstraint`), `schemas.py` (`UserRead.role`), `services.py` (`register_user`, `ensure_initial_admin`), `api/app/core/security.py` (`require_role`), `api/app/core/config.py` (`INITIAL_ADMIN_*`, `hide_input_in_errors`), `api/main.py` (lifespan), `api/tests/conftest.py` (vaciar `INITIAL_ADMIN_*`), `api/tests/unit/test_config.py` si el cambio de errores lo exige. **`controllers.py` no cambia** | ARQ-003, OPS-003 | M |
| **API-004** (nueva) revocación por `token_version` (ADR-003) | `api/tests/unit/test_token_revocation.py` | `api/app/core/security.py` (claim `tv`, `ensure_token_is_current`, `get_current_user`), `api/app/modules/auth/services.py` (`build_tokens`, `refresh_tokens`) | API-002 | S |
| **API-003** forgot y reset | `api/app/shared/mail.py`, `api/tests/unit/test_password_reset.py`, `api/tests/unit/test_mail.py` | `api/app/modules/auth/entities.py` (`PasswordResetToken`), `schemas.py` (`NewPassword`, `ForgotPasswordRequest`, `ResetPasswordRequest`, `MessageResponse`), `services.py`, `controllers.py` (2 endpoints), `api/app/core/config.py` (`FRONTEND_BASE_URL`, `PASSWORD_RESET_EXPIRE_MINUTES`), `api/app/shared/exceptions.py` (`InvalidTokenError`, `ExpiredTokenError`). **`database.py` no cambia** (la entidad se registra al importar `entities`) | ARQ-003, API-002, API-004 | M |
| **QA de API** (nueva, propuesta; sustituye la parte API de QA-002) | `api/tests/integration/test_roles.py`, `test_password_reset.py`, `test_initial_admin.py`, `test_migration_init_db.py` (subproceso) | — | API-003 | M |
| **QA-002** (flujo API-Web) | `api/tests/integration/test_auth_flow.py` | — | QA de API, WEB-002, WEB-003 | M |

Notas: (1) API-003 puede fusionar API-004 si el PM prefiere menos tareas (M alto); separarla mantiene cada entrega pequeña. (2) Documentar las variables nuevas (`INITIAL_ADMIN_*`, `FRONTEND_BASE_URL`, `PASSWORD_RESET_EXPIRE_MINUTES`) en `api/.env.example` (solo comentarios, sin valores) y en el README es opcional y de decisión del PM. (3) Al cerrar API-002 y API-003 el PM actualiza «Estado actual y huecos conocidos» de `AGENTS.md` (roles, reseteo, sin rate limiting, `tv`). (4) Ningún agente arranca la API contra `api/data/app.db` (R-10). (5) Las tareas `WEB-*` leen §3 y §6, no la implementación.

### 9.1 Replanificación del Front y del formato del 422 (ARQ-004; el PM edita `tasks/`)
**Orden propuesto (serie):** … → API-003 → **API-005** → QA-003 → WEB-001 → **WEB-004** → WEB-002 → WEB-003 → QA-002. WEB-001 no depende de API-005 (el normalizador acepta ambas formas); API-005 va antes de QA-003 para que QA escriba contra la forma final. Cada tarea WEB añade sus entradas en `app.routes.ts` y en `app.routes.server.ts` **junto con su ruta** (una entrada de servidor para una ruta inexistente puede avisar o fallar en el build).

| Tarea | Ficheros nuevos | Ficheros modificados | Depende de | Tamaño |
|-------|-----------------|----------------------|------------|--------|
| **API-005** (nueva) handler del 422 (ADR-001) | `api/app/shared/validation.py`, `api/tests/unit/test_validation_errors.py` (VE-06, VE-08, VE-09) | `api/app/shared/exceptions.py` (registrar el handler), `api/app/modules/auth/controllers.py` (`responses={422: ...}` en las 5 operaciones con cuerpo). **Ajuste mecánico de EP-01** (excepción documentada a la propiedad de tests, para no dejar `pytest` en rojo entre tareas; QA lo revisa en QA-003): `api/tests/integration/helpers.py` (`comprobar_422_password`: `error.fields[0]`, `code`, `message`), `api/tests/integration/test_register_password_bytes.py` (los dos usos de `detail[0]`) y `api/tests/integration/test_seguridad_y_contrato.py` (el `$ref` del 422 pasa a `ValidationErrorResponse`) | ARQ-004, API-003 | S |
| **QA-003** (cambia) | `api/tests/integration/test_validation_errors.py` (VE-01 a VE-05, VE-07, VE-10) | sin cambios de ficheros, pero PR-10 y SC-03 se asertan con el envelope | API-005 | M |
| **WEB-001** (cambia: «Base de sesión», se recomienda **dividirla** para no dejar una L) | `web/src/environments/environment.ts`; `core/config/api-base-url.ts`; `core/http/api-error.ts`, `validation-messages.ts`, `api-error.interceptor.ts`; `core/auth/auth-context.ts`, `auth.interceptor.ts`, `auth.guard.ts`, `return-url.ts`; `modules/auth/models/auth.models.ts`; `modules/auth/services/auth.service.ts`, `token-storage.service.ts`; `modules/auth/validators/password.validators.ts`; el `*.spec.ts` de cada pieza (FE-ER, FE-TK, FE-SV, FE-IN, FE-GD, FE-VL) | `web/src/app/app.config.ts` (`provideHttpClient(withFetch(), withInterceptors([apiErrorInterceptor, authInterceptor]))`), `app.routes.ts` (`''`, `login` con `guestGuard`, `**`), `app.routes.server.ts` (solo `login` en `Prerender` y `**` en `Client`), `app.ts`, `app.html`, `app.css`, `app.spec.ts` (§6.1), `web/src/index.html` (`lang="es"`, título, meta `referrer`) | ARQ-004 | L (M si se divide) |
| **WEB-004** (nueva) login real, pantalla de inicio y cierre de sesión | `web/src/app/modules/inicio/inicio/inicio.component.{ts,html,css}` y `inicio.component.spec.ts`; `login.component.spec.ts` | `web/src/app/modules/auth/login/login.component.ts` y `.html` (§6.9; **sin** tocar todavía los dos enlaces), `web/src/app/app.routes.ts` (ruta `inicio` con `authGuard`) | WEB-001 | S |
| **WEB-002** registro | `web/src/app/modules/auth/register/register.component.{ts,html,css}` y `.spec.ts` | `web/src/app/app.routes.ts` y `app.routes.server.ts` (`register`, `Prerender`), `login.component.ts` (importar `RouterLink`) y `login.component.html` (enlace «Regístrate aquí» → `/register`) | WEB-004 | M |
| **WEB-003** forgot y reset | `web/src/app/modules/auth/forgot-password/forgot-password.component.{ts,html,css}`, `reset-password/reset-password.component.{ts,html,css}` y sus `.spec.ts` | `web/src/app/app.routes.ts` y `app.routes.server.ts` (`forgot-password` en `Prerender`; `reset-password` en `Client` con las cabeceras de ADR-006), `login.component.html` (enlace «¿Olvidaste tu contraseña?» → `/forgot-password`), `web/src/server.ts` **solo si** `ServerRoute.headers` no emite las cabeceras en una ruta `Client` | WEB-002 | M |
| **QA-002** (cambia) | `api/tests/integration/test_auth_flow.py`; informe con los casos FE-SSR, FE-SEG y FE-A11Y de §7.7 | — | QA-003, WEB-003 | M |
| **OPS-004** (opcional, P2, backlog) e2e con Playwright | `web/` (dependencia y config de e2e) | — | WEB-003 | S |

Notas: (1) Los criterios `FE-*` de nivel **U** son del Developer en cada tarea WEB; QA-002 cubre los S, I y M. (2) Tras API-005 el PM actualiza en `AGENTS.md` la línea de «Estado actual» sobre el formato del 422 y, tras las tareas WEB, la del Front (ya hay `provideHttpClient`, interceptores, servicios, guards y rutas). (3) `base-tests-password.md` conserva el texto histórico de `detail` (superado por ADR-001 cuando API-005 esté hecha). (4) Dependencias npm nuevas: ninguna (`@angular/forms`, `@angular/router` y `rxjs` ya están). (5) Ningún agente arranca la API contra `api/data/app.db` ni usa los puertos 4200 y 8000 del usuario (R-10).
