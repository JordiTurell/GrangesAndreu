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
| ARQ-003 | arq | Contrato API de recuperación de contraseña y roles admin/user | arquitecto | — | P0 | M | done | — |
| ARQ-004 | arq | Diseño Angular de autenticación: rutas, sesión, guards y pantallas | arquitecto | ARQ-003 | P0 | M | done | — |
| OPS-003 | ops | Migraciones mínimas: añadir `role` y `token_version` a `users` sin perder datos (ADR-005) | developer | ARQ-003 | P0 | S | todo | — |
| API-002 | api | Roles admin y user y primer admin por variables de entorno | developer | ARQ-003, OPS-003 | P0 | M | todo | — |
| API-004 | api | Revocación de tokens por `token_version` (ADR-003) | developer | API-002 | P0 | S | todo | — |
| API-003 | api | Forgot-password y reset-password en la API (modo desarrollo) | developer | ARQ-003, API-002, API-004 | P0 | M | todo | — |
| API-005 | api | Handler propio del 422 con envelope sin `input` (ADR-001) | developer | ARQ-004, API-003 | P0 | S | todo | — |
| QA-003 | qa | Integración de la API: roles, primer admin, migración, recuperación de contraseña y formato del 422 | qa | API-005 | P1 | M | todo | — |
| WEB-001 | web | Base de sesión en Angular: HttpClient, interceptores, guards, servicios y rutas | developer | ARQ-004 | P0 | M | todo | — |
| WEB-004 | web | Login real, pantalla de inicio y cierre de sesión | developer | WEB-001 | P0 | S | todo | — |
| WEB-002 | web | Pantalla de registro | developer | WEB-004 | P1 | M | todo | — |
| WEB-003 | web | Pantallas de forgot-password y reset-password | developer | WEB-002 | P1 | M | todo | — |
| QA-002 | qa | Integración API-Web del flujo completo de autenticación | qa | QA-003, WEB-003 | P1 | M | todo | — |

## Camino crítico y paralelización
```
ARQ-003 ─→ OPS-003 ─→ API-002 ─→ API-004 ─→ API-003 ─→ API-005 ─→ QA-003 ─┐
ARQ-004 ─→ WEB-001 ─→ WEB-004 ─→ WEB-002 ─→ WEB-003 ───────────────────┴─→ QA-002
```
Un único árbol de trabajo: el circuito ejecuta en serie. Orden de ejecución: OPS-003, API-002, API-004, API-003, API-005, QA-003, WEB-001, WEB-004, WEB-002, WEB-003, QA-002. WEB-001 no depende de API-005 (el normalizador del Front acepta ambas formas del 422); cada tarea WEB añade sus entradas en `app.routes.ts` y `app.routes.server.ts` junto con su ruta. OPS-004 (e2e con Playwright) queda en backlog.

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
| R-09 | Cambio ajeno en `web/angular.json` (analytics del CLI de Angular) | alta | baja | Resuelto: el usuario lo commiteó |
| R-10 | La migración de `users` se aplica sola en el primer arranque real sobre `api/data/app.db` (el servidor del usuario con reload la ejecutaría al editarse `database.py`) | alta | media | Parada del PM antes de OPS-003: copia de `app.db` por el usuario; agentes solo con BD temporales; ALTER aditivo e idempotente |
| R-11 | `INITIAL_ADMIN_PASSWORD` en `api/.env` es un secreto en claro | media | media | `SecretStr`, `hide_input_in_errors`, retirar tras el primer arranque; `.env` nunca se commitea |
| R-12 | El mini-migrador no cubre borrados, renombrados ni cambios de tipo | media | baja | ADR-005 fija los criterios de paso a Alembic |
| R-13 | El token de reseteo va en la URL del enlace (Referer, historial y logs SSR) | media | media | ARQ-004 decide `RenderMode` y el tratamiento de `/reset-password` |
| R-14 | El reseteo solo funciona con `DEBUG=true` hasta que haya SMTP; con `DEBUG=true` compartido también se loguean enlaces | media | media | Aceptado para desarrollo local; SMTP y rate limiting en backlog antes de un despliegue no local |
| R-15 | El refresh token en `localStorage` o `sessionStorage` es legible por XSS (ADR-002) | baja | alta | Access token solo en memoria, sin `innerHTML`; cookies `HttpOnly` con BFF en backlog |
| R-16 | La plantilla de bienvenida de `app.html` y `app.spec.ts` rompen todas las rutas hasta limpiarlos | alta | baja | WEB-001 los limpia (contrato §6.1) |
| R-17 | API-005 cambia el formato aprobado del 422 y toca 3 ficheros de tests de EP-01 (excepción a la propiedad de tests) | media | media | Ajuste mecánico y acotado; QA lo revisa en QA-003; aviso al usuario |
| R-18 | App sin zone.js: el estado asíncrono en campos planos no repinta | media | media | Todo estado asíncrono en `signal`; lo verifican los `*.spec.ts` y QA-002 |

## Siguiente paso
ARQ-003 y ARQ-004 `done`: el contrato `contracts/auth-completo.md` queda aprobado (API y Front) con ADR-001, ADR-002, ADR-003, ADR-005, ADR-006, ADR-007 y ADR-011 aceptados y sin preguntas de negocio. **Cambio a tener en cuenta:** ADR-001 sustituye el 422 por defecto de FastAPI por un envelope `error.fields` sin `input` (API-005). Supuestos reversibles a confirmar al cerrar la épica: Recordarme = sesión persistente hasta 7 días, destino `/inicio` tras el login y login automático tras el registro. **Parada antes de OPS-003:** el usuario debe copiar `api/data/app.db` y decidir si para su `python main.py` con reload (la migración se aplicaría sola al arrancar). Tras API-002 tendrá que definir `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_USERNAME` e `INITIAL_ADMIN_PASSWORD` en su `api/.env`.
