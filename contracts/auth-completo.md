# Contrato · auth-completo (EP-02)
**Estado:** aprobado   **Alcance:** Ambos
**Historias:** US-01, US-02, US-03, US-04   **Tareas:** OPS-003, API-002 a API-008, WEB-001 a WEB-015, QA-002 a QA-007

Formato corto (migrado el 2026-11-13): solo lo que comparten varias tareas; el detalle de cada una va en su `spec` y `acceptance`. El OpenAPI real se genera del código y debe coincidir con §3. Módulo ya implementado: [auth.md](auth.md). Contrato anterior (101 KB, solo consulta): `auth-completo.old.md`.

Decisiones del usuario (no se reabren): enlace de reseteo solo en el log y solo con `DEBUG=true`; token de 30 minutos y de un solo uso; registro directo sin verificación de email; roles `admin` y `user` (el registro público siempre crea `user`); primer admin por variables de entorno; el esquema de `users` conserva los datos.

## 1. Decisiones
ADR aplicables (todos aceptados, en `contracts/adr/`): [ADR-001](adr/ADR-001-errores-validacion.md) 422 con envelope sin `input` (§3.5, §5.4); [ADR-002](adr/ADR-002-tokens-front.md) access en memoria y refresh en `localStorage` (Recordarme) o `sessionStorage` (§5.3); [ADR-003](adr/ADR-003-refresh-tokens.md) revocación global con `users.token_version` y claim `tv`, sin rotación (§3.3); [ADR-004](adr/ADR-004-password-bytes.md) contraseña de 8 caracteres a 72 bytes UTF-8; [ADR-005](adr/ADR-005-migraciones.md) migraciones mínimas aditivas e idempotentes (§2.3); [ADR-006](adr/ADR-006-rendermode.md) `Prerender` solo en `login`, `register` y `forgot-password` (§5.2); [ADR-007](adr/ADR-007-roles.md) roles globales en `users.role`, fuera del JWT (§2.1, §3.4); [ADR-011](adr/ADR-011-recuperacion-password.md) token hasheado, 30 min, un solo uso, el último pedido invalida los anteriores (§2.2, §3.1, §3.2).

| ID | Decisión local |
|----|----------------|
| D1 | El rol no va en el JWT: `/me` y `UserRead` lo leen de la BD en cada petición |
| D2 | `register` ignora cualquier `role` del body (`UserCreate` no tiene el campo) y el servicio fija `user` |
| D3 | Primer admin con `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_USERNAME` e `INITIAL_ADMIN_PASSWORD` (§4.1, §4.5) |
| D4 | `forgot-password` responde 202 sin consultar la BD; el trabajo va a `BackgroundTasks` con sesión propia sobre `db.get_bind()` (sin enumeración por tiempo; los tests, que solo sobrescriben `get_db`, ven las filas) |
| D5 | Errores del reseteo: 400 `invalid_token` y 400 `expired_token` |
| D6 | Rate limiting de `login` y `forgot-password`: backlog (condición previa a un despliegue no local; riesgo R-05) |
| F1 | Destino tras el login: `returnUrl` saneado o `/inicio` (pantalla privada mínima). Tras registrarse: login automático sin Recordarme (si falla, `/login?motivo=registrada`) |
| F2 | Pantallas nuevas con Reactive Forms tipados y `signal` (el login conserva `FormsModule`/`ngModel`); `''` → `login` y `**` → `''` |
| F3 | Sin guard de rol (el rol solo se muestra; la autorización es de la API). `/reset-password` sin `guestGuard`; tras un reseteo correcto se descarta la sesión local |
| F4 | `environment.apiBaseUrl = 'http://127.0.0.1:8000/api'` (sin `fileReplacements`). «Cerrar sesión» solo local (no hay logout en la API). `core/` solo con lo transversal; `AuthService` y `TokenStorageService` en `modules/auth/services/` |

## 2. Modelo de datos
### 2.1 `users` (columnas nuevas; ver [auth.md](auth.md) §2 para las demás)
- `role`: String(10) NOT NULL, `server_default text("'user'")`, `default` `UserRole.USER.value`, `CHECK (role IN ('admin', 'user'))` con nombre `ck_users_role`.
- `token_version`: Integer NOT NULL, `server_default text("0")`, `default` 0. Interno: nunca se serializa.
- `UserRole` es un `enum.StrEnum` (`ADMIN = "admin"`, `USER = "user"`) en `modules/auth/entities.py`. Los usuarios existentes quedan con `role = 'user'` y `token_version = 0`.

