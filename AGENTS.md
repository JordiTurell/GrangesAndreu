# AGENTS

Reglas y contexto comunes a todos los agentes de GrangesAndreu. El rol de cada agente está en `.github/agents/*.agent.md`; aquí no se asigna ningún rol.

## Idioma y reglas comunes
- Español por defecto (código, identificadores y mensajes de commit según el estilo existente), salvo que el usuario pida otro idioma.
- Leer `README.md` y el código real antes de actuar; basar las decisiones en el repo, no en suposiciones.
- Control de versiones: **solo el Developer escribe en git** (commit de cada tarea aprobada y `git restore` de una tarea rechazada 3 veces) y nunca sube nada (ver "Política Git"). El resto de agentes solo usa git de lectura. No tocar `.env`, secretos ni `api/data/`.
- Acciones destructivas (borrar datos, reset de BD) solo con confirmación del usuario. La única reversión permitida es el `git restore` de los ficheros de una tarea tras 3 KO.
- No inventar requisitos: preguntar o registrar el supuesto.

## Circuito de trabajo

```
Usuario → PM (analiza) → Arquitecto (contrato corto + tareas pequeñas) → PM
Por cada tarea:  PM → Developer → PM → QA → PM
   OK  (APROBADO)  → PM ordena al Developer el commit → tarea done
   KO  (RECHAZADO) → PM reenvía al Developer (máx. 3 intentos)
   3.º KO          → QA ordena el rollback → PM → Developer: git restore de esa tarea
```

El PM es el centro: los demás le responden con el bloque `## Resultado` y él decide el siguiente paso. Diagramas en `flujo-agents.md`.

| Fase | Agente | Entrada | Salida |
|------|--------|---------|--------|
| Analizar | PM | Petición + repo | `tasks/<slug>.json` con épica, historias y `analysis` (≤ 1 página) |
| Diseñar y trocear | Arquitecto | `analysis` del PM | `contracts/<slug>.md` corto, ADR si procede y las **tareas pequeñas** en `tasks/<slug>.json` |
| Implementar | Developer | Bloque de la tarea | Código, tests unitarios, `reports/<slug>/entrega-<ID>.md` |
| Verificar | QA | Tarea + entrega | `reports/<slug>/qa-<ID>.md` con `APROBADO` (OK) o `RECHAZADO` (KO) |
| Commit | Developer (orden del PM) | Tarea `APROBADA` | Commit local de los ficheros de la tarea |
| Deshacer | Developer (orden de QA vía PM) | 3.º KO | `git restore` solo de los ficheros de la tarea |
| Cerrar | PM | Commit hecho | Tarea `done` y resumen al usuario |

`<slug>` es siempre `epic.slug` definido por el PM; el resto de agentes lo reutilizan.

### Propiedad de artefactos
- **`tasks/<slug>.json`**: el PM crea el esqueleto (épica, historias, `analysis`) y es el único que cambia `status`, `attempts` y `bugs`. El Arquitecto añade las tareas al trocear. No existe `tasks/<slug>.md`: el tablero se muestra en el chat.
- **Contrato** (`contracts/<slug>.md`): lo escribe el Arquitecto; solo contiene lo que comparten varias tareas. Pasa a `aprobado` cuando cumple su checklist y el PM (o el usuario) lo confirma.
- **Tareas**: pequeñas y autocontenidas (ver "Tarea pequeña"). El Developer y QA trabajan con el bloque de la tarea, sin leer el JSON entero.
- **Tests**: el Developer escribe los unitarios de lo que implementa; QA escribe los de integración, contrato, e2e y regresión. Instalar herramientas de test o lint es una tarea `OPS-*`.
- **Defectos**: QA los reporta; el PM los reenvía al Developer. Si el contrato es incorrecto van al Arquitecto; si falta un requisito, al PM.

### Tarea pequeña (la define el Arquitecto)
Una capa, un objetivo, ≤ 3 ficheros de producción más sus tests, tamaño `S`, ≤ 5 criterios de aceptación comprobables. Campos: `id`, `story`, `layer`, `title`, `spec` (qué construir: rutas, campos, errores, reglas; lo que el Developer necesita sin abrir el contrato), `files` (producción y tests), `acceptance`, `contract_refs` (solo si `spec` remite al contrato), `depends_on`, `status`, `attempts`. Si no cabe, se divide.

### Política de eficiencia (aplica a todos los agentes)
Objetivo: poco contexto y pocas ejecuciones repetidas.
- **Contexto mínimo**: el PM pasa a cada subagente el bloque de la tarea pegado en el prompt (id, `spec`, `files`, `acceptance`) y, en reintentos, solo las líneas `BUG` del informe de QA. Nadie lee `tasks/<slug>.json` entero, ni el contrato completo (solo las `contract_refs` si la tarea las cita), ni `README.md` ni los `.agent.md` de otros roles.
- **Alcance**: Developer y QA leen y tocan solo los `files` de la tarea y lo que importan de forma directa.
- **Verificación escalonada** (una ejecución por nivel y por intento):
  1. *Developer*: solo los tests de la tarea (`pytest <ficheros>`; `npm test -- --no-watch` y `npm run build` solo si cambió `web/`) más el import/arranque. Nunca la suite completa salvo código transversal (`core/`, `shared/`, `main.py`, `app.config.ts`).
  2. *QA por tarea*: revisa el diff de los `files`, ejecuta una vez los tests de la tarea y los del módulo afectado y un smoke. No repite pruebas ni comprobaciones que no cubren los `acceptance`.
  3. *Regresión completa*: solo en tareas `QA-*` y al cerrar la épica.
