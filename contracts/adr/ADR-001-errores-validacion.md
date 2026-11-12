# ADR-001 · Formato de los errores de validación (422)
**Estado:** aceptado   **Fecha:** 2026-11-11
**Épica:** EP-02 `auth-completo` (contrato: [../auth-completo.md](../auth-completo.md) §3, §5, §6.6 y §7.8)

## Contexto
- Los errores de dominio usan `{"error": {"code", "message"}}` (`shared/exceptions.py`); los 422 de validación usan el formato por defecto de FastAPI, `{"detail": [{"loc", "type", "msg", "input", "ctx"}]}`.
- `input` repite el valor rechazado: en `register` y `reset-password` es la **contraseña** o el **token** (entrada de [auth-completo.md](../auth-completo.md) §8).
- BUG-004 (EP-01): un sustituto Unicode aislado (`"\ud800"`) en el JSON hace que el handler por defecto dé **500** al serializar `input` (y el mensaje de `email_validator` puede incluir el valor).
- Otras respuestas de error del framework tampoco son envelope: 404 y 405 de Starlette (`{"detail": "Not Found"}`), 500 (texto plano) y fallos de red (`status 0`). Un cliente necesita un normalizador aunque la API cambie.
- Impacto en tests existentes (EP-01): `api/tests/integration/helpers.py` (`comprobar_422_password`), `test_register_password_bytes.py` (2 sitios) y `test_seguridad_y_contrato.py` (esquema `HTTPValidationError`).

## Opciones
| Opción | Pros | Contras |
|--------|------|---------|
| A. Mantener `detail` y normalizar solo en el Front | Sin cambios de API ni de tests | El Front no puede quitar de la respuesta lo que la API ya envía (`input` con contraseña/token); BUG-004 sigue; dos formas de error en todos los módulos futuros |
| B. Handler propio de `RequestValidationError` con envelope `{"error": {"code": "validation_error", "message", "fields": [...]}}`, sin `input` | Una sola forma de error de dominio; corta el eco de secretos y BUG-004 en un punto; cambio pequeño y localizado | Cambia el contrato aprobado del 422 (los `detail` de EP-01 y de §7.4 pasan a `fields`); retoca 3 ficheros de tests de EP-01 |
| C. Responder con ambas formas (`detail` y `error`) | Compatible hacia atrás | Dos fuentes de verdad, `input` seguiría en `detail` o habría que quitarlo igualmente |

## Decisión
**Opción B**, más un normalizador único en el Front (que además cubre 404/405, 5xx y red).

1. **Estado** 422 (sin cambios). **Cuerpo:**
   ```json
   {"error": {"code": "validation_error", "message": "Los datos enviados no son válidos",
              "fields": [{"loc": ["body", "new_password"], "code": "password_too_long",
                          "message": "La contraseña no puede superar los 72 bytes en UTF-8",
                          "ctx": {"max_bytes": 72}}]}}
   ```
   `fields[]` equivale al `detail[]` de Pydantic con `type → code` y `msg → message`, **sin `input`**; `ctx` es opcional (se omite si queda vacío).
2. **Reglas del handler** (`app/shared/validation.py`, registrado desde `register_exception_handlers`, de modo que cualquier `FastAPI()` que lo llame —incluidas las de test, patrón P-1— lo hereda):
   - Nunca incluye `input`, `url` ni el objeto de error. `ctx` solo conserva valores `str`, `int`, `float`, `bool` o `None` y descarta la clave `error`.
   - Toda cadena emitida (`message`, elementos de `loc`) se sanea con `s.encode("utf-8", "replace").decode("utf-8")`: **ningún contenido del usuario puede provocar un 500** (BUG-004).
   - Para campos sensibles (último elemento de `loc` en `password`, `new_password`, `token`, `refresh_token`) el `message` de Pydantic solo se usa si `code` ∈ {`missing`, `string_type`, `string_too_short`, `string_too_long`, `password_too_long`}; en otro caso es «Valor no válido».
   - No registra el cuerpo de la petición ni los errores con su contenido.
3. **OpenAPI:** las operaciones con cuerpo (`register`, `login`, `refresh`, `forgot-password`, `reset-password`) declaran `responses={422: {"model": ValidationErrorResponse}}`; `HTTPValidationError` y `ValidationError` desaparecen del `/openapi.json` (contrato §5).
4. **Front:** `normalizeApiError` acepta el envelope, el `detail` por defecto (transición hasta API-005 y 404/405), red y 5xx; el texto de los errores de campo lo pone el Front por `(campo, code)` (contrato §6.6). Por eso WEB-001 no depende de API-005.
5. Fuera de alcance: envelope para 404/405 (handler de `StarletteHTTPException`) y 500; backlog. Observación relacionada y no cubierta: un `username` con sustitutos aislados (válido para el esquema) puede dar 500 al insertar en SQLite; backlog (validador de UTF-8 en `UserCreate.username`).

## Consecuencias
- **API (API-005):** `app/shared/validation.py` (nuevo), `app/shared/exceptions.py`, `app/modules/auth/controllers.py` (`responses`), tests unitarios nuevos y ajuste mecánico de los 3 ficheros de integración de EP-01. Debe ir **después** de API-003 (para declarar `responses` en los 5 endpoints de una vez) y **antes** de QA-003 (para que QA escriba contra la forma final).
- **Contratos:** [auth.md](../auth.md) y [auth-completo.md](../auth-completo.md) actualizados (marcados «ADR-001, API-005»); `base-tests-password.md` conserva el texto histórico de EP-01 (`detail`), superado por este ADR cuando API-005 esté hecha.
- **Web:** `ApiError`, `normalizeApiError`, `validation-messages.ts` (WEB-001).
- **Tests:** criterios VE-01 a VE-10 (contrato §7.8) y FE-ER-* (§7.7).
- **Datos / migraciones:** ninguno.

## Tareas derivadas
API-005 (handler), QA-003 (criterios VE), WEB-001 (normalizador).
