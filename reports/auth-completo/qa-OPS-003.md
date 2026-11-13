# Informe QA · auth-completo · OPS-003 (EP-02)
**Veredicto:** APROBADO
**Alcance:** OPS-003 (`api/app/core/migrations.py`, `api/app/core/database.py`, `api/tests/unit/test_migrations.py`). Contrato §2.3 y §7.2, ADR-005.
**Estado del árbol (`git status --porcelain`):** `M api/app/core/database.py`, `?? api/app/core/migrations.py`, `?? api/tests/unit/test_migrations.py` (además de ficheros de agentes, `AGENTS.md`, `tasks/` y `reports/`, ajenos a la tarea). QA no ha modificado código.
**Estado propuesto:** done

## Pruebas ejecutadas (Python 3.13, Windows, BD temporales; sin servidor; no se tocó `api/data/` ni `.env`)
- `cd api; python -m pytest tests/unit/test_migrations.py -q` → **15 passed** (1,3 s).
- Smoke `from main import app` (`DEBUG=true`, `DATABASE_URL` a un fichero temporal) → OK (`GrangesAndreu API`).
- MG-07 en subproceso: copia temporal con el DDL congelado de §2.3 y 2 usuarios sembrados con SQL crudo; `init_db()` con `cwd=api/`, `DEBUG=true`, `DATABASE_URL` temporal, ejecutado dos veces.
- No ejecutada: regresión completa (fuera de alcance por instrucción; el Developer reporta 204 passed).

## Criterios
- ✔ MG-01 a MG-06 y RL-09 (parte BD): 15 tests unitarios en verde (idempotencia, BD nueva, `CHECK`, sin `users`, carrera, `init_db`).
- ✔ MG-07 salida 0 en ambas ejecuciones: `run 1 rc 0 OK` / `run 2 rc 0 OK`.
- ✔ MG-07 filas conservadas: `id, username, email, hashed_password, is_active, created_at` idénticos a los sembrados; `role='user'` y `token_version=0` en las dos filas.
- ✔ MG-07 esquema: `table_info` → `('role','VARCHAR(10)',notnull 1,"'user'")` y `('token_version','INTEGER',1,'0')`; `ck_users_role` presente 1 vez; índices únicos `ix_users_email`/`ix_users_username` intactos; `UPDATE users SET role='root'` → `IntegrityError`.
- ✔ MG-07 segunda ejecución sin cambios: instantánea de filas y `sqlite_master` idéntica entre la 1.ª y la 2.ª ejecución.
- ✔ §2.3: DDL literal del contrato y `init_db()` = `create_all` + `run_migrations(engine)` (revisado en el código); `requirements.txt` sin cambios (no figura en `git status`).
- ✔ Entrega con `sqlite_version` 3.49.1 documentada; sin tocar `api/data/app.db` ni `api/.env`.
- ➖ MG-08 (PM, cierre de épica) y la comprobación «después de API-002» (entidad con columnas): no aplicables aún; el Developer la simuló en una BD temporal y se repetirá cuando API-002 esté integrada.

## Defectos
Ninguno (sin S1–S3).

## Notas para el PM (no bloquean)
- R-10: la migración se aplicará sola sobre `api/data/app.db` en el primer arranque real; el usuario debe copiarlo antes (el servidor con reload puede dispararla al guardar `database.py`).
- Al integrar API-002, la entidad debe declarar `server_default=text("'user'")`/`text("0")` y `CheckConstraint(name="ck_users_role")` para que MG-03 siga igual (ADR-005 §5).

## Resultado
agente: QA
tarea: OPS-003
estado: ok
veredicto: APROBADO
artefactos: reports/auth-completo/qa-OPS-003.md
bugs: ninguno
detalle: 15/15 tests de migraciones, smoke e MG-07 (subproceso, BD temporal, 2 ejecuciones) en verde; filas conservadas con role=user y token_version=0, CHECK activo e idempotente. Sin tocar api/data ni .env.
