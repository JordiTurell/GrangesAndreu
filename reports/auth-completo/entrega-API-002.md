## Entrega · API-002
**Intento:** 1
**Contrato:** contracts/auth-completo.md (aprobado)
**Estado propuesto:** in_qa (con 2 tests de integración de QA que hay que actualizar; ver «Deuda o riesgos»)

**Cambios**
- `api/app/modules/auth/entities.py`: `UserRole` (`StrEnum`); columnas `role` (String(10), `default` `"user"`, `server_default=text("'user'")`) y `token_version` (Integer, `default` 0, `server_default=text("0")`); `CheckConstraint(..., name="ck_users_role")`. Sin tabla `roles`.
- `api/app/modules/auth/schemas.py`: `UserRead.role: UserRole`; alias `NewPassword` (§4.2) usado por `UserCreate.password`. El OpenAPI de `UserCreate.password` no cambia. `UserCreate` sigue sin `role` (EP-02-D2).
- `api/app/modules/auth/services.py`: `register_user` fija `role=USER`; nuevo `ensure_initial_admin` (§4.5, reglas 1 a 7; errores solo con nombre de variable y `type`, `from None`; logs sin secretos).
- `api/app/core/security.py`: `require_role(*roles)` (`ValueError` sin roles; 401 antes que 403; 403 `forbidden` vía `PermissionDeniedError`).
- `api/app/core/config.py`: `initial_admin_email`, `initial_admin_username`, `initial_admin_password: SecretStr`; `hide_input_in_errors=True`.
- `api/main.py`: `lifespan` llama a `ensure_initial_admin` con `SessionLocal` tras `init_db()` (`get_secret_value()` solo ahí).
- `api/tests/conftest.py`: fija `INITIAL_ADMIN_*` a `""` antes de importar `app.*`.
- Tests nuevos: `tests/unit/test_roles.py` (RL-03, RL-06 a RL-10, defaults/CHECK de la entidad; RL-06/RL-07 con la ruta P-1 montada por el test, como pide el DoD), `tests/unit/test_initial_admin.py` (AD-01 a AD-11); `tests/unit/test_config.py` (variables nuevas, `hide_input_in_errors`; `entorno_limpio` limpia también `INITIAL_ADMIN_*`).

**Cómo probar** (desde `api/`): `python -m pytest tests/unit/test_roles.py tests/unit/test_initial_admin.py tests/unit/test_config.py tests/unit/test_migrations.py`

**Verificación realizada**
- `tests/unit` completo: en verde (incluye `test_migrations.py`, OPS-003: la entidad y el `ALTER` coinciden, la migración no cambia nada en BD nueva).
- Integración de auth existente (`test_auth_regresion`, `test_login_password_bytes`, `test_config_startup`, parte de `test_seguridad_y_contrato` y `test_register_password_bytes`): 235 en verde; 6 fallos esperados (abajo).
- `from main import app` + `TestClient` con `DEBUG=true`, `DATABASE_URL` temporal y `INITIAL_ADMIN_*`: arranque OK; admin creado en el lifespan; login admin 200 y `/me` con `role: "admin"`; `register` con `"role": "admin"` en el body → 201 con `role: "user"`; 422 sigue con tipo `string_too_short`. `/openapi.json`: `UserRead` con `role` (requerido) y sin `token_version` ni `hashed_password`; `UserCreate` sin `role`.
- No se ha arrancado servidor, ni tocado `api/data/` ni `.env`; sin instalaciones.

**Desviaciones del contrato:** ninguna. Fuera de esta tarea (no hecho a propósito): claim `tv` y `ensure_token_is_current` (API-004), `FRONTEND_BASE_URL` y `PASSWORD_RESET_EXPIRE_MINUTES` (API-003).

**Deuda o riesgos detectados**
- Los 6 fallos son tests de QA que fijan el conjunto exacto de campos de `UserRead` y deben incluir `role` según §2.1/§3 (ficheros fuera de mi alcance): `tests/integration/test_register_password_bytes.py` (`CAMPOS_USER_READ`, línea 20; 5 casos de `test_register_acepta_hasta_72_bytes`) y `tests/integration/test_seguridad_y_contrato.py::test_openapi_user_read_no_expone_hashed_password` (línea 152). Hay que añadir `"role"` a ambos conjuntos (tarea de QA o ajuste del PM).
- Orden en `NewPassword`: `Field(min_length)` debe ir **antes** de `AfterValidator`; al revés, el tipo del 422 pasa de `string_too_short` a `too_short` (comentado en el código). Relevante para API-003/API-005.
- Los tests RL-06/RL-07 usan `TestClient`, que el reparto de §7 asigna a QA (nivel I); se incluyen porque el DoD de la tarea exige probar la dependencia con una ruta de prueba. QA puede duplicarlos o ampliarlos (RL-01, RL-02, RL-04, RL-05).

**Siguiente paso:** QA-xxx (verificar §7.1 y §7.3; actualizar los 2 tests de integración señalados).
