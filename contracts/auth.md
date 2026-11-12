# Contrato · auth
**Estado:** aprobado (as-built a 2026-11-11 tras EP-01; EP-02 pendiente de implementar, ver [auth-completo.md](auth-completo.md); diseño Web de ARQ-004 en [auth-completo.md](auth-completo.md) §6)   **Alcance:** API (implementada) · Web (diseñada por ARQ-004, sin implementar)
**Épica:** anterior al circuito de agentes (sin `EP-xx`); ampliado por EP-01 y EP-02   **Verificado contra el código:** 2026-11-11
**Tareas que desbloquea:** las `WEB-*` de EP-02 (login, registro, recuperación y sesión; ver [auth-completo.md](auth-completo.md) §9.1) y las `OPS-003`, `API-002`, `API-004`, `API-003` y `API-005` de EP-02

> Documenta el comportamiento implementado en `api/app/modules/auth/`. **EP-01 (`base-tests-password`, ADR-004), ya implementada con `API-001`:** el límite de contraseña se cuenta en bytes UTF-8 y `register` devuelve 422 `password_too_long` ([contrato de la épica](base-tests-password.md)). **EP-02 (`auth-completo`):** el contrato objetivo (recuperación de contraseña, roles `admin` y `user`, primer admin, revocación de tokens y migración de `users`) está en [auth-completo.md](auth-completo.md), que es la fuente de verdad de esas partes. Lo marcado **EP-02** abajo **aún no está implementado** y pasará a as-built cuando lo hagan esas tareas. Los puntos abiertos están en los ADR de §1. El OpenAPI de referencia es el generado en `/openapi.json`.

## 1. Decisiones (ADR)
Los ADR están indexados en [contracts/adr/README.md](adr/README.md). ADR-001, ADR-002 y ADR-006 (ARQ-004, 2026-11-11) están **aceptados**; ADR-001 cambia el formato del 422 en la API (**ADR-001/API-005, pendiente de implementar**); ADR-004 (aceptado) ya está implementado y los de EP-02 están aceptados pero sin implementar.

| ID | Tema | Estado | Afecta a |
|----|------|--------|----------|
| [ADR-001](adr/ADR-001-errores-validacion.md) | Formato de error de validación (422): envelope `{error:{code,message,fields}}` sin `input` (**ADR-001/API-005**) | **aceptado** | API (handler del 422), servicios y manejo de errores del Front |
| [ADR-002](adr/ADR-002-tokens-front.md) | Almacenamiento de tokens y "Recordarme" compatible con SSR | **aceptado** | Login Web, guards, interceptors |
| [ADR-003](adr/ADR-003-refresh-tokens.md) | Revocación de refresh tokens con `token_version` (**EP-02**) | **aceptado** | `refresh`, `get_current_user`, `reset-password` |
| [ADR-004](adr/ADR-004-password-bytes.md) | Límite de contraseña en bytes (bcrypt) | **aceptado** | `POST /api/auth/register` (422 si >72 bytes UTF-8), `POST /api/auth/login` (401 si >72 bytes, sin cambios de contrato) |
| [ADR-005](adr/ADR-005-migraciones.md) | Migraciones mínimas idempotentes para `users` (**EP-02**) | **aceptado** | `init_db()` |
| [ADR-007](adr/ADR-007-roles.md) | Roles globales `admin` y `user` (**EP-02**) | **aceptado** | `users.role`, `/me`, `require_role` |
| [ADR-011](adr/ADR-011-recuperacion-password.md) | Recuperación de contraseña (**EP-02**) | **aceptado** | `forgot-password`, `reset-password` |
| [ADR-006](adr/ADR-006-rendermode.md) | `RenderMode` por ruta del Front | **aceptado** | `app.routes.server.ts` |

## 2. Modelo de datos
Tabla `users` (`api/app/modules/auth/entities.py`):

| Columna | Tipo | Restricciones |
|---------|------|---------------|
| `id` | Integer | PK, autoincremental |
| `username` | String(80) | NOT NULL, único, indexado |
| `email` | String(120) | NOT NULL, único, indexado |
| `hashed_password` | String(255) | NOT NULL (bcrypt) |
| `is_active` | Boolean | NOT NULL, por defecto `true` |
| `created_at` | DateTime(timezone=True) | NOT NULL, por defecto la hora UTC actual |
| `role` | String(10) | **EP-02:** NOT NULL, `DEFAULT 'user'`, `CHECK (role IN ('admin', 'user'))` |
| `token_version` | Integer | **EP-02:** NOT NULL, `DEFAULT 0` (interno, no se serializa) |

