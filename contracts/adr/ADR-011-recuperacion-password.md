# ADR-011 · Recuperación de contraseña (forgot/reset) en modo desarrollo
**Estado:** aceptado   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md) §3, §4.3, §4.4)

## Contexto
- Decisiones del usuario: en desarrollo no se envía correo y el enlace se escribe en el log de la API; el token caduca a los 30 minutos y es de un solo uso; sin verificación de email; el SMTP real queda en backlog.
- `settings.debug` (`DEBUG`) es la única bandera de modo que existe. uvicorn solo configura sus propios loggers: un INFO de otro logger no sale por consola sin configuración.
- La fixture de tests solo sobrescribe `get_db`; el `lifespan` usa el engine global. La BD SQLite devuelve `DateTime(timezone=True)` sin zona. El `ValidationError` de pydantic muestra los valores de entrada.
- `hash_password` es bcrypt (~250 ms): útil para contraseñas, no para buscar un token por igualdad.

## Opciones
| Tema | Opciones | Elegida |
|------|----------|---------|
| Token | JWT firmado con caducidad; token aleatorio guardado hasheado | Aleatorio `secrets.token_urlsafe(32)` (256 bits): revocable, de un solo uso real, sin lógica criptográfica propia |
| Hash del token | bcrypt; SHA-256 | SHA-256 hexadecimal: el token ya tiene entropía de sobra y se busca por igualdad indexada |
| Tokens previos | Varios válidos a la vez; el último invalida los anteriores | El último pedido borra los anteriores: un enlace vivo por usuario y como máximo una fila por usuario (sin crecimiento sin límite) |
| Un solo uso | Comprobar y luego marcar; `UPDATE ... WHERE used_at IS NULL AND expires_at > :now` | Consumo atómico con `rowcount == 1`: seguro con peticiones concurrentes |
| Enumeración | Responder igual pero trabajar de forma distinta; responder igual y trabajar en segundo plano | 202 inmediato y `BackgroundTasks`: el tiempo no depende de si el email existe; la tarea usa el `bind` de `get_db` |
| Activación del enlace en log | Variable propia; `settings.debug` | Solo `settings.debug is True`, evaluado en cada llamada, con doble comprobación en el emisor |
| Rate limiting | Ahora (memoria o `slowapi`); backlog | Backlog (ver abajo) |

## Decisión
1. `POST /api/auth/forgot-password` (202, respuesta idéntica exista o no el email o esté inactiva) y `POST /api/auth/reset-password` (200; 400 `invalid_token` / `expired_token`; 422 con las reglas de contraseña de `register`, incluido `password_too_long` de ADR-004 sobre `new_password`). Detalle en el contrato §3.
2. Tabla `password_reset_tokens` (`user_id` con `ON DELETE CASCADE`, `token_hash` único, `created_at`, `expires_at`, `used_at`). Se guarda solo el hash; el token nunca se devuelve ni se guarda en claro.
3. Caducidad 30 minutos (`PASSWORD_RESET_EXPIRE_MINUTES`, defecto 30). `expires_at <= ahora` ya es caducado. Las fechas leídas de SQLite se tratan como UTC.
4. Una contraseña nueva inválida (422) **no consume** el token. Un reseteo correcto cambia la contraseña, consume el token e incrementa `users.token_version` (ADR-003): revoca todos los tokens emitidos. No inicia sesión.
5. **Servicio de envío** `app/shared/mail.py`: `MailSender.send_password_reset(to_email, reset_url)`; `LogMailSender` (INFO en el logger `app.mail`) solo con `settings.debug is True`; `NullMailSender` en cualquier otro caso. Fuera de debug no se escribe ningún enlace ni token. El enlace es `{FRONTEND_BASE_URL}/reset-password?token=<token>` (`FRONTEND_BASE_URL`, defecto `http://localhost:4200`, debe empezar por `http://` o `https://`).
6. **Rate limiting (login y forgot-password): backlog**, con estos motivos: no hay envío real de correo, por lo que `forgot-password` no tiene un vector de abuso externo en esta épica (como máximo una fila por usuario y un INFO en el log de desarrollo); bcrypt encarece el fuerza bruta de `login` pero no lo impide; la solución correcta depende de decisiones aún abiertas (almacenamiento compartido entre workers, cabeceras de proxy, política por IP y por email). Es **condición previa a cualquier despliegue no local**; el diseño mínimo del backlog es por IP y por email, 429 `too_many_requests` y `Retry-After`. Riesgo R-05 aceptado para uso local.
7. Los errores de dominio nuevos (`InvalidTokenError`, `ExpiredTokenError`) viven en `shared/exceptions.py` y siguen el envelope `{"error": {"code", "message"}}`; los 422 siguen el formato por defecto (ADR-001 pendiente).

## Consecuencias
- **API:** entidad y esquemas nuevos, 2 endpoints, `shared/mail.py`, `shared/exceptions.py`, `config.py` (2 variables), `security.py` (revocación). Tabla nueva: la crea `create_all`, sin migración.
- **Seguridad:** sin enumeración por respuesta ni por tiempo; token de 256 bits hasheado y de un solo uso atómico; el 422 hace eco de `input` (entrada de ADR-001); en producción sin SMTP la función no entrega enlaces (R-14).
- **Web (ARQ-004):** ruta `/reset-password` con `?token=`; no prerenderizar; quitar el token de la URL y `Referrer-Policy: no-referrer` (ADR-006); tras reset ir a `/login`.
- **Tests:** PR-01 a PR-17 y LK-01 a LK-05 del contrato §7.
- **Backlog:** SMTP real (nueva clase de `MailSender`), rate limiting, plantillas y expiración configurable por entorno, limpieza periódica de filas caducadas.

## Tareas derivadas
API-003, API-004, QA de API, WEB-003, ARQ-004.
