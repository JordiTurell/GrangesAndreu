# EP-02 · Autenticación completa: login, registro, recuperación de contraseña y roles admin/user
**Objetivo:** login y registro reales (Web contra la API), recuperación de contraseña (forgot/reset) con enlace en modo desarrollo y dos roles globales, admin y user.  **Alcance:** Ambos
**Supuestos:** EP-01 se cierra antes; el enlace de reseteo va al log de la API (sin correo) y caduca a los 30 minutos, de un solo uso; sin verificación de email; el registro siempre crea rol `user` y no admite elegir rol (confirmado); el primer admin se crea con variables de entorno al arrancar; añadir el rol a `users` exige estrategia de esquema (ADR-005) y no se borra la BD sin confirmación.
**Fuera de alcance:** correo real (SMTP), verificación de email, cambio de contraseña con sesión, 2FA, gestión de usuarios por el admin, roles por granja, dashboard. **Backlog:** rate limiting (si el Arquitecto lo difiere), SMTP.

## Historias
- US-01 · Como visitante quiero registrarme desde la Web para tener una cuenta
  - [ ] Pantalla de registro enlazada desde el login
  - [ ] Crea la cuenta con rol `user` sin poder elegir rol
  - [ ] Muestra los errores 409 y 422 de la API
- US-02 · Como usuario registrado quiero iniciar sesión desde la Web contra la API real para acceder a las pantallas privadas
  - [ ] Login real con tokens según ADR-002
  - [ ] Guard de rutas privadas y refresco de sesión
  - [ ] La sesión conoce el rol
- US-03 · Como usuario que olvidó su contraseña quiero solicitar un enlace y fijar una nueva para recuperar el acceso
  - [ ] Respuesta uniforme exista o no el email; enlace en el log en modo desarrollo
  - [ ] Token de 30 minutos y un solo uso
  - [ ] La contraseña nueva cumple las reglas del registro (ADR-004)
  - [ ] Se puede entrar con la contraseña nueva y no con la antigua
- US-04 · Como responsable de la app quiero que cada usuario tenga rol admin o user para restringir funciones en el futuro
  - [ ] Todo usuario tiene rol y los existentes quedan con uno válido
  - [ ] `/me` devuelve el rol y hay dependencia para exigirlo
  - [ ] Se documenta cómo se crea el primer admin
  - [ ] No se puede obtener el rol `admin` desde el registro público

## Tablero
| ID | Capa | Tarea | Responsable | Depende de | Prio | Tamaño | Estado | Bugs |
|----|------|-------|-------------|------------|------|--------|--------|------|
| ARQ-003 | arq | Contrato API de recuperación de contraseña y roles admin/user | arquitecto | EP-01 cerrada | P0 | M | todo | — |
| ARQ-004 | arq | Diseño Angular de autenticación: rutas, sesión, guards y pantallas | arquitecto | ARQ-003 | P0 | M | todo | — |
| OPS-003 | ops | Estrategia de cambio de esquema para añadir el rol a users | developer | ARQ-003 | P0 | S | todo | — |
| API-002 | api | Roles admin y user en la API | developer | ARQ-003, OPS-003 | P0 | M | todo | — |
| API-003 | api | Forgot-password y reset-password en la API (modo desarrollo) | developer | ARQ-003, API-002 | P0 | M | todo | — |
| WEB-001 | web | Base de autenticación en Angular y login real | developer | ARQ-004 | P0 | L | todo | — |
| WEB-002 | web | Pantalla de registro | developer | WEB-001 | P1 | M | todo | — |
| WEB-003 | web | Pantallas de forgot-password y reset-password | developer | WEB-001 | P1 | M | todo | — |
| QA-002 | qa | Integración API-Web del flujo completo de autenticación | qa | API-003, WEB-002, WEB-003 | P1 | M | todo | — |

## Camino crítico y paralelización
```
EP-01 ─→ ARQ-003 ─→ OPS-003 ─→ API-002 ─→ API-003 ───────────────┐
            └────→ ARQ-004 ─→ WEB-001 ─→ WEB-002 ─────────────────┼─→ QA-002
                                     └─→ WEB-003 ────────────────┘
```
Un único árbol de trabajo: aunque la rama Web podría ir en paralelo a la de API, el circuito ejecuta en serie. Orden de ejecución: ARQ-003, ARQ-004, OPS-003, API-002, API-003, WEB-001, WEB-002, WEB-003, QA-002. `WEB-003` depende del contrato de API-003, no de su implementación.

## Riesgos
| ID | Riesgo | Prob. | Impacto | Mitigación |
|----|--------|-------|---------|------------|
| R-01 | Añadir el rol a `users` sin migraciones (ADR-005) con `api/data/app.db` ya poblada | alta | alta | ARQ-003 decide la estrategia y OPS-003 la implementa antes de API-002; sin borrar la BD sin confirmación |
| R-02 | Escalada de privilegios si el registro admite elegir rol | media | alta | El contrato prohíbe el rol en el registro; QA-002 lo verifica |
| R-03 | Seguridad del reseteo: token adivinable o reutilizable, enumeración, log del enlace activo fuera de desarrollo | media | alta | Token aleatorio hasheado, un solo uso, respuesta uniforme y log solo en debug; QA lo verifica |
| R-04 | Refresh tokens stateless: siguen válidos tras resetear la contraseña (ADR-003) | alta | media | ARQ-003 resuelve ADR-003 o documenta la limitación |
| R-05 | Sin rate limiting en login y forgot-password | media | media | ARQ-003 registra la decisión; si se difiere, backlog |
| R-06 | Conflicto de ficheros con EP-01 y dependencia de pytest | alta | media | EP-02 empieza tras cerrar EP-01; ejecución en serie |
| R-07 | SSR: ADR-002 y ADR-006 sin resolver | media | media | ARQ-004 los resuelve antes de WEB-001 |
| R-08 | Node 20 por defecto en la terminal (Angular 22 exige 22.22 o superior) | media | baja | `nvm use 26.0.0` antes de `npm` |
| R-09 | Cambio ajeno en `web/angular.json` (analytics del CLI de Angular, identificador personal) | alta | baja | El usuario decide: commitear, descartar o ignorar |

## Siguiente paso
EP-01 sigue abierta (OPS-002 `in_progress`, intento 1, con BUG-001 ya corregido en `config.py` y pendiente de entrega y nuevo QA; OPS-001, API-001 y QA-001 en `todo`). Parada del PM: `git status --porcelain -uall -- api web` lista `web/angular.json`, que no pertenece a ninguna tarea. El usuario lo gestiona él (commit o revert) y avisará al PM; entonces el PM reanuda EP-01 con OPS-002 y, al cerrarla, invoca al Arquitecto con ARQ-003.
