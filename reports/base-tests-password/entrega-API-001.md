## Entrega · API-001
**Intento:** 1
**Contrato:** contracts/base-tests-password.md (aprobado), §1 (ADR-004), §3, §4.1, §5, §7.2 a §7.5; contracts/adr/ADR-004-password-bytes.md (aceptado)
**Estado propuesto:** in_qa

**Cambios:**
- `api/app/core/security.py`:
  - Nueva `exceeds_password_limit(password: str) -> bool`: `len(password.encode("utf-8")) > MAX_PASSWORD_BYTES`, sin normalización Unicode. Única fuente del criterio.
  - `hash_password`: lanza `ValueError("La contraseña no puede superar los 72 bytes en UTF-8")` si `exceeds_password_limit`; en otro caso, igual que antes.
  - `verify_password`: la comprobación `exceeds_password_limit` (devuelve `False` sin llamar a bcrypt) y la codificación quedan dentro del `try` que captura `ValueError` (cubre hash malformado y `UnicodeEncodeError`).
  - `MAX_PASSWORD_BYTES` se conserva tal cual.
- `api/app/modules/auth/schemas.py`:
  - `UserCreate.password`: `Annotated[str, AfterValidator(_check_password_bytes)] = Field(min_length=8, description="Mínimo 8 caracteres y máximo 72 bytes en UTF-8 (límite de bcrypt).")`, **sin `max_length`**. `_check_password_bytes` lanza `PydanticCustomError("password_too_long", "La contraseña no puede superar los {max_bytes} bytes en UTF-8", {"max_bytes": MAX_PASSWORD_BYTES})` si `exceeds_password_limit`.
  - `LoginRequest.password` sin cambios (`min_length=1`, `max_length=MAX_PASSWORD_BYTES`, en caracteres). `UserRead`, `RefreshRequest` y `TokenResponse` sin cambios.
  - El import `from app.core.security import MAX_PASSWORD_BYTES, exceeds_password_limit` funciona y no hay ciclo: `security` solo importa `config`, `database` y `shared.exceptions`; la entidad `User` se importa de forma perezosa dentro de `get_current_user`.
- `api/tests/unit/test_password_bytes.py` (nuevo, 37 tests, nivel U): `exceeds_password_limit` (incluye NFC frente a NFD), `hash_password`/`verify_password` (L-07, no llama a bcrypt si supera el límite, texto no codificable), `UserCreate` R-01 a R-11 (solo los marcados U; R-12 a R-14 son de QA), mensaje exacto, `string_too_short`, mínimo en caracteres, `LoginRequest` (L-08) y esquema JSON de `UserCreate` y `LoginRequest` (§5).
- Sin cambios en `services.py`, `controllers.py`, `config.py`, `requirements.txt`, `conftest.py`, `test_health.py`, `test_config.py`, `contracts/`, `tasks/`, `web/`, `api/.env*` ni `api/data/`.

**Cómo probar:**
```powershell
cd api
python -m pytest -v
```
Los tests de nivel I (endpoint con `client`) son de QA-001. Para la verificación extremo a extremo (más abajo) usé un script desechable fuera del repo, ya borrado.

**Verificación realizada:**
- Entorno: Windows, Python 3.13.5; bcrypt 5.0.0, pydantic 2.13.5 (pydantic_core 2.46.5), starlette 1.7.0, fastapi 0.142.2, httpx2 2.16.0, pytest 9.2.0. Con bcrypt 4.x no se ha probado (no instalado); la defensa en profundidad hace que el resultado no dependa de la versión.
- `python -m pytest -v` completo, desde `api/`, sin avisos (53 existentes + 37 nuevos):