- **Informes breves**: `entrega-<ID>.md` ≤ 25 líneas y `qa-<ID>.md` ≤ 1 página; una línea por criterio con ✔/✘ y evidencia. Sin repetir el contrato ni pegar salidas completas.
- **Entorno una vez por circuito**: el preflight (Python, Node, `nvm use`, `npm ci`, `requirements.txt`) lo hace el PM al empezar; los subagentes no lo repiten salvo fallo.
- **Subagentes sin sobrecarga**: no arrancar API/Web si no hace falta; en tests usar `TestClient` y BD temporal; parar los procesos al terminar.

### Estados de tarea
`todo` → `in_progress` → `in_qa` → `done`. Con KO: `rejected` → `in_progress` (reintento). Tras el 3.º KO y el rollback: `reverted`. Cualquier estado puede pasar a `blocked` indicando el motivo.

## Automatización y política Git

### Circuito automático
Cuando el usuario pide construir o cambiar algo, el PM ejecuta el circuito completo invocando a Arquitecto, Developer y QA como subagentes y solo se detiene en las "Paradas". Si el usuario pide solo planificar, se detiene tras el plan del Arquitecto. El detalle del bucle está en `.github/agents/pm.agent.md`.

### Resultado de cada agente
Cada agente termina su respuesta con este bloque, que el PM lee para decidir el siguiente paso:

```
## Resultado
agente: Arquitecto | Developer | QA
tarea: <ID>
estado: ok | bloqueado | pregunta
veredicto: APROBADO | RECHAZADO          # solo QA
orden: ninguna | rollback                # solo QA; rollback solo en el 3.º RECHAZADO
artefactos: <rutas>
bugs: <BUG-001 (S2), ...>                # solo QA
commit: <hash corto> | restore           # solo Developer, al commitear o deshacer
adr_pendientes: <ADR-xxx>                # solo Arquitecto
preguntas: <decisiones de negocio o datos que faltan>   # solo si estado = pregunta
detalle: <1-3 líneas>
```

### Política Git
- **Solo el Developer escribe en git**, y únicamente por orden del PM:
  - *Commit* de una tarea `APROBADA`: `git add -- <files de la tarea> reports/<slug>/entrega-<ID>.md reports/<slug>/qa-<ID>.md` y `git commit` con asunto `<ID>: <título de la tarea>` y cuerpo con épica, historia y veredicto. También un commit de plan al aprobar el contrato (`tasks/<slug>.json`, `contracts/`) y otro de cierre de épica con el estado final del JSON.
  - *Rollback* tras el 3.º KO, solo si QA lo ordena (`orden: rollback`): `git restore --staged --worktree -- <ficheros de la tarea ya rastreados>` y borrar los ficheros nuevos de la tarea (los de `files` que sigan sin rastrear). Nunca `git clean`, ni `restore` sin lista de ficheros, ni de ficheros que no sean de la tarea.
- **Prohibido para todos**: `push`, `pull`, `fetch`, `merge`, `rebase`, `reset`, `clean`, `checkout`, `switch`, `stash`, `revert`, `cherry-pick`, `tag`, `commit --amend` y crear o borrar ramas. Las subidas las hace el usuario.
- **Solo lectura** para PM, Arquitecto y QA: `git status`, `diff`, `log`, `show`, `rev-parse`, `branch --show-current`, `remote -v` y `config --get`.
- **Precondición**: antes de cada tarea, `git status --porcelain -uall -- api web` debe estar vacío (cada tarea aprobada queda commiteada). Cualquier cambio es ajeno: parar y avisar; no se toca trabajo ajeno. En un reintento solo pueden aparecer los `files` de esa tarea.
- **Alcance de la entrega**: al volver el Developer, el PM comprueba con `git status --porcelain -uall` que solo han cambiado los `files` de la tarea y `reports/<slug>/`. Si no: parar por fichero fuera de alcance.
- **Reintentos**: un KO pasa por el PM (`rejected`, `attempts + 1`) y el Developer corrige sobre el árbol, solo los `files` de la tarea. Máximo 3 intentos. En el 3.º KO, QA escribe `orden: rollback`; el PM ordena el rollback al Developer, la tarea queda `reverted` y el PM avisa al usuario. Una integración fallida (`QA-*`) devuelve la tarea culpable a `in_progress`.
- **Nunca se commitean** `.env`, `*.db`, `data/`, `node_modules/`, `dist/` ni `.angular/`.

