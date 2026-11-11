# Informe QA · base-tests-password · QA-001 (EP-01)
**Veredicto:** APROBADO
**Alcance verificado:** QA-001 (tests de integración de `register`/`login` con el límite en bytes, regresión de arranque ST-01 a ST-10 y `get_settings()`), y revisión de cierre de US-01, US-02 y US-03 de la épica.
**Estado del árbol (`git status --porcelain -uall`, HEAD `9a8c2c0`, rama `main`):** modificados `api/app/core/security.py`, `api/app/modules/auth/schemas.py`, `api/requirements.txt`, `tasks/base-tests-password.{json,md}`; nuevos `api/tests/**` (`conftest.py`, `test_health.py`, `unit/`, `integration/`) y `reports/base-tests-password/{entrega-API-001,entrega-OPS-001,qa-API-001,qa-OPS-001}.md`. `api/app/core/config.py` ya está en HEAD (OPS-002).
**Estado propuesto por tarea:** QA-001 → `done`
**Veredicto de la épica EP-01:** US-01 (base de tests y arranque), US-02 (límite de contraseña en bytes) y US-03 (verificación de integración y regresión) cumplidas; ver "Veredicto de la épica" al final.

## Resumen
- Suite completa final (`cd api; python -m pytest -q`): **189 passed in 51.76s** = 90 de OPS-001/API-001 (`test_health` 1, `unit/test_config` 52, `unit/test_password_bytes` 37) + **99 de integración de QA-001** (`test_register_password_bytes` 24, `test_login_password_bytes` 16, `test_seguridad_y_contrato` 12, `test_auth_regresion` 7, `test_config_startup` 40). Sin fallos, errores, omitidos ni xfail. (Las cifras provisionales "183", "93" y "186" de versiones anteriores de este informe estaban desfasadas; la cuenta real viene de `--collect-only`.)
- Test añadido para cerrar un hueco que detectó MS07: `test_login_con_hash_corrupto_en_la_bd_da_401_sin_500` (3 casos; L-07 a nivel HTTP) en `test_login_password_bytes.py`.
- Mutaciones: auth MS01 a MS17 (16 detectadas por integración; MS06 solo por unitarios, con causa) y configuración MC01 a MC14 (14 detectadas por integración; MC08 verificada a mano). Ninguna superviviente sin explicar.
- Robustez: `-W error`, orden inverso, orden aleatorio, cada fichero de integración suelto y otro cwd, todo en verde (ver "Registro de robustez").
- Aislamiento (audit hook, 58 conexiones `sqlite3.connect`): todas bajo `pytest-of-*`; ninguna a `api/data/app.db`. Metadatos de `app.db` y `app.db-wal` idénticos antes y después.
- Defectos nuevos: ninguno. Abiertos de la épica, todos S4 y no bloqueantes: BUG-002, BUG-003, BUG-004, BUG-005 y OBS-8 (ver "Defectos").

## Trazabilidad (contrato §7 → test → resultado)
Todos los resultados provienen de la suite `-v` de esta sesión (`run1-v`: 183 passed). Fichero abreviado: reg = `test_register_password_bytes.py`, log = `test_login_password_bytes.py`, seg = `test_seguridad_y_contrato.py`, rgr = `test_auth_regresion.py`, cfg = `test_config_startup.py`.