```
============================= test session starts =============================
platform win32 -- Python 3.13.5, pytest-9.2.0, pluggy-1.7.0 -- C:\Python313\python.exe
rootdir: C:\proves\g\api
plugins: anyio-4.15.1
collected 90 items

tests/test_health.py::test_health PASSED                                 [  1%]
tests/unit/test_config.py::test_co_01_ausente_usa_el_defecto PASSED      [  2%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-02-una-url] PASSED [  3%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-03-comas] PASSED [  4%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-04-espacios-y-vacios] PASSED [  5%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-05-json] PASSED [  6%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-06-json-con-espacios] PASSED [  7%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-07-vacia] PASSED [  8%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-07-espacios] PASSED [ 10%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-07-coma] PASSED [ 11%]
tests/unit/test_config.py::test_cors_origins_formatos[CO-07-json-vacio] PASSED [ 12%]
tests/unit/test_config.py::test_co_08_json_roto_aborta_sin_incluir_el_valor PASSED [ 13%]
tests/unit/test_config.py::test_co_09_elementos_no_str_se_rechazan PASSED [ 14%]
tests/unit/test_config.py::test_co_10_una_lista_ya_construida_pasa_sin_cambios PASSED [ 15%]
tests/unit/test_config.py::test_db_01_sin_database_url_usa_data_dir PASSED [ 16%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-02-punto-barra-cwd-actual] PASSED [ 17%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-02-punto-barra-DB-04-otro-cwd] PASSED [ 18%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-sin-punto-cwd-actual] PASSED [ 20%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-sin-punto-DB-04-otro-cwd] PASSED [ 21%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-en-la-raiz-cwd-actual] PASSED [ 22%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-en-la-raiz-DB-04-otro-cwd] PASSED [ 23%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-con-punto-punto-cwd-actual] PASSED [ 24%]
tests/unit/test_config.py::test_db_02_03_04_ruta_relativa_respecto_a_base_dir[DB-03-con-punto-punto-DB-04-otro-cwd] PASSED [ 25%]
tests/unit/test_config.py::test_db_02_settings_resuelve_respecto_a_api PASSED [ 26%]
tests/unit/test_config.py::test_db_05_url_absoluta_queda_identica PASSED [ 27%]
tests/unit/test_config.py::test_db_05_url_absoluta_posix_queda_identica PASSED [ 28%]
tests/unit/test_config.py::test_db_05_url_absoluta_con_unidad_queda_identica[sqlite:///C:/x/app.db] PASSED [ 30%]
tests/unit/test_config.py::test_db_05_url_absoluta_con_unidad_queda_identica[sqlite:///C:\\x\\app.db] PASSED [ 31%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-06-sqlite-vacia] PASSED [ 32%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-06-memoria] PASSED [ 33%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-06-uri-file] PASSED [ 34%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-07-postgresql] PASSED [ 35%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-no-parseable] PASSED [ 36%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-vacia] PASSED [ 37%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-solo-separador] PASSED [ 38%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-puerto-no-numerico] PASSED [ 40%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-puerto-vacio] PASSED [ 41%]
tests/unit/test_config.py::test_db_06_07_09_sin_fichero_sqlite_queda_identica[DB-09-ipv6-sin-cerrar] PASSED [ 42%]
tests/unit/test_config.py::test_db_08_conserva_los_parametros_de_consulta PASSED [ 43%]
tests/unit/test_config.py::test_db_10_crea_el_directorio_pero_no_el_fichero PASSED [ 44%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-06-sqlite-vacia] PASSED [ 45%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-06-memoria] PASSED [ 46%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-06-uri-file] PASSED [ 47%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-07-postgresql] PASSED [ 48%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-no-parseable] PASSED [ 50%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-vacia] PASSED [ 51%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-solo-separador] PASSED [ 52%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-puerto-no-numerico] PASSED [ 53%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-puerto-vacio] PASSED [ 54%]
tests/unit/test_config.py::test_db_11_sin_fichero_sqlite_no_crea_nada[DB-09-ipv6-sin-cerrar] PASSED [ 55%]
tests/unit/test_config.py::test_fx_01_secret_key_ausente_fuera_de_debug_no_crea_data PASSED [ 56%]
tests/unit/test_config.py::test_fx_02_configuracion_valida_no_crea_data PASSED [ 57%]
tests/unit/test_config.py::test_fx_03_debug_sin_secret_key_genera_clave_efimera PASSED [ 58%]
tests/unit/test_password_bytes.py::test_limite_es_72_bytes PASSED        [ 60%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_acepta_hasta_72_bytes[vacia] PASSED [ 61%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_acepta_hasta_72_bytes[72-ascii] PASSED [ 62%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_acepta_hasta_72_bytes[72-bytes-con-36-enes] PASSED [ 63%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_acepta_hasta_72_bytes[72-bytes-con-18-emojis] PASSED [ 64%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_rechaza_mas_de_72_bytes[73-ascii] PASSED [ 65%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_rechaza_mas_de_72_bytes[74-bytes-con-37-enes] PASSED [ 66%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_rechaza_mas_de_72_bytes[73-bytes-con-19-caracteres] PASSED [ 67%]
tests/unit/test_password_bytes.py::test_exceeds_password_limit_no_normaliza_unicode PASSED [ 68%]
tests/unit/test_password_bytes.py::test_hash_password_lanza_value_error_si_supera_el_limite[73-ascii] PASSED [ 70%]
tests/unit/test_password_bytes.py::test_hash_password_lanza_value_error_si_supera_el_limite[80-bytes-con-40-enes] PASSED [ 71%]
tests/unit/test_password_bytes.py::test_hash_password_de_72_bytes_se_verifica PASSED [ 72%]
tests/unit/test_password_bytes.py::test_hash_password_de_72_ascii_exactos PASSED [ 73%]
tests/unit/test_password_bytes.py::test_l_07_verify_password_con_mas_de_72_bytes_es_false PASSED [ 74%]
tests/unit/test_password_bytes.py::test_l_07_verify_password_no_acepta_un_prefijo_de_72_bytes PASSED [ 75%]
tests/unit/test_password_bytes.py::test_l_07_verify_password_con_hash_malformado_es_false PASSED [ 76%]
tests/unit/test_password_bytes.py::test_verify_password_no_llama_a_bcrypt_si_supera_el_limite PASSED [ 77%]
tests/unit/test_password_bytes.py::test_verify_password_con_texto_no_codificable_es_false PASSED [ 78%]
tests/unit/test_password_bytes.py::test_user_create_acepta_contrasenas_dentro_del_limite[R-02] PASSED [ 80%]
tests/unit/test_password_bytes.py::test_user_create_acepta_contrasenas_dentro_del_limite[R-04] PASSED [ 81%]
tests/unit/test_password_bytes.py::test_user_create_acepta_contrasenas_dentro_del_limite[R-05] PASSED [ 82%]
tests/unit/test_password_bytes.py::test_user_create_acepta_contrasenas_dentro_del_limite[R-08] PASSED [ 83%]
tests/unit/test_password_bytes.py::test_user_create_acepta_contrasenas_dentro_del_limite[R-10] PASSED [ 84%]
tests/unit/test_password_bytes.py::test_user_create_rechaza_mas_de_72_bytes[R-01] PASSED [ 85%]
tests/unit/test_password_bytes.py::test_user_create_rechaza_mas_de_72_bytes[R-03] PASSED [ 86%]
tests/unit/test_password_bytes.py::test_user_create_rechaza_mas_de_72_bytes[R-06] PASSED [ 87%]
tests/unit/test_password_bytes.py::test_user_create_rechaza_mas_de_72_bytes[R-07] PASSED [ 88%]
tests/unit/test_password_bytes.py::test_user_create_rechaza_mas_de_72_bytes[R-09] PASSED [ 90%]
tests/unit/test_password_bytes.py::test_user_create_mensaje_exacto_del_contrato PASSED [ 91%]
tests/unit/test_password_bytes.py::test_mas_de_72_caracteres_es_password_too_long_y_no_string_too_long PASSED [ 92%]
tests/unit/test_password_bytes.py::test_r_11_menos_de_8_caracteres_es_string_too_short PASSED [ 93%]
tests/unit/test_password_bytes.py::test_user_create_el_minimo_cuenta_caracteres_y_no_bytes PASSED [ 94%]
tests/unit/test_password_bytes.py::test_l_08_login_request_no_valida_bytes PASSED [ 95%]
tests/unit/test_password_bytes.py::test_l_08_login_request_mantiene_la_cota_de_72_caracteres PASSED [ 96%]
tests/unit/test_password_bytes.py::test_login_request_rechaza_password_vacia PASSED [ 97%]
tests/unit/test_password_bytes.py::test_json_schema_de_user_create_password PASSED [ 98%]
tests/unit/test_password_bytes.py::test_json_schema_de_login_request_password_no_cambia PASSED [100%]

============================= 90 passed in 1.68s ==============================
```
- Arranque: `python -c "from main import app"` desde `api/` con `DEBUG=true` y `DATABASE_URL` a una BD temporal (directorio en `%TEMP%`, borrado después) → `main.app OK: FastAPI`. También se importan sin error `app.modules.auth.schemas` y `app.core.security` como primer import en procesos distintos (sin ciclo). No se creó ni modificó `api/data/`.
- Verificación extremo a extremo (script desechable fuera del repo, ya borrado; `TestClient(main.app, raise_server_exceptions=False)` sobre una **copia** de `api/` sin `.env` ni `data/` y BD SQLite temporal; no se abrió ningún puerto ni se tocaron los procesos del usuario). Resultado final del script: `TODO OK`, todas las comprobaciones `[OK]`, ninguna `[FALLO]`. Cuerpos truncados; `input` recortado a 12 caracteres y sin tokens completos:

