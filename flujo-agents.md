# Flujo de agentes · GrangesAndreu

Guía visual del circuito PM → Arquitecto → Developer → QA. Los diagramas usan Mermaid (para verlos en la vista previa de Markdown de VS Code hace falta soporte de Mermaid, p. ej. la extensión *Markdown Preview Mermaid Support*). Las reglas completas están en [AGENTS.md](AGENTS.md) y en `.github/agents/`.

## 1. Visión general

El PM es el centro del circuito: invoca a los demás como subagentes, recibe su bloque `## Resultado` y decide el siguiente paso. Es el único que usa git de escritura.

```mermaid
flowchart LR
    U([Usuario])
    subgraph CIRCUITO [Circuito de agentes]
        PM["PM<br/>planifica y orquesta"]
        ARQ["Arquitecto<br/>contrato y ADR"]
        DEV["Developer<br/>implementa"]
        QA["QA<br/>verifica"]
    end
    GIT[("Git · main")]

    U -->|petición| PM
    PM -->|tarea ARQ| ARQ
    ARQ -->|contrato + Resultado| PM
    PM -->|tarea API, WEB u OPS| DEV
    DEV -->|código sin commit + entrega| PM
    PM -->|tarea entregada| QA
    QA -->|veredicto + bugs| PM
    PM -->|commit y push solo si APROBADO| GIT
    PM -.->|pregunta o aviso| U
```

Modo manual (sin orquestar): los *handoffs* de cada agente permiten pasar el trabajo a mano.

```mermaid
flowchart LR
    PM["PM"]
    ARQ["Arquitecto"]
    DEV["Developer"]
    QA["QA"]
    PM -.-> ARQ
    ARQ -.-> DEV
    ARQ -.-> PM
    DEV -.-> QA
    DEV -.-> ARQ
    QA -.-> DEV
    QA -.-> PM
    QA -.-> ARQ
```

## 2. Secuencia de una petición completa

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant PM
    participant ARQ as Arquitecto
    participant DEV as Developer
    participant QA
    participant G as Git

    U->>PM: Petición
    PM->>PM: Precondición: api/ y web/ sin cambios ajenos
    PM->>PM: Plan en tasks/slug.json y .md
    PM->>ARQ: Tarea ARQ-001
    ARQ-->>PM: Contrato + ADR + Resultado
    alt Decisión de negocio o ADR pendiente
        PM-->>U: Pregunta y se detiene
    else Contrato aprobable
        PM->>PM: Estado aprobado y replanifica
        PM->>G: Commit ARQ-001 (plan, contrato, ADR) y push
    end
    loop Cada tarea OPS, API o WEB
        PM->>DEV: Implementa la tarea (con informe de QA si es reintento)
        DEV-->>PM: Código sin commit + entrega-ID.md + Resultado
        PM->>QA: Verifica la tarea
        QA-->>PM: qa-ID.md + veredicto + bugs
        alt APROBADO
            PM->>PM: Puertas del PM
            PM->>G: Commit ID: título y push
        else RECHAZADO
            PM->>PM: Rollback de api/ y web/
            Note over PM,DEV: Reintento con el informe de QA (máximo 3 intentos)
        end
    end
    PM->>QA: Tareas QA de integración
    PM-->>U: Resumen y commits de la épica
```

## 3. Bucle de una tarea (aprobación, rollback y paradas)

```mermaid
flowchart TD
    A([Tarea desbloqueada]) --> B{"api/ y web/ sin cambios ajenos?"}
    B -->|no| S1([Parar y avisar al usuario])
    B -->|sí| C["status: in_progress"]
    C --> D["Developer implementa<br/>lee qa-ID.md si es reintento"]
    D --> E{"Resultado del Developer"}
    E -->|bloqueado o pregunta| S2([Parar y preguntar])
    E -->|ok| F["status: in_qa"]
    F --> G["QA verifica y escribe qa-ID.md"]
    G --> H{"Veredicto"}

    H -->|APROBADO| I{"Puertas del PM en verde?"}
    I -->|no| S3([Parar y avisar])
    I -->|sí| J["status: done"]
    J --> K["git commit ID: título"]
    K --> L["git push origin HEAD"]
    L --> M{"Push aceptado?"}
    M -->|no| S4([Parar sin forzar])
    M -->|sí| N([Siguiente tarea])

    H -->|RECHAZADO| R["Rollback: git restore y git clean<br/>solo en api/ y web/"]
    R --> T["status: rejected<br/>attempts + 1"]
    T --> V{"attempts menor que 3?"}
    V -->|sí| C
    V -->|no| W["status: blocked"]
    W --> S5([Parar y avisar<br/>repo en el último commit bueno])

    classDef stop fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
    classDef ok fill:#e2f5e6,stroke:#2e8b57,color:#14532d
    class S1,S2,S3,S4,S5 stop
    class N,J,K,L ok
```

## 4. Estados de una tarea

```mermaid
stateDiagram-v2
    [*] --> todo
    todo --> in_progress: Developer invocado
    todo --> blocked: dependencia bloqueada
    in_progress --> in_qa: entrega lista
    in_progress --> blocked: bloqueo o pregunta
    in_qa --> done: QA APROBADO, commit y push
    in_qa --> rejected: QA RECHAZADO, rollback
    rejected --> in_progress: reintento
    rejected --> blocked: 3 intentos agotados
    blocked --> in_progress: desbloqueada
    done --> [*]