| ID contrato | Test (fichero) | Resultado |
|-------------|----------------|-----------|
| R-01, R-03, R-06, R-07, R-09, R-12 | `test_register_rechaza_mas_de_72_bytes_con_422[...]` (reg): 422, `loc`, `type == password_too_long`, "72 bytes", 0 usuarios | PASS |
| R-02, R-04, R-05, R-08, R-10 | `test_register_acepta_hasta_72_bytes[...]` (reg): 201, campos de `UserRead`, hash guardado verifica la contraseña completa | PASS |
| R-11 | `test_r_11_menos_de_8_caracteres_sigue_dando_string_too_short` (reg) | PASS |
| R-13 | `test_r_13_la_contrasena_rechazada_no_deja_usuario[R-01,R-03,R-06]` (reg): 201 posterior y recuento con `db_session` | PASS |
| R-14 | `test_r_14_password123_se_registra_y_el_duplicado_da_409`, `test_r_14_duplicados_sin_distinguir_mayusculas` (reg) | PASS |
| Extra §7.5 | `test_contrasena_larga_con_email_existente_no_revela_la_cuenta`, `test_el_limite_cuenta_los_bytes_recibidos_sin_normalizar_unicode`, `test_el_resto_de_validaciones_del_422_no_cambia` (reg) | PASS |
| L-01 | `test_l_01_registra_con_72_bytes_y_entra_con_la_misma` (log) | PASS |
| L-02, L-03 | `test_l_02_...`, `test_l_03_...`, `test_l_02_l_03_los_401_son_indistinguibles` (log) | PASS |
| L-04 | `test_l_04_no_se_acepta_un_prefijo_de_72_bytes[bcrypt-real/bcrypt-que-trunca x 2]` (log; simula bcrypt 4.x, R-04) | PASS |
| L-05 | `test_l_05_emojis_por_encima_de_72_bytes_dan_401_...` (log) | PASS |
| L-06 | `test_l_06_mas_de_73_caracteres_dan_422_string_too_long`, `test_login_la_cota_de_caracteres_sigue_vigente` (log) | PASS |
| L-07, L-08, §7.4 | Unitarios del Developer (`unit/test_password_bytes.py`, 37 tests) | PASS (regresión) |
| §7.5 sin 500 ni hash | `test_ninguna_respuesta_de_auth_expone_hash_ni_da_500` (12 respuestas, 201/409/422/200/401), `test_el_vigilante_*` (5), `comprobar_respuesta` en cada llamada de `ClienteApi` | PASS |
| §7.5 secretos en log | `test_la_contrasena_no_aparece_en_logs_ni_en_la_salida` (seg) | PASS |
| §5 OpenAPI | `test_openapi_user_create_password_*`, `test_openapi_login_request_password_*`, `test_openapi_rutas_de_register_y_login[2]`, `test_openapi_user_read_no_expone_hashed_password` (seg) | PASS |
| Regresión auth | `test_flujo_register_login_me_refresh`, 401 de capitalización, tokens de tipo incorrecto, `/me` sin token/inválido, usuario desactivado, BD limpia por test x2 (rgr) | PASS |
| ST-01 | `test_st_01_dotenv_con_el_formato_de_env_example_arranca`, `test_st_01_la_app_completa_arranca_...` (cfg) | PASS |
| ST-02 | `test_st_02_dotenv_con_cors_en_lista_json`, `test_st_02_la_app_completa_arranca_...` (cfg) | PASS |
| ST-03 | `test_st_03_cors_como_variable_de_entorno_sin_dotenv`, `..._sin_cors_origins_usa_el_defecto`, `..._la_variable_de_entorno_prevalece_sobre_dotenv` (cfg) | PASS |
| ST-04, ST-05 | `test_st_04_05_secret_key_ausente_fuera_de_debug_no_crea_directorios`, `test_st_04_secret_key_ausente_con_dotenv_en_la_copia` (cfg) | PASS |
| ST-06 | `test_st_06_cors_json_roto_no_crea_directorios` (cfg) | PASS |
| ST-07 | `test_st_07_database_url_relativa_se_resuelve_respecto_a_api` (cfg) | PASS |
| ST-08 | `test_st_08_database_url_absoluta_queda_identica_y_crea_su_directorio` (cfg) | PASS |
| ST-09 | `test_st_09_url_sin_fichero_sqlite_queda_identica_y_no_crea_nada` (cfg) | PASS |
| ST-10 | `test_st_10_con_variables_validas_nada_cambia` (cfg, `-W error::RuntimeWarning`) | PASS |
| FX-B, FX-C | `test_fx_b_otras_configuraciones_invalidas_no_crean_directorios`, `test_fx_c_sin_database_url_se_crea_data_como_siempre` (cfg) | PASS |
| BUG-001 (regresión) | `test_bug_001_url_no_parseable_no_rompe_settings_ni_filtra_la_clave` (cfg) | PASS |
| `get_settings()` / M14 | 5 tests `test_get_settings_*` (cfg): crea directorio pero no fichero, defecto `data/`, configuración inválida no deja directorios, mensaje de CORS sin el valor | PASS |