- Migración: hoy ninguna (tabla creada por `create_all`). **EP-02:** `role` y `token_version` se añaden con `core/migrations.py` (ADR-005, OPS-003) conservando los usuarios, que quedan como `user`; además se crea la tabla `password_reset_tokens` ([auth-completo.md](auth-completo.md) §2.2).
- `email` se guarda en minúsculas; la unicidad de `email` y `username` se comprueba sin distinguir mayúsculas en `services.py`.

## 3. API
Prefijo global `/api`; router de auth en `/auth`. JSON en `snake_case`.

### POST /api/auth/register
- **Auth:** pública
- **Request:** `UserCreate` — `{username, email, password}`; `password`: mínimo 8 caracteres y máximo 72 **bytes** en UTF-8 (ADR-004)
- **Response 201:** `UserRead` (**EP-02:** incluye `role`, siempre `"user"`; el body no admite rol: un campo `role` enviado se ignora y no hay forma de registrarse como `admin`)
- **Errores:** 409 `conflict` ("El email ya está registrado" / "El nombre de usuario ya está registrado"); 422 validación (hoy `detail`; **ADR-001/API-005:** `error.code == "validation_error"` con `error.fields[]`, ver [auth-completo.md](auth-completo.md) §3). Con `password` de más de 72 bytes UTF-8: hoy `detail[0]` con `loc == ["body", "password"]`, `type == "password_too_long"`, `msg == "La contraseña no puede superar los 72 bytes en UTF-8"` y `ctx == {"max_bytes": 72}`; tras API-005 `error.fields[0]` con los mismos `loc` y `ctx`, `code == "password_too_long"` y `message` (ADR-004; 72 bytes se aceptan, 73 se rechazan)

### POST /api/auth/login
- **Auth:** pública
- **Request:** `LoginRequest` — `{email, password}`; `password` de 1 a 72 caracteres (cota de tamaño; sin validación en bytes, ADR-004)
- **Response 200:** `TokenResponse`
- **Errores:** 401 `unauthorized` ("Credenciales inválidas" si el usuario no existe, la contraseña es errónea o supera 72 bytes UTF-8 —nunca se autentica por truncamiento—; "La cuenta está desactivada" si la contraseña es correcta pero `is_active=false`); 422 validación (incluye más de 72 caracteres, `string_too_long`)

### POST /api/auth/refresh
- **Auth:** pública (el refresh token va en el cuerpo)
- **Request:** `RefreshRequest` — `{refresh_token}`
- **Response 200:** `TokenResponse` (nuevo par de tokens; el refresh token anterior **sigue siendo válido** tras un refresh normal: limitación aceptada, ADR-003)
- **Errores:** 401 `unauthorized` ("El token ha expirado", "Token inválido", "Tipo de token incorrecto", "Token sin sujeto", "Usuario no válido o inactivo"; **EP-02:** "Token revocado" si su claim `tv` no coincide con `users.token_version`, p. ej. tras un reseteo de contraseña); 422 validación

### GET /api/auth/me
- **Auth:** Bearer (access token)
- **Response 200:** `UserRead` (**EP-02:** incluye `role`, leído de la BD en cada petición)
- **Errores:** 401 `unauthorized` ("Credenciales no proporcionadas" y los mismos mensajes de token de arriba, con "Tipo de token incorrecto" si se envía un refresh token)

### POST /api/auth/forgot-password (EP-02, pendiente de API-003)
- **Auth:** pública. **Request:** `ForgotPasswordRequest` — `{email}`. **Response 202:** `MessageResponse`, idéntica exista o no el email o esté inactiva la cuenta (sin enumeración de cuentas ni por tiempo). **Errores:** 422 validación (`detail`; **ADR-001/API-005:** `error.fields[]`).
- Token aleatorio (256 bits) guardado hasheado (SHA-256), caduca a los 30 minutos y es de un solo uso; el último pedido invalida los anteriores. En modo desarrollo (`DEBUG=true`) el enlace `{FRONTEND_BASE_URL}/reset-password?token=...` se escribe en el log de la API (logger `app.mail`); fuera de debug no se escribe nada. Detalle en [auth-completo.md](auth-completo.md) §3 y §4.3.