### 2.2 `password_reset_tokens` (tabla nueva; `create_all` la crea porque `init_db()` ya importa `entities`)
Columnas: `id` (Integer, PK autoincremental); `user_id` (Integer NOT NULL, FK `users.id` `ondelete=CASCADE`, índice); `token_hash` (String(64) NOT NULL, único: SHA-256 hexadecimal); `created_at` y `expires_at` (DateTime(timezone=True) NOT NULL; `expires_at = created_at + PASSWORD_RESET_EXPIRE_MINUTES`); `used_at` (DateTime(timezone=True) NULL, se rellena al consumir).
- Como máximo una fila por usuario. Se guarda el hash; el token (`secrets.token_urlsafe(32)`, 43 caracteres) solo existe en memoria y en el enlace del log de desarrollo. SQLite devuelve las fechas sin zona: en Python se tratan como UTC (`replace(tzinfo=timezone.utc)` si `tzinfo is None`); en SQL se usa `datetime.now(timezone.utc)`.

### 2.3 Migración (hecha en OPS-003, ADR-005)
`core/migrations.py` expone `run_migrations(engine)`; `init_db()` lo llama tras `create_all`. Pasos aditivos que inspeccionan el esquema (`ADD COLUMN role` con su `CHECK` y `ADD COLUMN token_version`), idempotentes. Ningún agente abre `api/data/app.db`: la migración se aplicará en el primer arranque real del usuario (se recomienda copiar la BD antes).

## 3. API
Prefijo `/api/auth`, JSON en `snake_case`. Errores de dominio: `{"error": {"code", "message"}}`. Los errores de dominio no se declaran en OpenAPI; el 422 sí (§3.5).

### 3.1 `POST /forgot-password` (público)
- Request `ForgotPasswordRequest {email}` (`EmailStr`). Response **202** `MessageResponse {"message": "Si el email está registrado, recibirás un enlace para restablecer la contraseña."}`, **idéntica** (estado, cuerpo y cabeceras) exista o no el email o esté inactiva la cuenta. Único error: 422.
- El controlador no consulta la BD: añade `BackgroundTasks.add_task(services.process_forgot_password, db.get_bind(), str(payload.email))` y responde (D4).
- La tarea busca al usuario por email sin distinguir mayúsculas; si no existe o está inactivo, no hace nada. Si está activo: borra todos sus tokens, genera el token, guarda `sha256(token)` con `expires_at = now + 30 min`, `commit` y solo después envía el enlace `{FRONTEND_BASE_URL}/reset-password?token=<token>` (§4.3). Cualquier excepción se captura y se registra solo con `type(exc).__name__`.

### 3.2 `POST /reset-password` (público; el token es la credencial)
- Request `ResetPasswordRequest {token, new_password}`: `token` de 1 a 256 caracteres; `new_password` con las reglas de `register`. Response **200** `{"message": "Contraseña actualizada. Ya puedes iniciar sesión."}` (no inicia sesión ni devuelve tokens).
- Errores: 400 `invalid_token` (no existe, ya usado, sustituido, usuario inactivo o carrera de consumo); 400 `expired_token` (`expires_at <= ahora`); 422 por `token` vacío o >256 y por `new_password` (`string_too_short` o `password_too_long` con `ctx {"max_bytes": 72}`). La validación del esquema va antes de tocar el token: una contraseña inválida **no lo consume**.
- Reglas, en una transacción: buscar por `sha256(token)`; consumo atómico `UPDATE ... SET used_at = :now WHERE id = :id AND used_at IS NULL AND expires_at > :now` (si `rowcount != 1`, rollback e `invalid_token`); cambiar `hashed_password` e incrementar `token_version` en SQL (revoca todos los tokens emitidos, ADR-003); commit.

### 3.3 `register`, `me`, `login`, `refresh`
- `register`: sin cambios de entrada; ignora `role`; **201** `UserRead` con `role: "user"`. `GET /me`: `UserRead` con `role` leído de la BD. `UserRead` no incluye `token_version` ni `hashed_password`.
- `login` y `refresh` emiten tokens con el claim `tv` (entero). `refresh` y `get_current_user` responden **401** `unauthorized` «Token revocado» si `payload.get("tv", 0) != user.token_version` (sin `tv` vale 0). Un `refresh` normal no invalida el refresh anterior (limitación aceptada de ADR-003).