## Resultados por nivel
- **API (integración):** `register` (R-01 a R-14 y los extra de §7.5) y `login` (L-01 a L-06) con `TestClient` sobre una BD SQLite por test: 72 bytes aceptados, 73 bytes rechazados con 422 `password_too_long` sin crear usuario, límite en bytes sin normalizar Unicode, 401 indistinguibles ante cuenta inexistente o contraseña errónea, prefijo de 72 bytes no aceptado (con bcrypt real y con un `bcrypt` 4.x simulado que trunca), hash corrupto en la BD → 401 sin 500. **PASS** (24 + 16 tests).
- **Contrato:** `/openapi.json` coincide con §5 (`UserCreate.password` y `LoginRequest.password`: cotas y `description` con "72 bytes", rutas y métodos de `register`/`login`, `UserRead` sin `hashed_password`). **PASS** (`test_seguridad_y_contrato`, 12 tests). Los códigos de estado y el `type` del 422 son los del contrato.
- **Seguridad:** ninguna de las 12 respuestas auditadas de `register`/`login` (201/409/422/200/401) expone `hashed_password` ni `$2b$` ni da 500 (`comprobar_respuesta` en cada llamada de `ClienteApi`); la contraseña no aparece en logs ni en la salida; sin enumeración de cuentas ni con contraseña larga y correo ya registrado; `MS15` (exponer el hash), `MS16` (distinguir usuario inexistente) y `MS17` (imprimir la contraseña) detectadas. **PASS**. Riesgos preexistentes sin cambios, anotados en el backlog (hash en el log SQL con `DEBUG=true`, refresh tokens sin rotación, 422 con `input`). **PASS** con observaciones S4.
- **Regresión:** flujo `register` → `login` → `/me` → `refresh`, 401 de capitalización, tokens de tipo incorrecto, `/me` sin token o con token inválido, usuario desactivado, BD limpia por test; unitarios de OPS-001/API-001 (90) y `test_health`. **PASS** (7 + 90 + 1).
- **Arranque y configuración (ST-01 a ST-10, FX-B, FX-C, BUG-001, `get_settings()`):** 40 tests, 14 de 14 mutaciones de configuración detectadas por integración. **PASS**.
- **Robustez:** `-W error`, orden inverso, orden aleatorio (semilla 12345), cada fichero de integración suelto y `python -m pytest api/tests` desde la raíz: 189 passed en todos los casos. **PASS**. Sin tests inestables observados en 5 ejecuciones completas de esta sesión (más las de las sesiones previas).
- **Aislamiento:** audit hook de `sqlite3.connect` durante la suite: 58 conexiones, todas bajo `pytest-of-*`; ninguna a `api/data/app.db`. Metadatos de `api/data/app.db` y `app.db-wal` idénticos antes y después de 5 ejecuciones completas. Los tests de configuración trabajan sobre una copia de `api/` sin `.env` ni `data/`. **PASS**.
- **Web, Integración Front↔API y SSR:** no aplican (la épica no toca `web/`); no se ejecutaron `npm run build`, `npm test` ni servidores.

## Mutaciones
### Grupo auth (MS01 a MS17; integración 56 tests + unitarios 90)
Control sin mutar M00: 56 passed / 90 passed.

| ID | Mutación | Integración | Unitarios | Resultado |
|----|----------|-------------|-----------|-----------|
| MS01 | contar caracteres en lugar de bytes | 12 failed | 10 failed | DETECTADA |
| MS02 | `>=` en lugar de `>` | 12 failed | 9 failed + 5 errors | DETECTADA |
| MS03 | restaurar `max_length=72` en `UserCreate.password` | 4 failed | 3 failed | DETECTADA |
| MS04 | `verify_password` sin guardia de 72 bytes | 2 failed | 1 failed | DETECTADA |
| MS05 | `verify_password` autentica por truncamiento | 6 failed | 3 failed | DETECTADA |
| MS06 | `hash_password` sin guardia | 56 passed | 2 failed | SOBREVIVE a integración; la detectan los unitarios (causa: el validador del esquema rechaza antes con 422, así que la guardia de `hash_password` es defensa en profundidad inalcanzable por HTTP) |
| MS07 | `verify_password` no captura `ValueError` | 3 failed (tras añadir `test_login_con_hash_corrupto_en_la_bd_da_401_sin_500`; antes 56 passed) | 2 failed | DETECTADA (en la primera pasada sobrevivía a integración: ningún test metía un hash inválido en la BD; hueco cerrado en esta sesión) |
| MS08 | `UserCreate` sin validador de bytes | 13 failed | 7 failed | DETECTADA |
| MS09 | tipo `string_too_long` en lugar de `password_too_long` | 11 failed | 6 failed | DETECTADA |
| MS10 | mensaje del 422 sin "72 bytes" | 11 failed | 6 failed | DETECTADA |
| MS11 | `description` del esquema sin "72 bytes" | 1 failed | 1 failed | DETECTADA |
| MS12 | `UserCreate` `min_length=1` | 3 failed | 3 failed | DETECTADA |
| MS13 | `LoginRequest` valida bytes | 11 failed | 1 failed | DETECTADA |
| MS14 | `LoginRequest` sin `max_length` | 4 failed | 2 failed | DETECTADA |
| MS15 | `UserRead` expone `hashed_password` | 30 failed + 5 errors | 0 | DETECTADA (solo integración) |
| MS16 | `login` distingue usuario inexistente (enumeración) | 3 failed | 0 | DETECTADA (solo integración) |
| MS17 | `register` imprime la contraseña | 1 failed | 0 | DETECTADA (solo integración) |

