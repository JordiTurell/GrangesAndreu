# ADR · Decisiones de arquitectura

Decisiones **transversales** del proyecto. Las decisiones locales a una épica se escriben en la sección 1 de su contrato (`contracts/<slug>.md`). Lo mantiene el Arquitecto.

## Estados
`pendiente` → `propuesto` → `aceptado` | `reemplazado`. Un contrato no puede pasar a `aprobado` si depende de un ADR en `pendiente`.

## Plantilla (`ADR-NNN-<tema>.md`)
```markdown
# ADR-NNN · <título>
**Estado:** pendiente | propuesto | aceptado | reemplazado   **Fecha:**
**Contexto:** problema y restricciones (referencias al código)
**Opciones:** A, B, C con pros y contras
**Decisión:** opción elegida y motivo
**Consecuencias:** impacto en API, Web, tests y migraciones
**Tareas derivadas:** ARQ/API/WEB/OPS-xxx
```

## Índice

| ID | Tema | Estado | Bloquea o afecta a |
|----|------|--------|--------------------|
| [ADR-001](ADR-001-errores-validacion.md) | Formato de error de validación: handler propio del 422 con envelope `{error:{code,message,fields}}` sin `input` (cierra BUG-004) y normalizador único en el Front | aceptado | Contratos de todos los módulos, API-005, manejo de errores del Front. Sustituye al `detail` por defecto en [auth](../auth.md) y [auth-completo](../auth-completo.md) |
| [ADR-002](ADR-002-tokens-front.md) | Tokens en el Front: access en memoria, refresh en `localStorage` (Recordarme) o `sessionStorage`, refresco reactivo con una sola petición en vuelo; cookies `HttpOnly` con BFF como evolución | aceptado | Login Web, guards, interceptors, `AuthService` (WEB-001) |
| [ADR-003](ADR-003-refresh-tokens.md) | Revocación de refresh tokens: `users.token_version` y claim `tv`, sin rotación por uso | aceptado | `refresh`, `get_current_user`, `reset-password` |
| [ADR-004](ADR-004-password-bytes.md) | Límite de contraseña en bytes (bcrypt 72 bytes) frente a `max_length` en caracteres | aceptado | `register` y `login` |
| [ADR-005](ADR-005-migraciones.md) | Migraciones mínimas propias, aditivas e idempotentes (`core/migrations.py`); criterios de paso a Alembic | aceptado | Cualquier cambio de una tabla existente (OPS-003) |
| [ADR-006](ADR-006-rendermode.md) | `RenderMode` por ruta: solo `login`, `register` y `forgot-password` en `Prerender`; `reset-password` (token en la URL) y todo lo demás (`**`) en `Client` | aceptado | `app.routes.server.ts`, `index.html`, `server.ts` (WEB-001, WEB-003) |
| [ADR-007](ADR-007-roles.md) | Roles globales `admin` y `user` (alcance reducido; ámbito por granja y roles de granja, fuera) | aceptado | `users.role`, `/me`, `require_role` |
| ADR-008 | Mecanismo del chat en tiempo real (WebSocket, SSE o polling) | pendiente | Módulo de chat |
| ADR-009 | Modelado del control de horarios (jornadas, solapamientos, necesidad de operario) | pendiente | Módulo de horarios |
| ADR-010 | Zonas horarias y formato de fechas | pendiente | Horarios, tareas, inspecciones |
| [ADR-011](ADR-011-recuperacion-password.md) | Recuperación de contraseña: token hasheado de 30 min y un solo uso, enlace solo en log con `DEBUG=true`, rate limiting en backlog | aceptado | `forgot-password`, `reset-password`, `shared/mail.py` |