| Caso | Contraseña (bytes/caracteres) | Resultado |
|------|-------------------------------|-----------|
| R-01 | `"ñ"*40` (80/40) | 422 `{"type": "password_too_long", "loc": ["body","password"], "msg": "La contraseña no puede superar los 72 bytes en UTF-8", "ctx": {"max_bytes": 72}}` (no 500) |
| R-02 | `"a"*72` | 201 |
| R-03 | `"a"*73` | 422 `password_too_long` |
| R-04 | `"ñ"*36` (72/36) | 201 |
| R-05 | `"a"*70+"ñ"` (72/71) | 201 |
| R-06 | `"a"*71+"ñ"` (73/72) | 422 `password_too_long` |
| R-07 | `"ñ"*37` (74/37) | 422 `password_too_long` |
| R-08 | `"😀"*18` (72/18) | 201 |
| R-09 | `"😀"*18+"a"` (73/19) | 422 `password_too_long` |
| R-10 | `"ñ"*8` | 201 |
| R-11 | `"a"*7` | 422 `string_too_short` |
| R-12 | `"ñ"*10000` | 422 `password_too_long` |
| R-13 | tras 40 `ñ`, 73 `a` y `"a"*71+"ñ"`: mismo email/usuario con `Password123` | 201 en los tres (no 409: no queda usuario) |
| R-14 | `Password123` y duplicado | 201 y luego 409 `{"error": {"code": "conflict", ...}}` |
| L-01 | registrar y login con `"ñ"*36` | 200 con `access_token` y `refresh_token` |
| L-02 | usuario existente, login con `"ñ"*40` | 401 `{"error": {"code": "unauthorized", "message": "Credenciales inválidas"}}` |
| L-03 | email inexistente, login con `"ñ"*40` | 401 con cuerpo idéntico a L-02 |
| L-04 | cuenta con `"ñ"*36`, login con `"ñ"*36+"x"` (73 bytes) | 401 (sin truncamiento) |
| L-05 | login con `"😀"*20` (80/20) | 401 |
| L-06 | login con `"a"*73` | 422 `string_too_long` |
| — | login con `Password123` | 200 |

  Ninguna respuesta de los casos anteriores contiene `hashed_password`, `$2b$` ni `$2a$`.
