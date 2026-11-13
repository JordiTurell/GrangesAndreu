# Flujo de agentes · GrangesAndreu

Guía visual del circuito PM → Arquitecto → Developer → QA. Los diagramas usan Mermaid (para verlos en la vista previa de VS Code hace falta soporte de Mermaid). Las reglas completas están en [AGENTS.md](AGENTS.md) y en `.github/agents/`.

## 1. Visión general

El PM es el centro: analiza una vez, pasa el análisis al Arquitecto (que crea el contrato corto y las **tareas pequeñas**) y luego orquesta cada tarea con Developer y QA. Todo pasa por el PM. Solo el **Developer** escribe en git (commit de lo aprobado y rollback de lo rechazado 3 veces); nunca sube nada.

```mermaid
flowchart LR
    U([Usuario])
    PM["PM<br/>analiza y orquesta"]
    ARQ["Arquitecto<br/>contrato corto + tareas pequeñas"]
    DEV["Developer<br/>implementa, commitea, deshace"]
    QA["QA<br/>OK / KO"]
    GIT[("Git local<br/>push lo haces tú")]

    U -->|petición| PM
    PM -->|analysis| ARQ
    ARQ -->|contrato + tareas| PM
    PM -->|bloque de la tarea| DEV
    DEV -->|entrega| PM
    PM -->|bloque de la tarea| QA
    QA -->|OK / KO| PM
    PM -->|orden de commit o rollback| DEV
    DEV -->|commit / restore| GIT
    PM -->|resumen| U
```

## 2. Secuencia de una petición

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant PM
    participant ARQ as Arquitecto
    participant DEV as Developer
    participant QA
    participant G as Git local

    U->>PM: Petición
    PM->>PM: Preflight + análisis de repo y petición
    PM->>ARQ: analysis (tasks/slug.json)
    ARQ-->>PM: Contrato corto + tareas pequeñas + Resultado
    alt Decisión de negocio o ADR pendiente
        PM-->>U: Pregunta y se detiene
    else Contrato aprobable
        PM->>DEV: Commit de plan (tasks y contracts)
        DEV->>G: commit
    end
    loop Cada tarea, en orden de dependencias
        PM->>DEV: Bloque de la tarea
        DEV-->>PM: Código + entrega + Resultado
        PM->>QA: Bloque de la tarea
        QA-->>PM: Informe + OK o KO
        alt OK
            PM->>DEV: Orden de commit
            DEV->>G: commit de la tarea
            PM->>PM: tarea done (hash)
        else KO con menos de 3 intentos
            PM->>DEV: Líneas BUG (reintento)
        else 3.º KO
            QA-->>PM: orden rollback
            PM->>DEV: Orden de rollback
            DEV->>G: git restore de esa tarea
            PM->>PM: tarea reverted
        end
    end
    PM-->>U: Resumen (done, reverted, bugs) y push a tu cargo
```

## 3. Bucle de una tarea

```mermaid
flowchart TD
    A([Tarea desbloqueada]) --> B{"api/ y web/ limpios?"}
    B -->|no| S1([Parar y avisar])
    B -->|sí| C["in_progress<br/>Developer implementa"]
    C --> E{"Resultado Developer"}
    E -->|bloqueado o pregunta| S2([Parar y preguntar])
    E -->|ok| F["in_qa<br/>QA verifica la tarea"]
    F --> H{"Veredicto"}

    H -->|"OK (APROBADO)"| I["Developer commitea<br/>tarea done"]
    I --> N([Siguiente tarea])

    H -->|"KO (RECHAZADO)"| T["rejected, attempts + 1"]
    T --> V{"attempts menor que 3?"}
    V -->|sí| C
    V -->|no| W["QA: orden rollback<br/>Developer: git restore de la tarea"]
    W --> X["reverted"]
    X --> S5([Avisar al usuario])

    classDef stop fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
    classDef ok fill:#e2f5e6,stroke:#2e8b57,color:#14532d
    class S1,S2,S5 stop
    class N,I ok
```

## 4. Estados de una tarea

```mermaid
stateDiagram-v2
    [*] --> todo
    todo --> in_progress: Developer invocado
    todo --> blocked: dependencia bloqueada
    in_progress --> in_qa: entrega lista
    in_progress --> blocked: bloqueo o pregunta
    in_qa --> done: QA OK y commit hecho
    in_qa --> rejected: QA KO
    rejected --> in_progress: reintento (máx. 3 intentos)
    rejected --> reverted: 3.º KO y rollback
    blocked --> in_progress: desbloqueada
    done --> [*]
    reverted --> [*]
```

## 5. Quién toca git

| Agente | Git |
|---|---|
| PM, Arquitecto, QA | Solo lectura (`status`, `diff`, `log`, `show`, `rev-parse`…) |
| Developer | Solo por orden del PM: `add`/`commit` de los ficheros de la tarea y `restore` de esos ficheros tras `orden: rollback` de QA |
| Todos | Nunca `push`, `pull`, `fetch`, `reset`, `clean`, `checkout`, `stash`, `revert`, `rebase`, `merge`, `--amend` ni ramas |

Como cada tarea aprobada queda commiteada, el árbol de `api/` y `web/` está limpio entre tareas y el `git restore` solo afecta a la tarea que falla.

## 6. Qué hace cada agente

| | PM | Arquitecto | Developer | QA |
|---|---|---|---|---|
| **Misión** | Analiza y orquesta | Contrato corto y tareas pequeñas | Implementa, commitea, deshace | OK o KO por tarea |
| **Entrada** | Petición | `analysis` del PM | Bloque de la tarea | Bloque de la tarea + entrega |
| **Salida** | `tasks/<slug>.json` (estado) | `contracts/<slug>.md`, ADR, `tasks` | Código, tests, `entrega-<ID>.md` | `qa-<ID>.md`, `BUG-NNN`, `orden` |
| **Edita `tasks/*.json`** | Estado (`status`, `attempts`, `bugs`, `commit`) y esqueleto | Solo añade `tasks` | No | No |
| **Git** | Lectura | Lectura | Commit y restore por orden | Lectura |

## 7. Ahorro de contexto

- Cada subagente recibe en el prompt **el bloque de su tarea** (id, `spec`, `files`, `acceptance`); no lee el JSON entero ni el contrato completo.
- Tareas pequeñas: ≤ 3 ficheros de producción, un objetivo, ≤ 5 criterios.
- Contrato corto (~15 KB) con lo compartido; los criterios viven en cada tarea.
- Developer y QA ejecutan solo los tests de la tarea; la regresión completa solo en `QA-*` y al cerrar la épica.
- Informes cortos: entrega ≤ 25 líneas, QA ≤ 1 página.

## 8. Cuándo se detiene el PM

| Situación | Qué hace el PM |
|-----------|----------------|
| Un agente devuelve `estado: pregunta` | Te pregunta y espera |
| Contrato con decisión de negocio o ADR pendiente | Te pregunta; el contrato sigue en `draft` |
| `api/` o `web/` con cambios ajenos | Para antes de empezar la tarea |
| 3 KO de una tarea | QA ordena el rollback, el Developer la deshace, la tarea queda `reverted` y avisa |
| Fichero fuera de alcance, o fallo de un commit o rollback | Para y avisa |

## 9. Cómo usarlo

1. Elige el agente **PM** en el selector de chat.
2. Describe lo que quieres. Añade "solo planifica" si no quieres que ejecute el circuito.
3. Antes del primer uso, deja `api/` y `web/` sin cambios pendientes (el flujo exige árbol limpio para poder hacer commit y rollback por tarea).
4. Al terminar, revisa `git log` y haz tú el `push`.
