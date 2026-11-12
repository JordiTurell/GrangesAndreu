# ADR-007 · Roles globales `admin` y `user`
**Estado:** aceptado (alcance reducido a dos roles globales)   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md))

## Contexto
- El ADR-007 original contemplaba operario, responsable de granja y administrador, con ámbito por granja. No existe aún ningún módulo de dominio.
- Decisión del usuario (2026-11-11): solo dos roles globales, `admin` y `user`; todo usuario tiene siempre un rol; el registro público siempre crea `user` y no permite elegirlo; los usuarios existentes quedan como `user`; el primer admin sale de variables de entorno.
- El JWT dura 30 min (access) y 7 días (refresh); `get_current_user` carga al usuario en cada petición.

## Opciones
- **(a) Dónde vive el rol:** cadena con `CHECK` en `users.role` (elegida); `Enum` nativo de SQLAlchemy (DDL distinto entre `create_all` y el `ALTER` de la migración); tabla de roles y relación (excesivo para dos valores fijos).
- **(b) Rol en el JWT:** sí (sin lectura de BD, pero queda obsoleto: un admin degradado conservaría privilegios hasta 7 días con un refresh) o no (elegida: el rol se lee del usuario cargado en cada petición, sin coste extra).
- **(c) Campo `role` en el registro:** rechazarlo con 422 o ignorarlo (elegida: el esquema no tiene el campo y el servicio fija `user`; no cambia el contrato de `register` ni rompe clientes con campos de más).
- **(d) Jerarquía:** `admin` implica `user` o ninguna (elegida: sin jerarquía implícita; cada endpoint lista los roles permitidos).

## Decisión
1. `users.role`: `String(10)`, NOT NULL, `DEFAULT 'user'`, `CHECK (role IN ('admin', 'user'))` (`ck_users_role`). `UserRole` es un `StrEnum` con `ADMIN` y `USER`.
2. El rol **no** viaja en el JWT. `GET /api/auth/me` y `UserRead` lo devuelven; el Front lo obtiene de `/me`.
3. Dependencia `require_role(*roles: UserRole)` en `core/security.py`: 401 si no hay sesión válida, 403 `forbidden` («No tienes permisos para realizar esta acción») si el rol no está permitido. Sin roles → `ValueError`.
4. `register` **ignora** un `role` enviado y crea siempre `user`.
5. Único camino a `admin` en esta épica: `INITIAL_ADMIN_*` (crea o promueve; idempotente; solo actúa si no hay ningún admin). Sin endpoints de alta ni de cambio de rol.
6. La autorización la aplica siempre la API; el rol que muestra el Front solo sirve para la interfaz.

## Consecuencias
- **API:** `entities.py`, `schemas.py` (`UserRead.role`), `services.py`, `core/security.py`, `core/config.py`, `main.py`; migración de la columna (ADR-005).
- **Web (ARQ-004):** el modelo `UserRead` incluye `role: 'admin' | 'user'`; sin autorización en el cliente más allá de la navegación.
- **Fuera de alcance:** roles por granja, operario y responsable de granja, gestión de usuarios por el admin. Cuando existan, un ADR nuevo reemplazará o ampliará este (p. ej. membresías por granja en una tabla propia, sin tocar `users.role`).
- **Tests:** RL-01 a RL-10 y AD-01 a AD-11 del contrato §7.

## Tareas derivadas
OPS-003, API-002.
