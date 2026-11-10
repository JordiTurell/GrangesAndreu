# ADR-004 · Límite de contraseña en bytes UTF-8 (bcrypt)
**Estado:** aceptado   **Fecha:** 2026-11-10
**Épica:** EP-01 `base-tests-password` (contrato: [../base-tests-password.md](../base-tests-password.md))

## Contexto
- bcrypt solo procesa los primeros 72 **bytes** de la contraseña. `api/app/core/security.py` declara `MAX_PASSWORD_BYTES = 72`, pero `api/app/modules/auth/schemas.py` lo usa como `max_length` de `UserCreate.password` y `LoginRequest.password`, que cuenta **caracteres**.
- Una contraseña de 40 letras "ñ" (40 caracteres, 80 bytes) pasa la validación y llega a `hash_password`. Con bcrypt 5.x (versión instalada, 5.0.0) `hashpw` lanza `ValueError` y `POST /api/auth/register` responde **500**. Con bcrypt 4.x (`requirements.txt` pide `>=4.2.0`) se truncaría en silencio a 72 bytes, incluso en mitad de un carácter multibyte.
- `verify_password` captura `ValueError` y devuelve `False`, de modo que `POST /api/auth/login` con esa misma contraseña ya responde 401 (no 500) en bcrypt 5.x; en 4.x truncaría y compararía solo el prefijo.
- ADR-001 (formato de los 422) sigue `pendiente`: los errores de validación usan el formato por defecto de FastAPI (`{"detail": [...]}`) y no hay handler para `RequestValidationError`.
- Los errores de dominio (`AppError`) usan el envelope `{"error": {"code", "message"}}` y no existe una excepción de dominio para 422.

## Opciones
**(a) Dónde validar el límite**

| Opción | Pros | Contras |
|--------|------|---------|
| A. Esquema Pydantic (`UserCreate`) | El 422 sale del mecanismo ya vigente de FastAPI, sin tocar controladores ni handlers; se rechaza antes de consultar la BD o hashear; aparece en OpenAPI; mismo formato que el resto de validaciones | Hay que contar bytes con un validador propio (`max_length` no sirve) |
| B. Servicio (`register_user`) | Lógica de negocio centralizada | Exige una excepción de dominio 422 nueva con envelope, lo que prejuzga ADR-001; la validación ocurre tras la del esquema y duplica límites |
| C. Solo capturar `ValueError` de `hash_password` | Cambio mínimo | Depende de la versión de bcrypt (4.x trunca sin error); el mensaje llega tarde y mal formado |
| D. Pre-hash (SHA-256 + base64) antes de bcrypt | Elimina el límite | Cambia el esquema de hash: invalida los hashes existentes y exige migración; fuera de alcance |
| E. Truncar en silencio a 72 bytes | Nunca falla | Puede cortar un carácter multibyte, debilita la contraseña sin avisar y es opaco para el usuario |

**(c) Login**
- L1. `LoginRequest` comparte el límite en bytes y responde 422. Cambia el comportamiento actual de login y expone la regla en un endpoint de credenciales.
- L2. `LoginRequest` no valida bytes: mantiene su cota actual (1-72 caracteres) y `verify_password` devuelve `False` para lo que supere 72 bytes (401 uniforme). No cambia el contrato de login.

## Decisión
1. **Dónde (opción A, con defensa en profundidad):** el límite se valida en el esquema `UserCreate.password` mediante un validador (`AfterValidator`) que sustituye al `max_length`. Además, `core/security.py` protege `hash_password` y `verify_password` con el mismo criterio para no depender de la versión de bcrypt.
2. **Cómo se cuenta:** en bytes de la codificación UTF-8 de la cadena recibida, `len(password.encode("utf-8")) > MAX_PASSWORD_BYTES`. Sin normalización Unicode (NFC/NFD): se hashean exactamente los bytes recibidos. Un único helper en `core/security.py`, `exceeds_password_limit(password: str) -> bool`, es la fuente de este criterio y lo usan el esquema, `hash_password` y `verify_password`. Se rechaza lo que **supere** 72 bytes: 72 exactos se aceptan, 73 se rechazan.
3. **Mínimo:** `min_length=8` se mantiene en **caracteres** (un mínimo en bytes aceptaría 4 caracteres de 2 bytes). No se tocan reglas de complejidad.
4. **Forma del 422 de `register`:** error de validación estándar de FastAPI (`detail`), generado con `PydanticCustomError` para tener un `type` estable y un mensaje sin el prefijo `Value error,`:
   - status `422`; `detail[0].loc == ["body", "password"]`
   - `detail[0].type == "password_too_long"`
   - `detail[0].msg == "La contraseña no puede superar los 72 bytes en UTF-8"` (mensaje en español, bytes en el texto)
   - `detail[0].ctx == {"max_bytes": 72}`
   - Se aplica a **cualquier** contraseña de más de 72 bytes, incluidas las de más de 72 caracteres (se elimina el `max_length`, que producía `string_too_long`); así el cliente recibe siempre el mismo error. La contraseña de menos de 8 caracteres sigue siendo `string_too_short`.
   - Cuando ADR-001 cambie el envelope, solo cambia la serialización; el `type` y el `loc` se conservan como identificador del caso.
