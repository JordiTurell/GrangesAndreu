# ADR-003 · Revocación de refresh tokens (`token_version`)
**Estado:** aceptado   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md))

## Contexto
- Los JWT son *stateless*: access 30 min, refresh 7 días (`core/security.py`), con `sub`, `type`, `iat`, `exp` y `jti`. `POST /api/auth/refresh` valida el refresh token, comprueba que el usuario exista y esté activo, y devuelve un par nuevo; el refresh anterior **sigue siendo válido**. No hay logout.
- `get_current_user` y `refresh_tokens` ya cargan al usuario de la BD en cada petición (comprueban `is_active`).
- EP-02 añade el reseteo de contraseña: su motivo es recuperar una cuenta que puede estar comprometida. Si los tokens emitidos siguen valiendo hasta 7 días, quien tenga un refresh token robado conserva el acceso tras el cambio de contraseña (riesgo R-04).

## Opciones
| Opción | Pros | Contras |
|--------|------|---------|
| A. Aceptar la limitación | Sin cambios | El reseteo no corta el acceso robado; incoherente con su propósito |
| B. `users.token_version` y claim `tv` | Una columna y un claim; revoca **todos** los access y refresh del usuario de golpe; determinista de probar; sirve también para un futuro «cerrar todas las sesiones» | No revoca un token concreto; un refresh normal no invalida el anterior |
| C. Tabla de `jti` con rotación y detección de reutilización | Revocación fina y detección de robo | Tabla, limpieza, escritura en cada refresh, más superficie; desproporcionado ahora |
| D. `password_changed_at` frente a `iat` | Sin claim nuevo | `iat` tiene resolución de 1 s: o se revocan tokens recién emitidos tras el reseteo o sobreviven los de ese mismo segundo; tests con tiempo, frágiles |

## Decisión
**Opción B.**
1. `users.token_version` (Integer, NOT NULL, defecto `0`). Los access y refresh llevan el claim `tv` con el valor del usuario en la emisión.
2. `get_current_user` y `refresh_tokens` comparan `payload.get("tv", 0)` con `user.token_version`; si difieren → 401 `unauthorized` «Token revocado». La ausencia de `tv` equivale a `0`, de modo que los tokens anteriores a esta épica siguen valiendo mientras la versión sea `0`.
3. `reset-password` incrementa `token_version` en SQL (`token_version + 1`) en la misma transacción que cambia la contraseña. No devuelve tokens nuevos.
4. **Limitación aceptada:** un `refresh` normal no rota ni invalida el refresh token anterior. No hay logout ni rotación con detección de reutilización (backlog). Un robo sin cambio de contraseña no se detecta.
5. El rol no va en el token (ADR-007): `tv` es el único dato de estado que viaja en el JWT.

## Consecuencias
- **API:** `core/security.py` (claim, `ensure_token_is_current`), `services.build_tokens` y `refresh_tokens`, entidad `User` y migración de la columna (ADR-005, OPS-003). Sin endpoints nuevos ni cambios de esquemas.
- **Web (ARQ-004, ADR-002):** un 401 «Token revocado» en cualquier llamada o en el refresh obliga a descartar la sesión y volver al login.
- **Tests:** PR-14, PR-15 y el caso del token sin `tv` del contrato §7.4.
- **Datos existentes:** los usuarios quedan con `token_version = 0` y sus tokens vigentes siguen funcionando.

## Tareas derivadas
OPS-003 (columna), API-002 (entidad), API-004 (claim y comprobación), API-003 (incremento en el reseteo).