### Grupo configuración (MC01 a MC14; integración `test_config_startup.py` 40 tests + unitarios 90)
Control sin mutar M00c: 40 passed / 90 passed. Las 14 mutaciones son **DETECTADAS por integración**.

| ID | Mutación | Integración | Unitarios | Primer detector de integración |
|----|----------|-------------|-----------|--------------------------------|
| MC01 | quitar `NoDecode` (JSON del `.env.example` en comas) | 10 failed | 7 failed | `test_st_01_dotenv_con_el_formato_de_env_example_arranca` |
| MC02 | `DATABASE_URL` relativa respecto al cwd | 8 failed | 11 failed | `test_st_01_dotenv_...` (cwd distinto de la copia) |
| MC03 | `ensure_database_directory` dentro del validador (antes de la clave) | 5 failed | 3 failed | `test_st_04_05_..._no_crea_directorios[ST-04, ST-05]` |
| MC04 | `get_settings` no crea el directorio (M14) | 13 failed | 0 (90 passed) | `test_st_01_dotenv_...`; también los `test_get_settings_*`; **solo integración** |
| MC05 | `except` solo `ArgumentError` (regresión de BUG-001) | 3 failed | 6 failed | `test_bug_001_url_no_parseable_...[puerto-no-numerico, puerto-vacio, ipv6-sin-cerrar]` |
| MC06 | `parse_cors_origins` sin `strip` (M05, OBS-3 de qa-OPS-001) | 1 failed | 0 (90 passed) | `test_st_03_cors_como_variable_de_entorno_sin_dotenv[CO-02-json-con-espacios-alrededor]`; **solo integración** (cierra OBS-3) |
| MC07 | mensaje de CORS con el valor (M12b) | 1 failed | 0 (90 passed) | `test_get_settings_el_error_de_cors_no_incluye_el_valor_en_el_mensaje`; **solo integración** (cierra BUG-002) |
| MC08 | URL absoluta re-renderizada (`C:` pasa a `C%3A`) | "no tests ran" (la guardia F-2 aborta la sesión, rc 2) | "no tests ran" | Verificado a mano sobre copia con F-2 neutralizada: 5 failed de integración (`st_08`, `st_10`, `fx_c`, 2 `get_settings`) y 4 de unitarios. Detectada de ambos modos |
| MC09 | `ensure_database_directory` crea también el fichero | 3 failed | 1 failed | `test_st_08_...`, `test_get_settings_valida_crea_el_directorio_pero_no_el_fichero` |
| MC10 | defecto de CORS vacío | 1 failed | 1 failed | `test_st_03_sin_cors_origins_usa_el_defecto` |
| MC11 | sin `DATABASE_URL` usa `BASE_DIR` y no `DATA_DIR` | 2 failed | 1 failed | `test_fx_c_...`, `test_get_settings_sin_database_url_crea_data_dir_como_siempre` |
| MC12 | clave efímera aunque haya `SECRET_KEY` | 1 failed | 0 (90 passed, 14 avisos) | `test_st_10_con_variables_validas_nada_cambia` (`-W error::RuntimeWarning`); **solo integración** |
| MC13 | CORS abierto a `*` en `main.py` | 2 failed | 0 (90 passed) | `test_st_01_la_app_completa_...` y `test_st_02_la_app_completa_...` (preflight de origen ajeno); **solo integración** |
| MC14 | `ValueError` de CORS sin `from None` y con el valor | 1 failed | 1 failed | `test_get_settings_el_error_de_cors_no_incluye_el_valor_en_el_mensaje` |

