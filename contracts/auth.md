# Contrato · auth
**Estado:** aprobado (as-built)   **Alcance:** API (implementada) · Web (pendiente de diseño)
**Épica:** anterior al circuito de agentes (sin `EP-xx`)   **Verificado contra el código:** 2026-11-10
**Tareas que desbloquea:** futuras `WEB-*` de login, registro y sesión (ver §8)

> Documenta el comportamiento ya implementado en `api/app/modules/auth/`; no introduce decisiones nuevas. Los puntos abiertos están en los ADR de §1. El OpenAPI de referencia es el generado en `/openapi.json`.

## 1. Decisiones (ADR)
Los ADR pendientes están indexados en [contracts/adr/README.md](adr/README.md). Ninguno cambia el comportamiento actual de la API; los dos primeros **bloquean** el diseño Web de login.

| ID | Tema | Estado | Afecta a |
|----|------|--------|----------|
| ADR-001 | Formato de error de validación (422) | pendiente | Servicios y manejo de errores del Front |
| ADR-002 | Almacenamiento de tokens y "Recordarme" compatible con SSR | pendiente | Login Web, guards, interceptors |
| ADR-003 | Rotación/revocación de refresh tokens | pendiente | `POST /api/auth/refresh` |
| ADR-004 | Límite de contraseña en bytes (bcrypt) | pendiente | `POST /api/auth/register`, `POST /api/auth/login` |

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

- Migración: ninguna (tabla creada por `create_all`).
- `email` se guarda en minúsculas; la unicidad de `email` y `username` se comprueba sin distinguir mayúsculas en `services.py`.

## 3. API
Prefijo global `/api`; router de auth en `/auth`. JSON en `snake_case`.

### POST /api/auth/register
- **Auth:** pública
- **Request:** `UserCreate` — `{username, email, password}`
- **Response 201:** `UserRead`
- **Errores:** 409 `conflict` ("El email ya está registrado" / "El nombre de usuario ya está registrado"); 422 validación (`detail`)

### POST /api/auth/login
- **Auth:** pública
- **Request:** `LoginRequest` — `{email, password}`
- **Response 200:** `TokenResponse`
- **Errores:** 401 `unauthorized` ("Credenciales inválidas" si el usuario no existe o la contraseña es errónea; "La cuenta está desactivada" si la contraseña es correcta pero `is_active=false`); 422 validación

### POST /api/auth/refresh
- **Auth:** pública (el refresh token va en el cuerpo)
- **Request:** `RefreshRequest` — `{refresh_token}`
- **Response 200:** `TokenResponse` (nuevo par de tokens; el refresh token anterior **sigue siendo válido**, ver ADR-003)
- **Errores:** 401 `unauthorized` ("El token ha expirado", "Token inválido", "Tipo de token incorrecto", "Token sin sujeto", "Usuario no válido o inactivo"); 422 validación

### GET /api/auth/me
- **Auth:** Bearer (access token)
- **Response 200:** `UserRead`
- **Errores:** 401 `unauthorized` ("Credenciales no proporcionadas" y los mismos mensajes de token de arriba, con "Tipo de token incorrecto" si se envía un refresh token)

### Formato de errores
- Errores de dominio: `{"error": {"code": "<code>", "message": "<mensaje en español>"}}`. Los 401 incluyen `WWW-Authenticate: Bearer`.
- Errores de validación (422): formato por defecto de FastAPI, `{"detail": [...]}`, sin envelope (ADR-001).

### Tokens
- JWT firmado con `HS256` (configurable). Claims: `sub` (id de usuario como texto), `type` (`access` | `refresh`), `iat`, `exp`, `jti`.
- Caducidad por defecto: access 30 min, refresh 7 días (`ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS`). `expires_in` = segundos de vida del access token.

## 4. Esquemas Pydantic (`schemas.py`)

| Esquema | Campos y restricciones |
|---------|------------------------|
| `UserCreate` | `username` 3-80 caracteres; `email` (`EmailStr`); `password` 8-72 **caracteres** (ADR-004) |
| `LoginRequest` | `email` (`EmailStr`); `password` 1-72 caracteres |
| `RefreshRequest` | `refresh_token` (str) |
| `UserRead` | `id`, `username`, `email`, `is_active`, `created_at` (`from_attributes`) |
| `TokenResponse` | `access_token`, `refresh_token`, `token_type` (`"bearer"`), `expires_in` (int, segundos) |

`hashed_password` nunca se serializa.

## 5. Fragmento OpenAPI 3.1
Fuente de verdad: `/openapi.json` de la API en ejecución (rutas `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/auth/me`). No se duplica a mano para evitar desviaciones; cualquier cambio de contrato debe reflejarse en las secciones 3 y 4 de este documento.

## 6. Front (Angular)
Estado actual: `LoginComponent` en `web/src/app/modules/auth/login/` simula la llamada con `setTimeout` y navega a `/dashboard` (ruta inexistente). No hay `HttpClient`, servicios, interceptors, guards ni rutas. El diseño detallado se hará en una tarea `ARQ-*` una vez resueltos ADR-001 y ADR-002.

**Modelos TS (espejo del contrato, `modules/auth/models/`):**
```typescript
export interface UserCreate { username: string; email: string; password: string; }
export interface LoginRequest { email: string; password: string; }
export interface RefreshRequest { refresh_token: string; }
export interface UserRead { id: number; username: string; email: string; is_active: boolean; created_at: string; }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: 'bearer'; expires_in: number; }
export interface ApiErrorBody { error: { code: string; message: string } }
```

**Pendiente de diseño (`ARQ-*`):** rutas y guards, `RenderMode` de `/login` y de las rutas privadas, servicio `AuthService`, interceptor de `Authorization` y de refresco, almacenamiento de tokens, tratamiento de las dos formas de error y destino tras el login.

## 7. Criterios de verificación (para QA)
- `register` crea el usuario (201), no devuelve `hashed_password`, y rechaza duplicados de email y de usuario sin distinguir mayúsculas (409).
- `login` devuelve tokens (200); con usuario inexistente y con contraseña errónea responde 401 con el mismo mensaje; con usuario inactivo responde 401.
- `refresh` con un refresh token válido devuelve un par nuevo; con un access token, un token expirado o manipulado, o de un usuario inactivo, responde 401.
- `/auth/me` con access token válido devuelve el usuario; sin token, con token inválido o con un refresh token responde 401 con `WWW-Authenticate: Bearer`.
- Validación: email con formato inválido, `username` fuera de 3-80, `password` fuera de 8-72 → 422.
- Casos límite a vigilar: contraseña con caracteres no ASCII que supere 72 bytes (ADR-004) no debe producir 500.
- `/openapi.json` coincide con las secciones 3 y 4.

## 8. Fuera de alcance y preguntas abiertas
- No hay endpoints de logout, recuperación de contraseña ("¿Olvidaste tu contraseña?" está en la UI del login pero no existe API), cambio de contraseña ni gestión de usuarios.
- No hay roles ni permisos por granja (ADR de roles pendiente en el índice).
- La pantalla de registro no existe en el Front (el login enlaza a "Regístrate aquí" sin destino).
- ¿Qué significa "Recordarme" (sesión persistente vs. de pestaña)? Depende de ADR-002.
