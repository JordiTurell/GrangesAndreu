# ADR-002 · Almacenamiento y refresco de tokens en el Front (compatible con SSR) y «Recordarme»
**Estado:** aceptado   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md) §6.5)

## Contexto
- La API devuelve `{access_token, refresh_token, token_type, expires_in}` en el JSON (access 30 min, refresh 7 días); no usa cookies, no hay logout ni rotación (ADR-003); el rol sale de `GET /me` (ADR-007); un reseteo revoca todos los tokens (401 «Token revocado»).
- La Web es Angular 22 con SSR e hidratación, **sin zone.js**; `outputMode: server` con un Express (`server.ts`) que solo sirve la app. En el servidor no existen `window`, `localStorage` ni `sessionStorage`.
- No hay despliegue ni dominio propio: la Web (`localhost:4200`) y la API (`127.0.0.1:8000`) son orígenes distintos con CORS (`allow_credentials=True`, sin cookies en uso).
- El login ya tiene la casilla «Recordarme».

## Opciones
| Opción | XSS | CSRF | SSR | Coste |
|--------|-----|------|-----|-------|
| A. Todo en memoria | Mejor (nada persistido) | n/a | Trivial | Cada recarga pierde la sesión; «Recordarme» imposible |
| B. Todo en `localStorage` | Un script inyectado lee ambos tokens durante 7 días | n/a | Guardas `isPlatformBrowser` | Mínimo |
| C. Todo en `sessionStorage` | Igual que B, solo la pestaña | n/a | Ídem | Sin persistencia entre sesiones |
| D. Cookies `HttpOnly` con BFF/proxy en el Express | Mejor (el JS no ve el token) | Exige `SameSite` y token anti-CSRF | El servidor SSR vería la sesión | Endpoints BFF de login/refresh/logout, proxy de `/api`, cookies seguras (HTTPS), la API no cambia pero el Front deja de hablarle directo; `ng serve` no pasa por el Express: desproporcionado ahora |
| E. **Híbrida:** access en memoria; refresh en `localStorage` (Recordarme) o `sessionStorage` | Persiste solo el refresh; el access (30 min) no se escribe en ningún sitio | n/a | Guardas `isPlatformBrowser`; servidor sin sesión | Bajo; restauración con `/refresh` + `/me` al cargar |

## Decisión
**Opción E**, con D registrada como evolución (backlog: cuando exista despliegue con HTTPS y dominio común).

1. **Dónde:** access token solo en un campo privado de `AuthService` (memoria); refresh token en `TokenStorageService` (`auth.refresh_token`). No se persiste el usuario, el rol ni el access token: tras cada carga se recuperan con `POST /refresh` y `GET /me` (el rol siempre es el vigente, ADR-007).
2. **«Recordarme»:** marcado → refresh en `localStorage`: la sesión sobrevive al cierre del navegador **hasta que caduque el refresh token de la API** (7 días por defecto; el Front no puede alargarlo) o se cierre sesión. Sin marcar → `sessionStorage`: sobrevive a recargas en la **misma pestaña** y muere al cerrarla (otra pestaña no la comparte). El registro con login automático usa «sin marcar». Cada refresco reescribe el token en el mismo almacén. Supuesto registrado: es la convención habitual de la casilla; una duración distinta (p. ej. 30 días) requeriría TTL distintos en la API y un ADR nuevo.
3. **SSR e hidratación:** el servidor no tiene sesión. `TokenStorageService` es seguro en SSR (`isPlatformBrowser`, `try/catch`, nada en constructores). `AuthService.restoreSession()` solo actúa en el navegador y es memoizada; los guards la esperan. Las rutas privadas y `/reset-password` son `Client` (ADR-006), así que no hay HTML dependiente de la sesión que pueda diferir al hidratar; lo que dependa del navegador se fija en `afterNextRender`.
4. **Refresco:** reactivo. Una petición a la API con 401 dispara `refresh()` (una sola petición en vuelo compartida entre peticiones concurrentes) y se reintenta **una vez**; no hay refresco proactivo por reloj. El access de `/me` en la carga se obtiene con el mismo `refresh()`.
5. **Fallos de sesión:** si el refresco devuelve 401 (caducado, inválido, **«Token revocado»** tras un reseteo, o inexistente) → `clearSession(motivo)`, `motivo = revocada` solo si el mensaje es exactamente «Token revocado», y navegación a `/login?returnUrl=…&motivo=…`. Un fallo de red o 5xx en el refresco **no** cierra la sesión.
6. **Seguridad:** el riesgo residual es XSS leyendo el refresh token de `localStorage`/`sessionStorage`. Mitigaciones: sin `innerHTML`/`bypassSecurityTrust*` ni scripts de terceros, plantillas escapadas por Angular, access de 30 min solo en memoria, token enviado únicamente a `API_BASE_URL`, revocación global por reseteo (ADR-003). Un script inyectado en la página podría pedir `/refresh` igualmente, por lo que ni siquiera la memoria lo evita: la defensa real es D + CSP (backlog). CSRF no aplica (cabecera `Authorization`, sin cookies).
7. **Cerrar sesión es local** (no hay endpoint): se borran ambos tokens y el estado; el refresh token robado seguiría valiendo hasta caducar (limitación de ADR-003, backlog junto a la rotación).
8. **Varias pestañas:** el refresh token se lee del almacén en cada refresco (no se cachea), de modo que un cierre de sesión en otra pestaña se nota en el siguiente refresco; sin evento `storage` (backlog).

## Consecuencias
- **Web (WEB-001):** `TokenStorageService`, `AuthService`, `authInterceptor`, guards (contrato §6.4 y §6.5).
- **API:** ninguna. **Tests:** FE-TK-*, FE-SV-*, FE-IN-*, FE-GD-* (contrato §7.7).
- Si en el futuro se adopta D, cambian `TokenStorageService` y el interceptor; el contrato de `AuthService` y de las pantallas no.

## Tareas derivadas
WEB-001 (infraestructura y login), WEB-004 si el PM divide la tarea.
