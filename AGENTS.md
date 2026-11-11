# AGENTS

Reglas y contexto comunes a todos los agentes de GrangesAndreu. El rol de cada agente está en `.github/agents/*.agent.md`; aquí no se asigna ningún rol.

## Idioma y reglas comunes
- Español por defecto (código, identificadores y mensajes de commit sugeridos según el estilo existente), salvo que el usuario pida otro idioma.
- Leer `README.md` y el código real antes de actuar; basar las decisiones en el repo, no en suposiciones.
- Control de versiones: **ningún agente (PM incluido) hace commits ni subidas a git**; los hace el usuario cuando quiera (ver "Política Git"). Los agentes solo usan git de lectura. No tocar `.env`, secretos ni `api/data/`.
- Acciones destructivas (borrar datos, reset de BD) solo con confirmación del usuario. Nadie descarta cambios del árbol de trabajo: no hay rollback con git.
- No inventar requisitos: preguntar o registrar el supuesto.

## Circuito de trabajo

```
PM ⇄ Arquitecto   diseño y contrato
PM ⇄ Developer    implementación
PM ⇄ QA           verificación
```

En el circuito automático los agentes no se pasan el trabajo entre sí: cada uno responde al PM, que decide el siguiente paso (otra tarea o reintento). Diagramas en `flujo-agents.md`.

| Fase | Agente | Entrada | Salida |
|------|--------|---------|--------|
| Planificar | PM | Petición del usuario | `tasks/<slug>.json` y `tasks/<slug>.md` |
| Diseñar | Arquitecto | Tarea `ARQ-*` | `contracts/<slug>.md` y `contracts/adr/ADR-NNN-*.md` |
| Implementar | Developer | Tarea `API-*`, `WEB-*` u `OPS-*` + contrato aprobado | Código, tests unitarios y `reports/<slug>/entrega-<ID>.md` |
| Verificar | QA | Entrega del Developer | `reports/<slug>/qa-<ID>.md` y defectos `BUG-NNN` |
| Cerrar | PM | Veredicto `APROBADO` | Tarea `done` en `tasks/<slug>.json`, cambios sin commit y mensaje de commit sugerido en el resumen para el usuario |

`<slug>` es siempre `epic.slug` definido por el PM; el resto de agentes lo reutilizan.

### Propiedad de artefactos
- **`tasks/*.json`**: solo lo edita el PM. Los demás agentes informan en sus documentos y el PM refleja el estado.
- **Contratos**: los escribe el Arquitecto. Pasa a `aprobado` cuando cumple su checklist y el PM (o el usuario) lo confirma; una tarea `ARQ` solo es `done` con el contrato `aprobado`.
- **Tests**: el Developer escribe los unitarios de lo que implementa; QA escribe integración, contrato, e2e y regresión. Instalar herramientas de test o lint es una tarea `OPS-*` creada por el PM y ejecutada por el Developer.
- **Defectos**: QA los reporta en su informe. En el circuito automático el PM los reenvía al Developer, que corrige sobre el árbol de trabajo (sin rollback); en modo manual van directos al Developer con copia al PM. Si el contrato es incorrecto van al Arquitecto; si falta un requisito, al PM.

### Estados de tarea
`todo` → `in_progress` → `in_qa` → `done`. Si QA rechaza: `rejected` → `in_progress` (el Developer corrige sobre el árbol de trabajo). Cualquier estado puede pasar a `blocked` indicando el motivo.

## Automatización y política Git

### Circuito automático
Cuando el usuario pide construir o cambiar algo, el PM ejecuta el circuito completo invocando a Arquitecto, Developer y QA como subagentes y solo se detiene en las "Paradas". Si el usuario pide solo planificar, el PM se detiene tras el plan. El detalle del bucle está en `.github/agents/pm.agent.md`.

### Resultado de cada agente
Cada agente termina su respuesta con este bloque, que el PM lee para decidir el siguiente paso:

```
## Resultado
agente: Arquitecto | Developer | QA
tarea: <ID>
estado: ok | bloqueado | pregunta
veredicto: APROBADO | RECHAZADO          # solo QA
artefactos: <rutas>
bugs: <BUG-001 (S2), ...>                # solo QA
adr_pendientes: <ADR-xxx>                # solo Arquitecto
preguntas: <decisiones de negocio o datos que faltan>   # solo si estado = pregunta
detalle: <1-3 líneas>
```