- `/openapi.json` (§5): `UserCreate.password` = `{"type": "string", "minLength": 8, "title": "Password", "description": "Mínimo 8 caracteres y máximo 72 bytes en UTF-8 (límite de bcrypt)."}` (sin `maxLength`); `UserCreate.required = [username, email, password]`; `username` (min 3, max 80) y `email` (`format: email`) sin cambios; `LoginRequest.password` = `{"type": "string", "maxLength": 72, "minLength": 1, "title": "Password"}`; `register` 201 → `UserRead` y 422 → `HTTPValidationError`.
- Seguridad: no se loguean contraseñas ni tokens; el 422 sigue incluyendo `input` con la contraseña rechazada (fuera de alcance, §8/ADR-001).
- Sin servidores en ejecución propios; `api/data/` y `api/.env*` no se abrieron (la copia usada para el E2E no los contiene).

**Desviaciones del contrato:** ninguna en lo implementado (§4.1 y §5 se cumplen). Ver la observación sobre sustitutos aislados (§7.5) en el siguiente apartado.

**Deuda o riesgos detectados:**
- **Observación para QA y el PM (§7.5, S4), no causada por API-001:** un JSON con un sustituto aislado escapado (`"\ud800"`) en `password` devuelve **500** tanto en `register` como en `login`. La causa está antes de los esquemas y de `verify_password`: pydantic-core rechaza el JSON, el handler 422 por defecto de FastAPI devuelve en `detail[].input` el texto con el sustituto y `starlette.responses.JSONResponse.render` falla con `UnicodeEncodeError: 'utf-8' codec can't encode character '\ud800'`. Comprobado también con el código de `HEAD` de `security.py` y `schemas.py` (obtenido con `git show`, solo lectura): el 500 ya existía. Por tanto, la frase de §7.5 "en `login` debe dar 401, nunca 500" no se puede cumplir por HTTP con los ficheros de esta tarea; `verify_password("\ud800...", hash)` sí devuelve `False` (cubierto por un test unitario). Se resolvería con un handler de `RequestValidationError` (ADR-001, que además debería omitir `input` en `password`). No bloquea API-001; el PM decide si lo registra en el backlog o ajusta §7.5.
- Directamente sobre el esquema (Python, sin HTTP), `UserCreate(password="\ud800abcdefgh")` da `string_unicode` en `loc == ("password",)`: pydantic rechaza el sustituto antes del `AfterValidator`, de modo que no llega a `exceeds_password_limit` ni da `password_too_long` (coherente con §8: no se garantiza el 422 con tipo `password_too_long` para estos textos).
- `verify_password` sigue sin llamar a bcrypt cuando el usuario no existe (`authenticate_user` corta antes): hay una diferencia de tiempo entre usuario inexistente y contraseña errónea. Es previo y está fuera de alcance (no se toca `services.py`).
- Los hashes de `bcrypt` 4.x no se han probado (solo 5.0.0 instalada).
- Los tests con bcrypt real (`hash_de_36_enes` y `test_hash_password_de_72_ascii_exactos`) hacen dos hashes; el resto de la nueva batería es instantánea.

**Siguiente paso:** QA-001 (tests de integración R-xx, L-xx y §7.5 en `api/tests/integration/`) y, tras API-001, el PM actualiza el hueco de `AGENTS.md` y el caso de `qa.agent.md` sobre `max_length=72` (contrato §8).