### 3.4 `require_role(*roles: UserRole)` (`core/security.py`)
Fábrica de dependencias: resuelve `get_current_user` y, si `user.role` no está en `roles`, lanza `PermissionDeniedError` → **403** `forbidden` «No tienes permisos para realizar esta acción» (sin `WWW-Authenticate`); el 401 precede al 403; `require_role()` sin roles lanza `ValueError`. Sin jerarquía. No hay endpoints solo-admin en esta épica: se prueba con una ruta montada por el test.

### 3.5 Formato del 422 (ADR-001, API-005)
**422** `{"error": {"code": "validation_error", "message": "Los datos enviados no son válidos", "fields": [{"loc": ["body", "new_password"], "code": "password_too_long", "message": "La contraseña no puede superar los 72 bytes en UTF-8", "ctx": {"max_bytes": 72}}]}}`.
- `fields[i]` = `detail[i]` de Pydantic con `type → code` y `msg → message`, **sin `input`**, `url` ni objetos de error; `ctx` opcional, solo valores escalares, nunca la clave `error`.
- Toda cadena emitida se sanea con `s.encode("utf-8", "replace").decode("utf-8")` (BUG-004: sin 500 por sustitutos Unicode). Si el último elemento de `loc` es `password`, `new_password`, `token` o `refresh_token`, el `message` solo es el de Pydantic para `code` ∈ {`missing`, `string_type`, `string_too_short`, `string_too_long`, `password_too_long`}; en otro caso, «Valor no válido».
- Aplica a todos los endpoints con cuerpo y a cualquier `FastAPI()` que llame a `register_exception_handlers`. 404/405/500 y errores de dominio no cambian. OpenAPI: las 5 operaciones con cuerpo declaran `422 → ValidationErrorResponse` (API-008) y `HTTPValidationError` deja de existir.

### 3.6 Mensajes que interpreta el Front
409 `conflict`: «El email ya está registrado» o «El nombre de usuario ya está registrado»; 401 `unauthorized`: «Credenciales inválidas», «La cuenta está desactivada» y, tras un reseteo, «Token revocado» (otros 401: «El token ha expirado», «Token inválido», «Credenciales no proporcionadas»); 400 `invalid_token`: «El enlace de recuperación no es válido o ya se ha utilizado»; 400 `expired_token`: «El enlace de recuperación ha caducado».

## 4. Piezas internas
### 4.1 Configuración (`core/config.py`)
| Variable | Campo | Defecto | Reglas |
|----------|-------|---------|--------|
| `INITIAL_ADMIN_EMAIL` / `_USERNAME` | `initial_admin_email` / `initial_admin_username: str` | `""` | Se validan al arrancar (§4.5), no en `Settings` |
| `INITIAL_ADMIN_PASSWORD` | `initial_admin_password: SecretStr` | `SecretStr("")` | Solo se lee con `get_secret_value()` en `main.py`; nunca en logs ni errores |
| `FRONTEND_BASE_URL` | `frontend_base_url: str` | `"http://localhost:4200"` | Debe empezar por `http://` o `https://` (si no, `ValueError`); se quita la `/` final |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `password_reset_expire_minutes: int` | `30` | `Field(gt=0, le=1440)` |
`Settings` lleva `hide_input_in_errors=True`; `tests/conftest.py` vacía `INITIAL_ADMIN_*`.

### 4.2 Esquemas (`modules/auth/schemas.py`)
`UserRead` (+`role: UserRole`); `NewPassword` (alias `Annotated`: `Field(min_length=8)` **antes** de `AfterValidator(_check_password_bytes)` para conservar el tipo `string_too_short`), usado por `UserCreate.password` y `ResetPasswordRequest.new_password`; `ForgotPasswordRequest {email}`; `ResetPasswordRequest {token (1-256), new_password}`; `MessageResponse {message}`. `UserCreate` no tiene `role`. `LoginRequest`, `RefreshRequest` y `TokenResponse` no cambian.

