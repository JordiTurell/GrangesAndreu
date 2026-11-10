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
| ADR-001 | Formato de error de validación (422 de FastAPI vs. envelope `{error:{code,message}}`) | pendiente | Manejo de errores en el Front, contratos de todos los módulos |
| ADR-002 | Almacenamiento y refresco de tokens en el Front compatible con SSR (memoria, `localStorage`, cookies `HttpOnly`) y significado de "Recordarme" | pendiente | Login Web, guards, interceptors |
| ADR-003 | Rotación y revocación de refresh tokens (hoy *stateless*) | pendiente | `POST /api/auth/refresh` |
| ADR-004 | Límite de contraseña en bytes (bcrypt 72 bytes) frente a `max_length` en caracteres | pendiente | `register` y `login` |
| ADR-005 | Estrategia de migraciones (Alembic o equivalente) | pendiente | Cualquier cambio de una tabla existente |
| ADR-006 | `RenderMode` SSR por ruta (privadas sin `Prerender`) | pendiente | `app.routes.server.ts` |
| ADR-007 | Modelo de roles y permisos (operario, responsable de granja, administrador) y ámbito por granja | pendiente | Todos los módulos de dominio |
| ADR-008 | Mecanismo del chat en tiempo real (WebSocket, SSE o polling) | pendiente | Módulo de chat |
| ADR-009 | Modelado del control de horarios (jornadas, solapamientos, necesidad de operario) | pendiente | Módulo de horarios |
| ADR-010 | Zonas horarias y formato de fechas | pendiente | Horarios, tareas, inspecciones |