Nota sobre MC08: el script de mutaciones marca "detectada" cualquier código de salida distinto de 0; con MC08 la guardia F-2 del conftest aborta toda la sesión antes de ejecutar un solo test, de modo que ese "no tests ran" no prueba por sí solo la cobertura. Por eso se repitió con F-2 neutralizada (solo en una copia temporal, ya borrada).

## Registro de robustez (cuarta reanudación, 2026-11-11)
- **ANTES** (metadatos, sin abrir): `api/data/app.db` 4096 B, 2026-11-10T15:20:09; `api/data/app.db-wal` 24752 B, 2026-11-10T15:20:09; `app.db-shm` 32768 B, 2026-11-11T14:49:46 (lo toca el `python main.py` del usuario).
- **Suite completa** `cd api; python -m pytest -q`: **189 passed in 51.76s** (rc 0, ~53 s de pared). El "186" esperado estaba mal calculado: `collect-only` da `test_health` 1, `unit/test_config` 52, `unit/test_password_bytes` 37 (90 de OPS-001/API-001) + integración **99** = `test_register_password_bytes` 24, `test_login_password_bytes` 16, `test_seguridad_y_contrato` 12, `test_auth_regresion` 7, `test_config_startup` 40. Las cifras provisionales del Resumen (183, 93, 37 de `cfg`) estaban desfasadas; las tablas de mutaciones ya usaban 40.

- **`-W error`** (`python -m pytest -q -W error`, desde `api/`): **189 passed in 51.58s**, rc 0. El repo no tiene `pytest.ini`, `setup.cfg`, `pyproject.toml` ni `tox.ini`, y los `conftest` no declaran `filterwarnings`; no hay avisos de terceros que anotar.
- **Orden distinto** (plugin desechable `qa_shuffle.py` en `%TEMP%`, `-p qa_shuffle`): orden **inverso** 189 passed in 38.73s; orden aleatorio con semilla 12345 189 passed in 47.26s. Además, cada fichero de integración suelto (un comando por fichero): `test_seguridad_y_contrato` 12 passed, `test_register_password_bytes` 24, `test_login_password_bytes` 16, `test_config_startup` 40, `test_auth_regresion` 7; todos rc 0. Sin dependencias de orden ni de estado compartido.
- **Otro cwd** (raíz del repo, `python -m pytest api/tests -q`): **189 passed in 57.12s**, rc 0. BUG-005 **no afecta** (solo se manifiesta con `cwd = api/tests/unit` y ruta relativa; no se reprodujo para no arriesgar la lectura de `api/.env`).
- **DESPUÉS** (metadatos, sin abrir): `app.db` 4096 B 2026-11-10T15:20:09; `app.db-wal` 24752 B 2026-11-10T15:20:09; `app.db-shm` 32768 B 2026-11-11T14:49:46. **Idénticos al ANTES** (tamaño y fecha de los tres), `api/data/` sin ficheros nuevos.
- **Revisión de calidad** de `api/tests/integration/*.py` (búsquedas de texto; salida en `%TEMP%`):
  - *`api/.env` y `api/data/` reales:* ninguna lectura ni escritura. Las apariciones de `.env`, `data` y `app.db` son (a) el formato del `.env.example` replicado en cadenas, (b) rutas dentro de la **copia temporal** `granjas-qa-*/api` (que se crea con `ignore=(".env", ".env.*", "data", ...)` y con `assert not (copia / ".env").exists()` y `assert not (copia / "data").exists()`), (c) `monkeypatch.setattr(config, "DATA_DIR", directorio_temporal / "data")` y (d) un test que comprueba que el subproceso ejecutó el código de la copia (`base_dir == copia`). Las demás fixtures usan `tmp_path` y la BD temporal de `tests/conftest.py`.
  - *Puertos y red:* ningún `socket`, `uvicorn`, `urllib`, `requests` ni `http://` real. `localhost:4200`, `b:4200` y `evil.example` son solo valores de `Origin` en preflights CORS contra `TestClient` (ASGI en memoria) y valores de `CORS_ORIGINS`; `postgresql+psycopg://u:p@localhost/db` (ST-09) es una cadena que solo se resuelve como texto (sin conexión; el test pasa en esta máquina sin servidor PostgreSQL). Los puertos 8000 y 4200 no se usan (el `python main.py` del usuario siguió vivo: PID 3036 desde las 08:29 y su proceso hijo del reloader desde las 14:49).
  - *Esperas:* un único `time.sleep(0.2)` en `borrar_arbol` (`test_config_startup.py`, línea 98): reintento acotado (5 veces) del borrado en Windows (antivirus/WAL), no una espera arbitraria para sincronizar.
  - *`httpx`:* ningún `import httpx` ni `httpx2` en los tests; solo `fastapi.testclient.TestClient` (el fixture `client`, que usa la dependencia `httpx2` de `requirements.txt`).
  - *Secretos:* ninguno real. `SECRET_KEY` de prueba `clave-solo-para-tests-...` en `tests/conftest.py` (asignación directa, no `setdefault`); las contraseñas son literales de prueba; los tokens se obtienen de la API y los informes no los reproducen.
  - *Limpieza:* `entorno` (`granjas-qa-*`) borra con `borrar_arbol` en `finally`; las BD son por test en `tmp_path`; `pytest_sessionfinish` de `tests/conftest.py` hace `engine.dispose()` y borra `granjas-tests-*`. Tras las 6 ejecuciones de esta sesión no quedó ningún `granjas-tests-*` ni `granjas-qa-*` en `%TEMP%`.
  - *Subprocesos:* `subprocess.run` sin `shell=True`, con `timeout=180`, entorno filtrado (se quitan los campos de `Settings` y `PYTHONPATH` del shell) y `PYTHONDONTWRITEBYTECODE=1`.
  - *Limpieza de QA (paso 9):* borrados `%TEMP%\qa001-out`, `%TEMP%\qa001-final-v.txt` y `%TEMP%\pytest-of-*` (ningún `pytest` ni `mutar.py` en ejecución); no existían `qa-mut-*`, `granjas-tests-*` ni `granjas-qa-*`. Sin tocar `ops002-r2-*` ni los `qa-sim`, `qa_build*.txt`, `qa_diff.txt` y `qa_tab1.txt` de octubre (ajenos a esta épica). Solo quedan los procesos del usuario: `python main.py` (PID 3036) y su hijo del reloader.
  - *Árbol:* `git status` solo lista ficheros de la épica (`api/app/core/security.py`, `api/app/modules/auth/schemas.py`, `api/requirements.txt`, `tasks/base-tests-password.{json,md}`, `api/tests/**` y `reports/base-tests-password/**`); no hay ficheros ajenos ni prohibidos (`.env`, `*.db`, `data/`).