### POST /api/auth/reset-password (EP-02, pendiente de API-003)
- **Auth:** pública (el token es la credencial). **Request:** `ResetPasswordRequest` — `{token, new_password}`; `new_password` con las mismas reglas que `register` (mínimo 8 caracteres, máximo 72 bytes UTF-8, `password_too_long`). **Response 200:** `MessageResponse` (no inicia sesión).
- **Errores:** 400 `invalid_token` (no existe, usado, sustituido o usuario inactivo); 400 `expired_token`; 422 validación (`detail`; **ADR-001/API-005:** `error.fields[]`; una contraseña inválida no consume el token).
- Revoca todos los tokens emitidos del usuario (`token_version + 1`, ADR-003).

### Dependencia `require_role` (EP-02, pendiente de API-002)
- `require_role(UserRole.ADMIN)` en `core/security.py`: 401 si no hay sesión válida; 403 `{"error": {"code": "forbidden", "message": "No tienes permisos para realizar esta acción"}}` si el rol no está permitido. El rol no va en el JWT. No hay endpoints solo-admin en EP-02.

### Formato de errores
- Errores de dominio: `{"error": {"code": "<code>", "message": "<mensaje en español>"}}`. Los 401 incluyen `WWW-Authenticate: Bearer`.
- Errores de validación (422): hoy el formato por defecto de FastAPI, `{"detail": [...]}`, con `input` (el valor rechazado, también contraseñas y tokens) y 500 ante un sustituto Unicode aislado (BUG-004). **ADR-001 (aceptado; implementa API-005, pendiente):** `{"error": {"code": "validation_error", "message": "Los datos enviados no son válidos", "fields": [{"loc", "code", "message", "ctx"?}]}}`, **sin `input`** y sin 500; `fields[i]` equivale a `detail[i]` con `type → code` y `msg → message`. Detalle y reglas del handler en [auth-completo.md](auth-completo.md) §3 «Formato del 422». Los 404/405 del framework (`{"detail": "Not Found"}`) y el 500 no cambian.