```

## 5. Qué pasa con el código

Nada entra en el historial sin aprobar. El código vive sin commit hasta que QA lo aprueba.

```mermaid
flowchart LR
    W["Código sin commit<br/>árbol de trabajo"]
    W -->|QA APROBADO y puertas OK| C["Commit y push<br/>historial limpio"]
    W -->|QA RECHAZADO| X["Rollback<br/>git restore y git clean"]
    C -->|fallo en integración| V["git revert y push<br/>sin reescribir historial"]
    X -->|reintento| W
    V -->|reintento| W
```

Prohibido para todos los agentes: `push --force`, `--no-verify`, `--amend`, `rebase`, `reset --hard`, `clean -x`. Developer y QA no usan git de escritura.

## 6. Comportamiento interno de cada agente

### PM
```mermaid
flowchart LR
    A["Leer README, AGENTS y código"] --> B["Plan: épica, historias y tareas<br/>tasks/slug.json y .md"]
    B --> C{"Solo planificar?"}
    C -->|sí| D([Entrega el plan y para])
    C -->|no| E["Orquestar el circuito<br/>subagentes y git"]
    E --> F["Actualizar estados<br/>en tasks/slug.json"]
    F --> G([Resumen final al usuario])
```

### Arquitecto
```mermaid
flowchart LR
    A["Leer tarea ARQ y código"] --> B["Modelar datos"]
    B --> C["Diseñar API"]
    C --> D["Diseñar Front<br/>incluye RenderMode"]
    D --> E["Escribir contracts/slug.md y ADR"]
    E --> F{"Checklist"}
    F -->|incompleto| E
    F -->|falta decisión de negocio| Q(["estado: pregunta<br/>contrato en draft"])
    F -->|cumple| R(["estado: ok<br/>listo para aprobar"])
```

### Developer
```mermaid
flowchart LR
    A["Validar entrada<br/>contrato aprobado y tarea desbloqueada"] -->|falta o es ambiguo| X([Escalar a Arquitecto o PM])
    A --> B{"Es reintento?"}
    B -->|sí| C["Leer qa-ID.md<br/>partir del repo limpio"]
    B -->|no| D
    C --> D["Implementar por capas"]
    D --> E["Tests unitarios"]
    E --> F["Verificar: arranque, build y tests"]
    F --> G["Escribir entrega-ID.md"]
    G --> H(["estado: ok<br/>código sin commit"])
```

### QA
```mermaid
flowchart LR
    A["Leer tarea, contrato §7 y entrega"] --> B["Plan y trazabilidad"]
    B --> C["Smoke: API arranca, build y tests"]
    C --> D["API, contrato, Web,<br/>integración, SSR y seguridad"]
    D --> E["Regresión"]
    E --> F["Escribir qa-ID.md"]
    F --> G{"BUG S1, S2 o S3 abiertos?"}
    G -->|no| H(["APROBADO"])
    G -->|sí| I(["RECHAZADO + BUG-xxx"])
```

## 7. Ficha de cada agente

| | PM | Arquitecto | Developer | QA |
|---|---|---|---|---|
| **Misión** | Planifica, orquesta y cierra en git | Diseña el contrato antes de codificar | Implementa la tarea | Verifica con evidencia |
| **Entrada** | Petición del usuario | Tarea `ARQ-*` | Tarea `API/WEB/OPS-*` + contrato aprobado (+ `qa-ID.md` si reintento) | Entrega del Developer |
| **Salida** | `tasks/`, commits y push | `contracts/<slug>.md`, `contracts/adr/` | Código, tests unitarios, `entrega-ID.md` | `qa-ID.md`, `BUG-NNN`, veredicto |
| **Herramientas** | read, search, edit, execute, todo, agent | read, search, edit, todo | read, search, edit, execute, todo | read, search, edit, execute, todo |
| **Git** | Escribe (commit, push, rollback, revert) | No | Solo lectura | Solo lectura |
| **Edita `tasks/*.json`** | Sí (único) | No | No | No |
| **No hace** | Código de producción ni contratos | Implementar ni planificar | Rediseñar contratos ni cambiar alcance | Corregir código ni instalar herramientas |

## 8. Ficheros que genera el circuito

```mermaid
flowchart LR
    PM -->|escribe| T["tasks/slug.json<br/>tasks/slug.md"]
    ARQ[Arquitecto] -->|escribe| CT["contracts/slug.md<br/>contracts/adr/"]
    DEV[Developer] -->|escribe| CODE["api/ y web/<br/>tests unitarios"]
    DEV -->|escribe| EN["reports/slug/entrega-ID.md"]
    QA -->|escribe| QR["reports/slug/qa-ID.md"]
    QA -->|escribe| QT["tests de integración y e2e"]
    CT -->|lee| DEV
    CT -->|lee| QA
    EN -->|lee| QA
    QR -->|lee en reintentos| DEV
    QR -->|lee| PM
```

## 9. Cuándo se detiene el PM

| Situación | Qué hace el PM |
|-----------|----------------|
| Un agente devuelve `estado: pregunta` | Te pregunta y espera |
| Contrato con decisión de negocio o ADR pendiente | Te pregunta; el contrato sigue en `draft` |
| `api/` o `web/` con cambios ajenos | Para antes de empezar la tarea |
| 3 intentos fallidos de una tarea | Marca `blocked`, deja el repo en el último commit bueno y avisa |
| Puerta del PM en rojo o fichero prohibido en el diff | Para y avisa |
| `git push` rechazado | Para y avisa; no fuerza ni resuelve conflictos |

## 10. Cómo usarlo

1. Elige el agente **PM** en el selector de chat.
2. Describe lo que quieres. Añade "solo planifica" si no quieres que ejecute el circuito.
3. Antes del primer uso, deja `api/` y `web/` sin cambios pendientes en git.
4. Revisa los commits de la épica con `git log --oneline` cuando termine.