## Defectos
**Ninguno nuevo** (sin BUG-006). No hay S1, S2 ni S3 abiertos: BUG-001 (S3) se cerró en OPS-002 y su regresión está en `test_bug_001_url_no_parseable_no_rompe_settings_ni_filtra_la_clave` (3 casos, detectada por MC05). Abiertos y heredados, todos S4 y no bloqueantes (backlog preexistente):
- **BUG-002 (OPS-001, S4):** CO-08 de `unit/test_config.py` solo comprueba `endswith`, de modo que una mutación del mensaje de CORS que incluya el valor al principio sobrevive a ese unitario. QA-001 lo cubre en integración (`test_get_settings_el_error_de_cors_no_incluye_el_valor_en_el_mensaje`, detecta MC07 y MC14); el unitario sigue débil.
- **BUG-003 (OPS-001, S4):** `pytest --help` deja un directorio `granjas-tests-*` vacío en `%TEMP%` (`tests/conftest.py` crea el directorio al importar). No reproducido en esta sesión (solo se ejecutaron sesiones normales; no quedó ninguno).
- **BUG-004 (API-001, S4; devolver al Arquitecto):** un sustituto Unicode aislado (`"\ud800"`) en cualquier campo de texto da 500 por el handler 422 por defecto de FastAPI (`UnicodeEncodeError` al serializar `input`); preexistente, no específico de la contraseña y ligado a ADR-001. Ningún test de integración lo fija como esperado (cubierto solo en unitarios: `verify_password("\ud800", hash)` → `False`), de modo que corregirlo en ADR-001 no rompe QA-001.
- **BUG-005 (OPS-001, S4):** con `cwd = api/tests/unit` y ruta relativa el `conftest.py` de `tests/` no se carga (se saltan F-1 y F-2). No afecta a `python -m pytest` desde `api/` ni desde la raíz con `api/tests` (verificado en este informe).
- **OBS-8 (OPS-002, S4):** `OSError` de `Path.resolve()` con rutas SQLite relativas inválidas en Windows (`:` + dígito Unicode no ASCII); `resolve_database_url` no lo captura. Contrato silencioso; backlog.