### 4.3 Envío en modo desarrollo (`shared/mail.py`)
`MailSender` (Protocol `send_password_reset(to_email, reset_url)`), `LogMailSender`, `NullMailSender`, `get_mail_sender()` y `build_password_reset_url(token)`. `get_mail_sender()` devuelve `LogMailSender` **solo si `settings.debug is True`**, evaluado en cada llamada; `LogMailSender` vuelve a comprobar `debug` y escribe **una** línea INFO en el logger `app.mail`: `[DEV] Recuperación de contraseña para <email>: <reset_url>`. Fuera de debug no se escribe nada. `services.py` usa `from app.shared import mail` (módulo) para poder sustituirlo con `monkeypatch`.

### 4.4 Servicios y seguridad (nombres contractuales; firmas en la `spec` de cada tarea)
`services`: `register_user`, `hash_reset_token`, `FORGOT_PASSWORD_MESSAGE`, `create_password_reset`, `process_forgot_password`, `reset_password`, `build_tokens`. `shared/exceptions.py`: `InvalidTokenError`, `ExpiredTokenError`. `core/security.py`: claim `tv`, `ensure_token_is_current(payload, user)`, `require_role`. `shared/validation.py`: `validation_error_response(exc)` y `ValidationErrorResponse`.

### 4.5 Primer administrador (`services.ensure_initial_admin`, hecho en API-002)
Devuelve `"created"`, `"promoted"` o `"unchanged"`; `main.py` lo llama en el `lifespan` tras `init_db()`. Tres variables vacías → `unchanged`; solo algunas → `RuntimeError` con los nombres que faltan; se validan con `UserCreate` (el error solo lleva nombre de variable y `type`); si ya hay un admin → `unchanged`; si el email existe → se promueve (solo cambia `role`); si el `username` es de otro → `RuntimeError`; si no, se crea. Nunca se registra la contraseña.

## 5. Front (Angular 22, sin zone.js: todo estado asíncrono en `signal`)
### 5.1 Estructura (`web/src/app/`)
`core/` (config, http, auth: URL base, errores, interceptores, guards), `modules/auth/` (`models/`, `services/`, `validators/`, pantallas) y `modules/inicio/inicio/`. Cada pieza lleva su `*.spec.ts`. Pantallas `standalone` con `inject()`, Tailwind con el estilo del login y sin `.css` si estaría vacío.

