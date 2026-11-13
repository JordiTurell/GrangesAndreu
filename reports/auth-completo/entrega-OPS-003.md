## Entrega · OPS-003
**Intento:** 1
**Contrato:** contracts/auth-completo.md §2.3 y §7.2 (aprobado) y contracts/adr/ADR-005-migraciones.md (aceptado)
**Estado propuesto:** in_qa
**Versión de SQLite:** `sqlite3.sqlite_version` = **3.49.1** (Python 3.13.5). Admite `ALTER TABLE ... ADD COLUMN` con `NOT NULL DEFAULT` y `CONSTRAINT ... CHECK`.

**Cambios:**
- `api/app/core/migrations.py` (nuevo): `run_migrations(engine)` ejecuta en una transacción (`engine.begin()`) la tupla ordenada `MIGRATIONS` = (`_add_users_role`, `_add_users_token_version`). Ayudantes `_column_names` (inspector nuevo por llamada; `None` si la tabla no existe) y `_add_column` (no hace nada si falta la tabla o la columna ya existe; si el `ALTER` da `OperationalError`, relee el esquema y lo ignora solo si la columna ya existe; en otro caso relanza). DDL literal del contrato: `role VARCHAR(10) NOT NULL DEFAULT 'user' CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))` y `token_version INTEGER NOT NULL DEFAULT 0`.
- `api/app/core/database.py`: `init_db()` llama a `run_migrations(engine)` tras `create_all` (import de `.migrations` arriba; sin ciclos, `migrations.py` no importa `database`).
- `api/tests/unit/test_migrations.py` (nuevo, 15 tests): MG-01 a MG-06 y RL-09 (parte de BD) con una BD «anterior» de DDL congelado y 2 usuarios sembrados con SQL crudo, y con la BD nueva de la fixture `engine`. Incluye idempotencia por paso, comparación de `PRAGMA table_info` entre BD nueva y migrada, índices únicos, `CHECK`, BD sin `users`, tres variantes de carrera (columna ya existente → se ignora; `users` como vista → `OperationalError` relanzado; relectura que sigue sin ver la columna → relanza) y `init_db()` con el engine global sustituido por uno temporal (`monkeypatch`). `test_bd_nueva_no_cambia_con_la_migracion` exige «sin cambios» solo cuando la entidad ya declara las columnas (después de API-002); antes exige idempotencia.

**Cómo probar:**
- `cd api; python -m pytest tests/unit/test_migrations.py -q`
- `cd api; python -m pytest -q` (suite completa)

**Verificación realizada:**
- `cd api; python -m pytest -q` → **204 passed** en 49 s (189 existentes + 15 nuevos), con la entidad `User` todavía **sin** `role`/`token_version` (estado actual).
- «Después de API-002» (simulado, sin tocar la entidad): tabla `users` creada en una BD temporal con una `Table` equivalente a la futura entidad (`server_default=text("'user'")`, `server_default=text("0")`, `CheckConstraint(name="ck_users_role")`). `run_migrations` no cambia `sqlite_master` y `PRAGMA table_info` da `('role', 'VARCHAR(10)', 1, "'user'")` y `('token_version', 'INTEGER', 1, '0')`, idéntico a la BD anterior migrada (MG-03). Implica que la entidad debe declarar exactamente esos `server_default` y el `CheckConstraint` con nombre `ck_users_role` (ADR-005 §5).
- Prueba tipo MG-07 manual: `cwd = api/`, `DEBUG=true`, `DATABASE_URL=sqlite:///<tmp>/copia.db` (directorio temporal, borrado al final), BD con DDL congelado y 2 usuarios; `init_db()` en un proceso Python → salida 0; filas intactas con `role='user'`, `token_version=0`; `table_info` como arriba; `ck_users_role` presente una vez; segunda ejecución → salida 0 y mismo resultado. (Con la entidad actual `init_db()` solo conoce la tabla `users`; `password_reset_tokens` llegará con API-003.)
- `git status`: solo `database.py`, `migrations.py`, `test_migrations.py` (de la tarea) y `tasks/auth-completo.json` (del PM).
- No se abrió, migró ni tocó `api/data/app.db` ni `api/.env`; todos los tests y pruebas usan BD temporales. Sin servidores arrancados. No se tocó `requirements.txt`. Sin comandos git de escritura.

**Desviaciones del contrato:** ninguna.

**Deuda o riesgos detectados:**
- R-10: al integrar y arrancar la API real, `init_db()` migrará `api/data/app.db` sola. El PM debe avisar al usuario de que copie `api/data/app.db` antes y de que su servidor con reload puede ejecutar la migración en cuanto se guarde `database.py`.
- La migración no tiene historial ni bajadas (ADR-005 §7 indica cuándo pasar a Alembic).
- MG-07 como criterio de nivel S (QA, en `QA-003`) y MG-08 (PM) quedan fuera; la comprobación manual MG-07 anterior es orientativa.

**Siguiente paso:** QA revisa OPS-003 cuando el PM lo decida (`QA-003` cubrirá MG-07 en subproceso). `API-002` depende de esta tarea.
