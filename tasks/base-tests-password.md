# EP-01 · Base de tests de la API y límite de contraseña en bytes
**Objetivo:** dotar a la API de infraestructura de tests, corregir el 500 de `POST /api/auth/register` con contraseñas multibyte de más de 72 bytes UTF-8 (ADR-004) y hacer fiable el arranque de la API con la configuración documentada (OPS-002).  **Alcance:** API
**Supuestos:** ADR-004 es técnico y lo cierra el Arquitecto; sin `api/.env` se usan variables de sesión (`DEBUG=true`, `DATABASE_URL` temporal); hay 4 commits locales (f35a787, 48bb5c9, 9137e26, f3a79f4) sin subir y ningún agente hace commits ni subidas: los hace el usuario, los cambios de cada tarea quedan sin commit en el árbol de trabajo y no hay rollback con git; el Developer escribe unitarios y QA los de integración; starlette 1.7.0 exige `httpx2` para `TestClient` (ARQ-002 lo fija en el contrato); el `api/.env` local es del usuario (JSON en `CORS_ORIGINS`) y nadie lo toca; `api/data/app.db` existe y no se toca.
**Fuera de alcance:** otros ADR, linter, CI, tests de otros endpoints, cambios en la Web, migraciones. **Backlog:** `created_at` sin zona horaria (ADR-010 pendiente), unicidad sin distinguir mayúsculas en BD, `SECRET_KEY` efímera con recarga en debug, traceback en el cuerpo del 500 en modo debug, versiones fijas de dependencias.

## Historias
- US-01 · Como desarrollador del equipo quiero una infraestructura de tests para la API con BD temporal para verificar cambios sin tocar la BD real ni la configuración local
  - [ ] `pytest` y `httpx2` en `api/requirements.txt` con rangos `>=` (sin `httpx`)
  - [ ] `api/tests/` con fixture de BD SQLite temporal (`get_db` sobrescrito) y `TestClient`
  - [ ] Test de humo de `GET /health` en verde
  - [ ] No se crea ni modifica `api/data/app.db` ni se requiere `api/.env`
- US-02 · Como usuario que se registra quiero que una contraseña que supera el límite de bcrypt en bytes se rechace con un error de validación claro para no recibir un 500
  - [ ] 40 letras "ñ" (80 bytes) en `register` → 422 claro, no 500
  - [ ] 72 bytes exactos se aceptan y 73 se rechazan con 422
  - [ ] `login` con más de 72 bytes no devuelve 500
  - [ ] Tests unitarios (Developer) y de integración (QA), con el límite exacto
  - [ ] ADR-004 aceptado y contrato de auth actualizado
- US-03 · Como desarrollador del equipo quiero que la API arranque con la configuración documentada en `.env.example`, desde cualquier directorio y sin efectos laterales si falla, para poner en marcha el entorno local sin errores de configuración
  - [ ] Un `api/.env` copiado de `.env.example` (`CORS_ORIGINS` con comas) arranca la API; el formato lista JSON sigue funcionando
  - [ ] Una `DATABASE_URL` SQLite relativa se resuelve respecto a `api/` y se crea el directorio de la BD, con independencia del cwd
  - [ ] Un arranque que falla por configuración no crea `api/data/`
  - [ ] Con variables ya válidas el comportamiento no cambia

## Tablero
| ID | Capa | Tarea | Responsable | Depende de | Prio | Tamaño | Estado | Bugs |
|----|------|-------|-------------|------------|------|--------|--------|------|
| ARQ-001 | arq | Resolver ADR-004 y contrato del límite de contraseña en bytes | arquitecto | — | P0 | S | done | — |
| ARQ-002 | arq | Revisar el contrato de EP-01: httpx2 y configuración de arranque | arquitecto | ARQ-001 | P0 | S | done | — |
| OPS-002 | ops | Arranque fiable de la API con la configuración documentada (sin tests; entrega con ST-01, ST-02, ST-04, ST-07) | developer | ARQ-002 | P0 | S | done | BUG-001 (cerrado) |
| OPS-001 | ops | Infraestructura de tests de la API (pytest, httpx2, fixture de BD temporal) y unitarios de configuración | developer | ARQ-002, OPS-002 | P0 | S | todo | — |
| API-001 | api | Rechazar con 422 las contraseñas que superan 72 bytes UTF-8 (ADR-004) | developer | ARQ-001, OPS-001 | P0 | S | todo | — |
| QA-001 | qa | Tests de integración del límite de contraseña en bytes y regresión de arranque (ST-01 a ST-10) | qa | API-001 | P1 | S | todo | — |