### 5.2 Rutas, guards y `RenderMode` (cada tarea WEB añade su ruta en `app.routes.ts` y `app.routes.server.ts` a la vez)
| Path | Guard | Título | `RenderMode` |
|------|-------|--------|--------------|
| `''` → `login`; `**` → `''` | — | — | `Client` (`**`) |
| `login` | `guestGuard` | Iniciar sesión | `Prerender` |
| `register` | `guestGuard` | Crear cuenta | `Prerender` |
| `forgot-password` | `guestGuard` | Recuperar contraseña | `Prerender` |
| `reset-password` | — (F3) | Nueva contraseña | `Client` con `headers: { 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store' }` |
| `inicio` | `authGuard` | Inicio | `Client` (cubierta por `**`) |
Todas con `loadComponent`. `authGuard` y `guestGuard` (`CanActivateFn` asíncronos, esperan `restoreSession()` en el navegador): `authGuard` deja pasar al autenticado y si no devuelve `UrlTree('/login', {queryParams: {returnUrl: state.url}})` (en el servidor nunca concede); `guestGuard` lleva al autenticado a `/inicio` (en el servidor siempre `true`). `sanitizeReturnUrl(value)` solo admite rutas internas (empieza por `/`, no por `//` ni `/\`, sin esquema, `://` ni caracteres de control, y no apunta a `/login`, `/register`, `/forgot-password` ni `/reset-password`); si no cumple, `null` y el destino es `/inicio`.

### 5.3 Sesión, tokens e interceptores (ADR-002)
- `TokenStorageService` (clave `auth.refresh_token`): `get()`, `set(token, persistent)` (`localStorage` o `sessionStorage`, borrando el otro), `update(token)` (mismo almacén), `clear()`; protegido con `isPlatformBrowser` y `try/catch`.
- `AuthService`: `status` (`'unknown' | 'anonymous' | 'authenticated'`), `user`, `role`, `login(c, remember)` (login → refresh al almacén → `me()`), `register` (no inicia sesión), `refresh()` (una sola petición en vuelo), `me()`, `forgotPassword`, `resetPassword`, `logout()`/`clearSession()` y `restoreSession()` (memoizada; 401 → limpia; red o 5xx → anónimo sin borrar el token). Las 5 llamadas públicas llevan `HttpContext` `PUBLIC_ENDPOINT`.
- `apiErrorInterceptor` (más externo) convierte todo fallo en `ApiError`; `authInterceptor` añade `Authorization: Bearer` solo a URLs de `API_BASE_URL` y, ante un 401 sin `RETRIED`, hace un único `refresh()` compartido y reintenta una vez; si el refresco falla con 401, `clearSession()` y va a `/login` con `returnUrl` y `motivo` (`revocada` si el mensaje es exactamente «Token revocado», si no `expirada`); red o 5xx no cierran la sesión. Orden: `[apiErrorInterceptor, authInterceptor]`.
- Sin lecturas de almacenamiento, query ni token en el primer pase de render (SSR/hidratación): `afterNextRender` o handlers.

### 5.4 Errores (`core/http/api-error.ts`, ADR-001)
`ApiError(status, code, message, fields: FieldError[])` con `FieldError {field: string | null; code; message; ctx?}`; `normalizeApiError(err: unknown): ApiError` nunca lanza: red (`status 0`) → `network_error`; `{error:{code,message,fields?}}` → tal cual; `{detail:[...]}` → `422 validation_error` (ignora `msg` e `input`); `{detail:"..."}` → `http_<estado>`; ≥ 500 o no JSON → `server_error`; el resto → `unexpected_error`. El `message` de cada campo es siempre el texto del Front (`validation-messages.ts`). Ninguna contraseña ni token va a `console`.

### 5.5 Modelos TS (`modules/auth/models/auth.models.ts`, espejo del contrato)
`UserRole = 'admin' | 'user'`; `UserCreate {username, email, password}`; `LoginRequest {email, password}`; `RefreshRequest {refresh_token}`; `ForgotPasswordRequest {email}`; `ResetPasswordRequest {token, new_password}`; `UserRead {id, username, email, role, is_active, created_at}`; `TokenResponse {access_token, refresh_token, token_type: 'bearer', expires_in}`; `MessageResponse {message}`; `ApiFieldError {loc, code, message, ctx?}`; `ApiErrorBody {error: {code, message, fields?}}`; `SessionNotice = 'expirada' | 'revocada' | 'registrada' | 'restablecida'`.

### 5.6 Pantallas
Comunes: `<label for>` en cada `input`, `aria-invalid` y `aria-describedby` con error, avisos `role="alert"` (error) y `role="status"` (informativo), botón `disabled` y `aria-busy` al enviar; errores de campo con el control `touched` o tras intentar enviar (los de servidor se limpian al editar). Las contraseñas nunca se recortan, registran ni guardan; correo y usuario sí se recortan. Validación espejo de la API: contraseña de mínimo 8 **puntos de código** (`Array.from(value).length`) y máximo 72 **bytes** (`new TextEncoder().encode(value).length`; sin `maxlength`; `"a".repeat(70) + "ñ"` pasa y `"a".repeat(71) + "ñ"` falla); usuario de 3 a 80 caracteres. El detalle de cada pantalla (campos, flujo, errores y avisos) está en la `spec` de su tarea WEB; `inicio` muestra usuario, correo y rol (`admin` → «Administrador», `user` → «Usuario»).

### 5.7 SSR y seguridad
Sin `window`, `document`, `localStorage` ni `sessionStorage` fuera de `TokenStorageService`. El prerender no llama a la API. Sin `innerHTML` ni `bypassSecurityTrust*`. Token de reseteo: solo en memoria, fuera de la URL tras leerlo, de `console` y de los almacenes; `Referrer-Policy: no-referrer` (meta global y cabecera de la ruta) y `Cache-Control: no-store`. Los puertos 4200 y 8000 son del usuario: los agentes usan puertos propios y BD temporal; nadie toca `api/data/app.db` ni `.env`. Node 26.0.0 (`nvm use 26.0.0`) para cualquier `npm`; sin dependencias npm nuevas.

## 6. Fuera de alcance
SMTP real y verificación de email; cambio de contraseña con sesión, 2FA y bloqueo de cuentas; logout y gestión de usuarios o roles en la API; roles por granja; rate limiting de `login` y `forgot-password`; rotación de refresh tokens; envelope para 404/405/500; cookies `HttpOnly`/BFF, CSP, evento `storage` entre pestañas, `roleGuard` y pantallas de admin; e2e con Playwright.