5. **Login (opción L2):** `LoginRequest.password` no comparte la validación en bytes y queda igual (`min_length=1`, `max_length=72` caracteres, cota gruesa de tamaño: un carácter ocupa al menos un byte, luego ninguna contraseña válida supera 72 caracteres). `verify_password` devuelve `False`, sin consultar bcrypt, si la contraseña supera 72 bytes, de forma que:
   - una contraseña de ≤72 caracteres y >72 bytes (p. ej. 40 "ñ") responde **401** `unauthorized` "Credenciales inválidas", con usuario existente o no, igual que cualquier contraseña errónea (sin enumeración de cuentas);
   - nunca se acepta por truncamiento un prefijo de 72 bytes (ni en bcrypt 4.x);
   - la codificación y el control permanecen dentro del `try` que captura `ValueError` (incluye `UnicodeEncodeError`), de modo que un texto no codificable en UTF-8 sigue dando `False` y 401.
   Más de 72 caracteres sigue siendo 422 `string_too_long` por la cota existente; no forma parte de esta decisión.
6. **`hash_password`:** lanza `ValueError` si la contraseña supera 72 bytes, en lugar de depender de bcrypt (que en 4.x truncaría). Es una invariante interna: no es alcanzable por HTTP porque el esquema ya lo rechaza.

## Consecuencias
- **API:** cambian `schemas.py` (`UserCreate.password`) y `core/security.py` (helper, `hash_password`, `verify_password`). Sin cambios en controladores, servicios, entidades, handlers ni migraciones. El OpenAPI de `UserCreate.password` pierde `maxLength: 72` y gana una `description` con el límite en bytes; `LoginRequest` no cambia.
- **Comportamiento:** `register` con >72 bytes pasa de 500 (bcrypt 5.x) a 422; `register` con más de 72 caracteres ASCII pasa de `string_too_long` a `password_too_long`; `login` no cambia salvo que la decisión es ahora explícita y no depende de la versión de bcrypt.
- **Datos existentes:** los hashes ya guardados no cambian. No se espera que existan usuarios creados con contraseñas de más de 72 bytes (en bcrypt 5.x el alta daba 500). Si existieran, creados con bcrypt 4.x y truncados, ya no podrían iniciar sesión con la contraseña completa; el proyecto no tiene despliegue con datos reales y se asume que no hay ninguno.
- **Web (futura):** el formulario de registro debe medir bytes con `TextEncoder` (el `maxlength` de HTML cuenta unidades UTF-16) y mostrar el error de `detail` con `type == "password_too_long"`.
- **Seguridad:** el 422 por defecto de FastAPI devuelve en `detail[].input` el valor rechazado, es decir, la contraseña en claro enviada por el propio cliente. No se resuelve aquí (requiere un handler de `RequestValidationError`, es decir, ADR-001); queda como entrada para ADR-001: omitir `input` en los errores del campo `password`.
- **Tests:** la verificación comprueba bytes, no caracteres; los casos límite (72/73 bytes, 71 caracteres con 72 bytes, 72 caracteres con 73 bytes, emoji de 4 bytes) están en `contracts/base-tests-password.md` §7. Las pruebas comprueban `status`, `loc`, `type` y la presencia de "72 bytes" en `msg`, no el envelope completo.
- **Documentación:** al cerrarse API-001, el PM actualiza el hueco conocido de `AGENTS.md` ("El límite de contraseña (`max_length=72`) cuenta caracteres…") y el caso conocido de `qa.agent.md`.

## Tareas derivadas
- OPS-001: infraestructura de tests de la API (requisito previo de los tests de este ADR).
- API-001: implementar el límite en bytes en `schemas.py` y `core/security.py` con tests unitarios.
- QA-001: tests de integración de `register` y `login`.
- ADR-001 (pendiente, fuera de alcance): formato de los 422 y eliminación de `input` en el campo `password`.