### Política Git (solo lectura para todos los agentes)
- **Sin commits ni subidas**: ningún agente ejecuta `git add`, `commit`, `push`, `pull`, `fetch`, `merge`, `rebase`, `reset`, `restore`, `clean`, `checkout`, `switch`, `stash`, `revert`, `cherry-pick`, `tag` ni crea o borra ramas. El usuario revisa y hace los commits y las subidas cuando quiera.
- **Comandos permitidos** (solo lectura): `git status`, `diff`, `log`, `show`, `rev-parse`, `branch --show-current`, `remote -v` y `config --get`.
- **Precondición**: antes de cada tarea, `git status --porcelain -uall -- api web` solo puede listar ficheros de tareas ya `done` (sus `files` en el JSON). Cualquier otro cambio es ajeno: parar y avisar; no se toca trabajo ajeno.
- **Instantánea por tarea**: el PM guarda la salida de `git status --porcelain -uall` antes de invocar al Developer y, al recibir la entrega, comprueba que solo han cambiado los `files` de la tarea y `reports/<slug>/` (con `git diff --stat` para los ficheros que ya estaban modificados). Si no: parar por fichero fuera de alcance.
- **Sin rollback**: una tarea rechazada pasa a `rejected` con `attempts + 1` y el Developer corrige sobre el árbol de trabajo, con el informe de QA como entrada y limitándose a los `files` de la tarea. Una integración fallida devuelve la tarea culpable a `in_progress`. Nadie borra ni descarta cambios.
- **Reintentos**: 2 tras un `RECHAZADO` (3 intentos en total). Agotados: tarea `blocked`, los cambios quedan en el árbol de trabajo para que el usuario decida y aviso.
- **Entrega al usuario**: al cerrar cada tarea `APROBADA` y al cerrar la épica, el PM lista en el resumen los ficheros de cada tarea y un mensaje de commit sugerido (asunto `<ID>: <título de la tarea>`; cuerpo con épica, historia, veredicto y rutas del contrato y del informe). El PM no lo ejecuta. Nunca se sugieren `.env`, `*.db`, `data/`, `node_modules/`, `dist/` ni `.angular/`.

### Paradas (el PM avisa o pregunta y se detiene)
- Un agente devuelve `estado: pregunta`, o el contrato deja decisiones de negocio o ADR pendientes.
- `api/` o `web/` con cambios ajenos antes de empezar una tarea.
- Reintentos agotados, puerta del PM en rojo sin causa clara, o fichero fuera de alcance o prohibido en el árbol de trabajo.

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
- Python 3.13 con las dependencias de `requirements.txt` instaladas (`pytest` y `httpx` no lo están).
- Angular 22.2 exige Node `^22.22.3 || ^24.15.0 || >=26` (`@angular/build`). La terminal arranca con Node 20.11.1 y NVM Portable solo cambia la versión de la terminal actual: antes de cualquier comando `npm`, ejecutar `nvm use 26.0.0` en esa terminal. Verificado con Node 26.0.0: `npm ci`, `npm run build` y `npm test -- --no-watch` pasan.
- Git con identidad configurada; los agentes solo lo leen (no hacen commits ni subidas).

### Estado actual y huecos conocidos
- `auth` implementado (`POST /api/auth/register|login|refresh`, `GET /api/auth/me`); su contrato está en `contracts/auth.md`.
- `pollos` está vacío y sin registrar en `api/main.py`. No hay más módulos de dominio.
- Sin migraciones: `create_all` no altera tablas existentes y no hay Alembic.
- Sin tests ni `pytest` en la API; un único test en la Web (`app.spec.ts`, que espera el título placeholder `Hello, web`). Sin linter en ninguna capa.
- El Front no tiene `provideHttpClient`, interceptors, servicios, modelos ni URL base de la API; `app.routes.ts` está vacío; el login simula la llamada y navega a `/dashboard`, que no existe.
- `app.routes.server.ts` prerenderiza todas las rutas (`**`).
- Los errores de dominio usan `{"error": {"code", "message"}}`, pero los 422 de validación usan el formato por defecto de FastAPI (`detail`).
- Los refresh tokens son *stateless*: no se rotan ni se revocan.
- El límite de contraseña (`max_length=72`) cuenta caracteres, mientras que bcrypt limita bytes.

