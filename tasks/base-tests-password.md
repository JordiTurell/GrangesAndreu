# EP-01 · Base de tests de la API y límite de contraseña en bytes
**Objetivo:** dotar a la API de infraestructura de tests y corregir el 500 de `POST /api/auth/register` con contraseñas multibyte de más de 72 bytes UTF-8 (ADR-004).  **Alcance:** API
**Supuestos:** ADR-004 es técnico y lo cierra el Arquitecto; sin `api/.env` se usan variables de sesión (`DEBUG=true`, `DATABASE_URL` temporal); el commit local f35a787 se sube con el primer push; el Developer escribe unitarios y QA los de integración.
**Fuera de alcance:** otros ADR, linter, CI, tests de otros endpoints, cambios en la Web, migraciones.

## Historias
- US-01 · Como desarrollador del equipo quiero una infraestructura de tests para la API con BD temporal para verificar cambios sin tocar la BD real ni la configuración local
  - [ ] `pytest` y `httpx` en `api/requirements.txt` con rangos `>=`
  - [ ] `api/tests/` con fixture de BD SQLite temporal (`get_db` sobrescrito) y `TestClient`
  - [ ] Test de humo de `GET /health` en verde
  - [ ] No se crea ni modifica `api/data/app.db` ni se requiere `api/.env`
- US-02 · Como usuario que se registra quiero que una contraseña que supera el límite de bcrypt en bytes se rechace con un error de validación claro para no recibir un 500
  - [ ] 40 letras "ñ" (80 bytes) en `register` → 422 claro, no 500
  - [ ] 72 bytes exactos se aceptan y 73 se rechazan con 422
  - [ ] `login` con más de 72 bytes no devuelve 500
  - [ ] Tests unitarios (Developer) y de integración (QA), con el límite exacto
  - [ ] ADR-004 aceptado y contrato de auth actualizado

## Tablero
| ID | Capa | Tarea | Responsable | Depende de | Prio | Tamaño | Estado | Bugs |
|----|------|-------|-------------|------------|------|--------|--------|------|
| ARQ-001 | arq | Resolver ADR-004 y contrato del límite de contraseña en bytes | arquitecto | — | P0 | S | done | — |
| OPS-001 | ops | Infraestructura de tests de la API (pytest, httpx, fixture de BD temporal) | developer | — | P0 | S | todo | — |
| API-001 | api | Rechazar con 422 las contraseñas que superan 72 bytes UTF-8 (ADR-004) | developer | ARQ-001, OPS-001 | P0 | S | todo | — |
| QA-001 | qa | Tests de integración del límite de contraseña en bytes | qa | API-001 | P1 | S | todo | — |

## Camino crítico y paralelización
```
ARQ-001 ──────────┐
                  ├→ API-001 → QA-001
OPS-001 ──────────┘
```
`ARQ-001` y `OPS-001` son independientes, pero se ejecutan en serie (un único árbol de trabajo y precondición de `api/` limpio). Orden de ejecución: ARQ-001 → OPS-001 → API-001 → QA-001.

## Riesgos
| ID | Riesgo | Prob. | Impacto | Mitigación |
|----|--------|-------|---------|------------|
| R-01 | Importar `main` lanza `pip install` de lo que falte (incluidos `pytest` y `httpx`) y necesita red | alta | baja | `pip install -r requirements.txt` en OPS-001 antes de `pytest`; documentarlo en la entrega |
| R-02 | `settings` y `engine` son singletons y el lifespan llama a `init_db()` sobre el engine global: sobrescribir `get_db` no basta para no tocar `api/data/app.db` | alta | media | `DEBUG` y `DATABASE_URL` temporal antes de importar la app; QA comprueba que `app.db` no cambia |
| R-03 | SQLite con WAL en Windows puede bloquear el borrado del fichero temporal | media | baja | Liberar el engine en el teardown; directorios temporales de pytest |
| R-04 | bcrypt 4.x truncaba en silencio y 5.x lanza `ValueError` | media | media | Validar en bytes con independencia de la versión de bcrypt |
| R-05 | El 422 sigue el formato por defecto mientras ADR-001 esté pendiente | baja | baja | Los tests comprueban el código 422 y el campo, no el texto del envelope |

## Siguiente paso
Invocar al Arquitecto con `ARQ-001` (entrada: este plan, `contracts/auth.md` y `contracts/adr/README.md`). Preflight del entorno ya verificado: `main`, remoto accesible, `api/` y `web/` limpios, Python 3.13.5, Node 26.0.0 (`nvm use 26.0.0`), `web/node_modules` presente, identidad git configurada, sin `api/.env`.