## Cobertura y huecos
- **Linux/macOS:** no probado (solo Windows, Python 3.13.5, pytest 9.2.0). Las rutas POSIX solo se comprueban como cadenas y el `OSError` de OBS-8 es propio de Windows.
- **bcrypt 4.x:** no hay instalación real; solo bcrypt 5.0.0. Se simula con un `bcrypt` que trunca a 72 bytes (`test_l_04_no_se_acepta_un_prefijo_de_72_bytes[bcrypt-que-trunca]`), lo que demuestra la defensa en profundidad de `verify_password`, pero no la versión mínima declarada (`bcrypt>=4.2.0`).
- **Mínimos de `requirements.txt`:** `pytest>=8.0.0`, `httpx2>=2.0.0`, `fastapi>=0.115.0`, `pydantic>=2.8.0`, `pydantic-settings>=2.7.0` no se verificaron con sus versiones mínimas (instalado: pytest 9.2.0, httpx2 2.16.0, fastapi 0.142.2, starlette 1.7.0, pydantic 2.13.5, pydantic-settings 2.15.0, SQLAlchemy 2.1.2); QA no instala paquetes.
- **`pytest.exe` a secas:** solo se ejecutó `python -m pytest`; el contrato fija ese comando y la forma sin `-m` no añade el cwd a `sys.path`, por lo que no se probó.
- **`api/.env` real:** no se leyó ni se usó. La puerta del PM de §7.6.3 (arranque con el `api/.env` del usuario, `CORS_ORIGINS` en JSON) queda para el PM; QA solo simuló un `.env` equivalente en copia (ST-01, ST-02).
- **Servidor real, Web y SSR:** no se levantó `uvicorn` ni `ng serve`; los puertos 8000 y 4200 no se usaron. Integración Front↔API no aplica (la épica no toca `web/`).
- **Surrogates y concurrencia:** no se fijan como esperados (BUG-004); no hay pruebas de carga ni de concurrencia sobre `register`.
- **Hash en `api/data/*`:** no se calcula ni se abre (aislamiento acreditado con existencia, tamaño y fecha de modificación).
- Herramientas pedidas al PM: ninguna `OPS-*` nueva.

## Backlog consolidado de la épica (para el PM)
- **Defectos S4 abiertos:** BUG-002 (aserción CO-08, Developer), BUG-003 (`--help`, Developer), BUG-004 (sustituto Unicode, Arquitecto + ADR-001), BUG-005 (`rootdir` / `pytest.ini`, una futura tarea `OPS` que escale el contrato §4.2), OBS-8 (`OSError` de `resolve()`, decidir captura). BUG-001 (S3) está cerrado.
- **Para el Arquitecto, en `contracts/base-tests-password.md`:** redacción de §7.5 y §8 (BUG-004: eliminar «en `login` debe dar 401, nunca 500» para los sustitutos aislados y registrar la entrada en ADR-001); DB-1 (citar también `ValueError`), DB-3 (describir la sustitución textual, no `render_as_string`, que da `C%3A` con SQLAlchemy 2.1.2) y FX-C (precisar «salvo la creación del directorio padre de una ruta SQLite absoluta»); en §8 añadir `contracts/auth.md` a los documentos a actualizar.
- **Para cerrar la épica (PM/Arquitecto):** la cabecera de `contracts/auth.md` (línea 2 «rev. ADR-004 pendiente de `API-001`» y línea 6 «hasta entonces el código aplica `max_length=72` … y `register` devuelve 500») quedará obsoleta al dar `API-001` por `done`; actualizar `AGENTS.md` y `qa.agent.md` (hueco conocido `max_length=72`/ADR-004 y «sin tests ni `pytest` en la API»); la puerta del PM de §7.6.3 con el `api/.env` real.
- **Seguridad y calidad preexistentes (backlog):** `echo=settings.debug` en `database.py` deja el hash bcrypt del `INSERT` en el log SQL con `DEBUG=true` (la contraseña en claro nunca aparece); refresh tokens sin rotación ni revocación (ADR-003); el 422 devuelve `input` con la contraseña rechazada y amplifica la respuesta con valores largos (ADR-001); `ValidationError` por `SECRET_KEY` ausente muestra el contenido de las variables (candidato `hide_input_in_errors=True`); `authenticate_user` no llama a `verify_password` si el usuario no existe (diferencia de tiempo); bcrypt 5.0.0 acepta `\u0000` sin 500.
- **Observaciones menores de OPS-002 (sin acción):** `%XX` en la ruta de instalación, `sqlite://host/…`, `CORS_ORIGINS` con comillas dentro del valor, `%20` en ruta relativa, `C:rel.db`.
- **Higiene:** las carpetas `ops002-r2-*` de `%TEMP%` (10/11) no son de QA y siguen ahí; las debe borrar el usuario o el Developer.