## Camino crítico y paralelización
```
ARQ-001 ─→ ARQ-002 ─→ OPS-002 ─→ OPS-001 ─→ API-001 → QA-001
```
Un único árbol de trabajo y precondición de `api/` limpio: todo se ejecuta en serie. `OPS-001` depende de `OPS-002` porque los unitarios de configuración (contrato §7.6.1) se escriben con la infraestructura de tests (EP-01-D8). `API-001` también depende de `ARQ-001`, ya `done`.

## Riesgos
| ID | Riesgo | Prob. | Impacto | Mitigación |
|----|--------|-------|---------|------------|
| R-01 | Importar `main` lanza `pip install` de lo que falte (incluidos `pytest` y `httpx2`) y necesita red | alta | baja | `pip install -r requirements.txt` en OPS-001 antes de `pytest`; documentarlo en la entrega |
| R-02 | `settings` y `engine` son singletons y el lifespan llama a `init_db()` sobre el engine global: sobrescribir `get_db` no basta para no tocar `api/data/app.db` | alta | media | `DEBUG` y `DATABASE_URL` temporal antes de importar la app; QA comprueba que `app.db` no cambia |
| R-03 | SQLite con WAL en Windows puede bloquear el borrado del fichero temporal | media | baja | Liberar el engine en el teardown; directorios temporales de pytest |
| R-04 | bcrypt 4.x truncaba en silencio y 5.x lanza `ValueError` | media | media | Validar en bytes con independencia de la versión de bcrypt |
| R-05 | El 422 sigue el formato por defecto mientras ADR-001 esté pendiente | baja | baja | Los tests comprueban el código 422 y el campo, no el texto del envelope |
| R-06 | Dependencias sin versión fija y entorno muy reciente: starlette 1.7.0 ya cambió `TestClient` a `httpx2` | media | media | ARQ-002 fijó `httpx2>=2.0.0` (EP-01-D4); la entrega de OPS-001 registra las versiones; versiones fijas en backlog |
| R-07 | Cambiar el parseo de `CORS_ORIGINS` puede romper el `api/.env` local (JSON) o el de `.env.example` (comas) | media | media | El contrato exige ambos formatos; QA los verifica con variables de entorno sin tocar `api/.env`; el PM comprueba al final que la API arranca con el `api/.env` existente |

## Siguiente paso
OPS-002 `done` (QA APROBADO en el intento 2, `reports/base-tests-password/qa-OPS-002.md`; BUG-001 cerrado). Siguiente tarea: `OPS-001` (Developer; entrada: este plan y `contracts/base-tests-password.md` §4.2 y §7.6.1), después `API-001` y `QA-001`. Backlog nuevo de QA: OBS-8 (`OSError` de `Path.resolve()` con rutas SQLite relativas que mezclan `:` y dígitos Unicode no ASCII, S4) y ajustes de redacción de DB-1, DB-3 y FX-C en el contrato. Parada pendiente: `web/angular.json` lleva un cambio ajeno que el usuario va a gestionar. Al cerrar la épica, el PM ejecuta la comprobación final de §7.6.3 con el `api/.env` real sin tocarlo. Preflight verificado el 2026-11-10: `main`, remoto accesible, `api/` y `web/` limpios, Python 3.13.5, identidad git configurada; `api/.env` y `api/data/app.db` locales (ignorados por git y fuera del alcance de las tareas).
