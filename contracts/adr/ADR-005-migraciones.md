# ADR-005 · Estrategia de migraciones: pasos mínimos idempotentes
**Estado:** aceptado   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md) §2.3)

## Contexto
- `init_db()` (`core/database.py`) solo ejecuta `Base.metadata.create_all`, que crea tablas que faltan pero **no altera** las existentes. No hay Alembic.
- EP-02 añade a `users` las columnas `role` y `token_version`. La BD local `api/data/app.db` ya tiene la tabla y usuarios, que deben conservarse con rol `user`. Las tablas nuevas (`password_reset_tokens`) las cubre `create_all`.
- SQLite admite `ALTER TABLE ... ADD COLUMN` con `NOT NULL` si hay `DEFAULT` constante, y también un `CHECK` de columna; las filas existentes toman el valor por defecto.
- Los tests crean el esquema con `create_all` (fixture `engine`) y la fixture `client` ejecuta el `lifespan` (`init_db()` sobre el engine global temporal).

## Opciones
| Opción | Pros | Contras |
|--------|------|---------|
| A. Alembic | Estándar, historial, autogeneración, bajadas | Dependencia nueva, `alembic.ini`, `env.py` y `versions/`; línea base para BD ya creadas sin `alembic_version` (`stamp`); `fileConfig` por defecto silencia los loggers existentes; `create_all` y Alembic conviven mal; el `lifespan` lo lanzaría en cada `client` de test; desproporcionado para un `ADD COLUMN` |
| B. Pasos propios aditivos e idempotentes por inspección del esquema (elegida) | Cero dependencias; un fichero; BD nueva y anterior pasan por el mismo código; rápido en tests; conserva los datos | Sin historial ni bajadas; solo cambios aditivos; dialecto SQLite verificado |
| C. Borrar o recrear la BD | Trivial | Pierde los usuarios; **descartada** por decisión del usuario |
| D. Tabla `schema_migrations` con versiones | Trazabilidad | Estado extra que mantener y que la BD nueva debería rellenar sin ejecutar nada; innecesaria si cada paso inspecciona el esquema |

## Decisión
**Opción B.**
1. Módulo `api/app/core/migrations.py`: `run_migrations(engine)` ejecuta en una transacción (`engine.begin()`) la tupla ordenada `MIGRATIONS` de funciones `(connection) -> None`.
2. **Regla de oro:** cada paso inspecciona el esquema (`sqlalchemy.inspect`) y no hace nada si su cambio ya está aplicado o si la tabla no existe. Así una BD creada por `create_all` con la entidad actual y una BD anterior son equivalentes tras `init_db()`.
3. Solo cambios **aditivos** (columnas con `DEFAULT` y `NOT NULL`, índices). Borrar, renombrar o cambiar tipos queda fuera de esta estrategia.
4. `init_db()` llama a `create_all` y después a `run_migrations`. Un fallo aborta el arranque. La carrera entre procesos se tolera releyendo el esquema tras un `OperationalError`.
5. El DDL de la migración y el de la entidad (`server_default=text(...)`, `CheckConstraint(name=...)`) deben producir el mismo resultado en `PRAGMA table_info`.
6. **Pasos de EP-02:** `_add_users_role` (`VARCHAR(10) NOT NULL DEFAULT 'user'` con `CONSTRAINT ck_users_role CHECK (role IN ('admin', 'user'))`) y `_add_users_token_version` (`INTEGER NOT NULL DEFAULT 0`).
7. **Revisar y pasar a Alembic cuando:** haya que borrar, renombrar o cambiar el tipo de una columna; haya más de unos cinco pasos acumulados; se despliegue sobre un motor distinto de SQLite; o se necesite historial o bajadas.
8. Ningún agente migra `api/data/app.db`: ocurre en el primer arranque real del usuario (el PM le avisa y recomienda una copia manual previa).

## Consecuencias
- **API:** `core/migrations.py` (nuevo) y `core/database.py` (`init_db`). `requirements.txt` no cambia.
- **Tests:** MG-01 a MG-08 del contrato §7.2 con una BD «anterior» de DDL congelado y una BD nueva; deben pasar antes y después de que la entidad declare las columnas.
- **Datos existentes:** conservados; usuarios con `role = 'user'` y `token_version = 0`.
- Las tablas nuevas siguen creándose con `create_all` sin pasos de migración.

## Tareas derivadas
OPS-003.