### Tokens
- JWT firmado con `HS256` (configurable). Claims: `sub` (id de usuario como texto), `type` (`access` | `refresh`), `iat`, `exp`, `jti`; **EP-02:** `tv` (versión de tokens del usuario; ausente equivale a `0`).
- Caducidad por defecto: access 30 min, refresh 7 días (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`). `expires_in` = segundos de vida del access token.

## 4. Esquemas Pydantic (`schemas.py`)

| Esquema | Campos y restricciones |
|---------|------------------------|
| `UserCreate` | `username` 3-80 caracteres; `email` (`EmailStr`); `password` mínimo 8 **caracteres** (`Field(min_length=8)`) y máximo 72 **bytes UTF-8** (`AfterValidator` con `exceeds_password_limit`, error `password_too_long`; sin `max_length`) (ADR-004) |
| `LoginRequest` | `email` (`EmailStr`); `password` 1-72 caracteres (sin validación en bytes: `verify_password` devuelve `False` si supera 72 bytes) |
| `RefreshRequest` | `refresh_token` (str) |
| `UserRead` | `id`, `username`, `email`, `is_active`, `created_at` (`from_attributes`); **EP-02:** `role` (`admin` \| `user`) |
| `TokenResponse` | `access_token`, `refresh_token`, `token_type` (`"bearer"`), `expires_in` (int, segundos) |
| `ForgotPasswordRequest` (**EP-02**) | `email` (`EmailStr`) |
| `ResetPasswordRequest` (**EP-02**) | `token` (1-256 caracteres); `new_password` (mismo tipo que `UserCreate.password`, ADR-004) |
| `MessageResponse` (**EP-02**) | `message` |

`hashed_password` y `token_version` nunca se serializan.

`core/security.py` (ADR-004): `exceeds_password_limit(password)` cuenta `len(password.encode("utf-8"))` frente a `MAX_PASSWORD_BYTES` (72) sin normalización Unicode; `hash_password` lanza `ValueError` y `verify_password` devuelve `False` (sin llamar a bcrypt) si se supera. Detalle en [base-tests-password.md](base-tests-password.md) §4.1.

## 5. Fragmento OpenAPI 3.1
Fuente de verdad: `/openapi.json` de la API en ejecución (rutas `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/me`; **EP-02:** `/api/auth/forgot-password` y `/api/auth/reset-password`, con el fragmento esperado en [auth-completo.md](auth-completo.md) §5). No se duplica a mano para evitar desviaciones; cualquier cambio de contrato debe reflejarse en las secciones 3 y 4 de este documento.

## 6. Front (Angular)
Estado actual: `LoginComponent` en `web/src/app/modules/auth/login/` simula la llamada con `setTimeout` y navega a `/dashboard` (ruta inexistente). No hay `HttpClient`, servicios, interceptors, guards ni rutas. **El diseño Angular (ARQ-004, ADR-001, ADR-002 y ADR-006 aceptados) está en [auth-completo.md](auth-completo.md) §6** (rutas, guards, `RenderMode`, `AuthService`, interceptores, tokens, errores y pantallas); lo de abajo son los modelos base.

**Modelos TS (espejo del contrato, `modules/auth/models/`):**
```typescript
export interface UserCreate { username: string; email: string; password: string; }
export interface LoginRequest { email: string; password: string; }
export interface RefreshRequest { refresh_token: string; }
export interface UserRead { id: number; username: string; email: string; role: UserRole; is_active: boolean; created_at: string; }  // role: EP-02
export type UserRole = 'admin' | 'user';  // EP-02
export interface ForgotPasswordRequest { email: string; }  // EP-02
export interface ResetPasswordRequest { token: string; new_password: string; }  // EP-02
export interface MessageResponse { message: string; }  // EP-02
export interface TokenResponse { access_token: string; refresh_token: string; token_type: 'bearer'; expires_in: number; }
export interface ApiErrorBody { error: { code: string; message: string } }
```

**Diseño (ARQ-004):** rutas y guards, `RenderMode`, `AuthService`, interceptores, almacenamiento de tokens, normalizador de errores (acepta el envelope de ADR-001, el `detail` por defecto, 404/405 y red), destino tras el login (`/inicio`) y tras el registro (login automático) en [auth-completo.md](auth-completo.md) §6. En esos modelos `ApiErrorBody` pasa a `{ error: { code: string; message: string; fields?: ApiFieldError[] } }` (ADR-001); el modelo de arriba es el de errores de dominio.

## 7. Criterios de verificación (para QA)
- `register` crea el usuario (201), no devuelve `hashed_password`, y rechaza duplicados de email y de usuario sin distinguir mayúsculas (409).
- `login` devuelve tokens (200); con usuario inexistente y con contraseña errónea responde 401 con el mismo mensaje; con usuario inactivo responde 401.
- `refresh` con un refresh token válido devuelve un par nuevo; con un access token, un token expirado o manipulado, o de un usuario inactivo, responde 401.
- `/auth/me` con access token válido devuelve el usuario; sin token, con token inválido o con un refresh token responde 401 con `WWW-Authenticate: Bearer`.
- Validación: email con formato inválido, `username` fuera de 3-80, `password` de menos de 8 caracteres o de más de 72 **bytes** → 422.
- Contraseñas multibyte (ADR-004), casos en [base-tests-password.md](base-tests-password.md) §7: `register` con `"ñ" * 40` (80 bytes) → 422 `password_too_long`, no 500; 72 bytes exactos → 201 y 73 → 422 (incluidos `"a" * 70 + "ñ"` → 201 y `"a" * 71 + "ñ"`, 72 caracteres y 73 bytes → 422); `login` con una contraseña de más de 72 bytes y ≤72 caracteres → 401 (mismo cuerpo que una contraseña errónea), nunca 500, y nunca autentica por truncamiento.
- Ninguna respuesta de `register`, `login` ni `/auth/me` contiene `hashed_password`.
- `/openapi.json` coincide con las secciones 3 y 4.
- **EP-02:** los criterios de roles, migración, primer admin, recuperación de contraseña y enlace en modo desarrollo (RL, MG, AD, PR, LK y SC) están en [auth-completo.md](auth-completo.md) §7.

## 8. Fuera de alcance y preguntas abiertas
- No hay endpoints de logout, cambio de contraseña (con sesión) ni gestión de usuarios. La recuperación de contraseña («¿Olvidaste tu contraseña?» está en la UI del login) está diseñada en EP-02 pero no implementada.
- Roles: **EP-02** define dos roles globales (`admin`, `user`; ADR-007); los roles y permisos por granja quedan fuera.
- Sin rate limiting de `login` ni de `forgot-password` (backlog, ADR-011).
- La pantalla de registro no existe aún en el Front (el login enlaza a "Regístrate aquí" sin destino); diseñada en [auth-completo.md](auth-completo.md) §6.9 (WEB-002).
- "Recordarme": resuelto en ADR-002 (sesión persistente hasta que caduque el refresh token frente a sesión de pestaña).
- El 422 por defecto devuelve `detail[].input` con el valor rechazado (también la contraseña): resuelto en ADR-001 (sin `input`; implementa API-005).