## Siguiente paso
1. **PM:** dar QA-001 por `done` y cerrar EP-01 (US-01, US-02 y US-03), con los cambios sin commit en el árbol. Mensaje de commit sugerido para el usuario: asunto `QA-001: Tests de integración del límite de contraseña en bytes y regresión de arranque`; cuerpo: épica EP-01 `base-tests-password`, historias US-01 a US-03, veredicto APROBADO, contrato `contracts/base-tests-password.md`, informe `reports/base-tests-password/qa-QA-001.md`. Ficheros: `api/tests/integration/{__init__,conftest,helpers,test_auth_regresion,test_config_startup,test_login_password_bytes,test_register_password_bytes,test_seguridad_y_contrato}.py` y los informes de `reports/base-tests-password/`. Nunca `.env`, `*.db`, `data/`, `node_modules/` ni `dist/`.
2. **PM:** ejecutar la puerta de §7.6.3 con el `api/.env` real, pasar al backlog los S4 y las observaciones anteriores y reflejar los estados en `tasks/base-tests-password.json`.
3. **Arquitecto (sin bloquear):** ajustar el contrato como se indica en el backlog.

## Veredicto de la épica EP-01
**APROBADO.** Sin S1, S2 ni S3 abiertos, suite completa (189 passed) y regresión en verde, contrato y OpenAPI coherentes y aislamiento acreditado.

| Historia | Veredicto | Evidencia |
|----------|-----------|-----------|
| **US-01** infraestructura de tests con BD temporal | CUMPLE | `pytest>=8.0.0` y `httpx2>=2.0.0` en `api/requirements.txt` (sin `httpx`); `api/tests/` con BD SQLite por test, `get_db` sobrescrito y `TestClient`; `test_health` en verde; 5 ejecuciones completas + audit hook (58 conexiones todas bajo `pytest-of-*`) y metadatos de `api/data/app.db` y `app.db-wal` idénticos antes y después; ningún test requiere `api/.env`: `tests/conftest.py` fija `DEBUG`, `SECRET_KEY` y `DATABASE_URL` por asignación directa antes de importar `app.*` y la guarda F-2 aborta la sesión si el engine global no apunta a la BD temporal (QA no leyó ni usó ese fichero). |
| **US-02** contraseña en bytes → 422 claro | CUMPLE | `ñ*40` (80 bytes) en `register` → 422 `password_too_long` (R-01 a R-13); 72 bytes → 201 y 73 → 422 (R-02, R-04, R-05, R-08, R-10); `login` con más de 72 bytes → 401, más de 72 caracteres → 422 y hash corrupto → 401, nunca 500 (L-01 a L-07); unitarios (37) e integración (24 + 16 + 12 + 7) con el límite exacto, 17 mutaciones de auth detectadas (16 por integración); ADR-004 aceptado. Salvedad documental: la cabecera de `contracts/auth.md` aún dice «pendiente de `API-001`» (cierre del PM/Arquitecto; el cuerpo del contrato sí está actualizado). |
| **US-03** arranque con la configuración documentada | CUMPLE | ST-01 y ST-02 (`.env` con el formato de `.env.example` y lista JSON, arranque completo de la app con preflight CORS), ST-07 y ST-08 (`DATABASE_URL` relativa respecto a `api/`, con cwd distinto, y creación del directorio), ST-04 a ST-06 y FX-B (un arranque fallido no crea `api/data/`), ST-10 y FX-C (con variables válidas nada cambia, `-W error::RuntimeWarning`); 14 mutaciones de configuración detectadas por integración. Falta solo la puerta del PM con el `api/.env` real (§7.6.3). |