### Paradas (el PM avisa o pregunta y se detiene)
- Un agente devuelve `estado: pregunta`, o el contrato deja decisiones de negocio o ADR pendientes.
- `api/` o `web/` con cambios ajenos antes de empezar una tarea.
- Tarea `reverted` tras 3 KO, fichero fuera de alcance o prohibido en el árbol, o fallo de un commit o rollback.

## Repo (estado verificado el 2026-11-10; revisar el código si ha pasado tiempo)

### Estructura y stack
- **API** (`api/`): FastAPI, SQLAlchemy 2, Pydantic 2, PyJWT y bcrypt. SQLite en `api/data/app.db` (ignorado por git) o `DATABASE_URL`. Prefijo `/api`; `/docs`, `/openapi.json` y `/health`.
- Módulos de la API en `api/app/modules/<modulo>/` con `entities.py`, `schemas.py`, `services.py`, `controllers.py` y `routes.py`; transversales en `api/app/core/` y `api/app/shared/`.
- **Web** (`web/`): Angular 22 con SSR e hidratación, Tailwind 4, Vitest y Prettier (`printWidth` 100, comillas simples; `.editorconfig` de 2 espacios). Módulos en `web/src/app/modules/<modulo>/<pantalla>/<pantalla>.component.{ts,html,css}`.
- TypeScript sin `strict`, pero con `noImplicitReturns`, `noImplicitOverride` y `noPropertyAccessFromIndexSignature`.

### Cómo ejecutar
- API: `cd api` y `python main.py` (`127.0.0.1:8000`; `bootstrap.py` instala con pip lo que falte de `requirements.txt`). Configuración en `api/.env` a partir de `api/.env.example`; `SECRET_KEY` obligatoria salvo `DEBUG=true`.
- Web (en `web/`): `npm start` (puerto 4200), `npm run build`, `npm test -- --no-watch`, `npm run serve:ssr:web` (tras `build`).
- CORS: `CORS_ORIGINS`, por defecto `http://localhost:4200`.
- Sin `api/.env`, arrancar la API con variables de entorno de la sesión (`DEBUG=true` y, en pruebas, `DATABASE_URL` a una BD temporal); no crear ni editar `.env`.
- `settings` y `engine` se crean al importar `main` y el lifespan llama a `init_db()` sobre el engine global: en pruebas hay que fijar `DEBUG` y `DATABASE_URL` en el entorno **antes** de importar; sobrescribir `get_db` no basta. Importar `main` también ejecuta `bootstrap.ensure_dependencies()` (pip, necesita red): instalar antes `requirements.txt`.

### Requisitos del entorno (verificado el 2026-11-10 en esta máquina)
- Python 3.13 con las dependencias de `requirements.txt` instaladas (incluidos `pytest` y `httpx2`; `TestClient` de starlette 1.7.0 exige `httpx2`, no `httpx`). Los tests se ejecutan con `cd api` y `python -m pytest` (`pytest.exe` no está en el PATH).
- Angular 22.2 exige Node `^22.22.3 || ^24.15.0 || >=26` (`@angular/build`). La terminal arranca con Node 20.11.1 y NVM Portable solo cambia la versión de la terminal actual: antes de cualquier comando `npm`, ejecutar `nvm use 26.0.0` en esa terminal. Verificado con Node 26.0.0: `npm ci`, `npm run build` y `npm test -- --no-watch` pasan.
- Git con identidad configurada; los agentes solo lo leen (no hacen commits ni subidas).

### Estado actual y huecos conocidos
- `auth` implementado (`POST /api/auth/register|login|refresh`, `GET /api/auth/me`); su contrato está en `contracts/auth.md`.
- `pollos` está vacío y sin registrar en `api/main.py`. No hay más módulos de dominio.
- Sin migraciones: `create_all` no altera tablas existentes y no hay Alembic.
- API con tests (`api/tests/`: fixtures de BD temporal en `conftest.py`, `unit/` del Developer e `integration/` de QA; 189 tests en verde el 2026-11-11). Un único test en la Web (`app.spec.ts`, que espera el título placeholder `Hello, web`). Sin linter en ninguna capa.
- El Front no tiene `provideHttpClient`, interceptors, servicios, modelos ni URL base de la API; `app.routes.ts` está vacío; el login simula la llamada y navega a `/dashboard`, que no existe.
- `app.routes.server.ts` prerenderiza todas las rutas (`**`).
- Los errores de dominio usan `{"error": {"code", "message"}}`, pero los 422 de validación usan el formato por defecto de FastAPI (`detail`).
- Los refresh tokens son *stateless*: no se rotan ni se revocan.
- El límite de contraseña de `register` se cuenta en bytes UTF-8 (72, ADR-004) y devuelve 422 `password_too_long`; `login` sigue acotando en caracteres y responde 401 con más de 72 bytes. Un sustituto Unicode aislado (`"\ud800"`) en el JSON da 500 en el handler 422 de FastAPI (BUG-004, backlog de ADR-001).

