# Flujo de agentes · GrangesAndreu

Guía visual del circuito PM → Arquitecto → Developer → QA. Los diagramas usan Mermaid (para verlos en la vista previa de Markdown de VS Code hace falta soporte de Mermaid, p. ej. la extensión *Markdown Preview Mermaid Support*). Las reglas completas están en [AGENTS.md](AGENTS.md) y en `.github/agents/`.

## 1. Visión general

El PM es el centro del circuito: invoca a los demás como subagentes, recibe su bloque `## Resultado` y decide el siguiente paso. **Ningún agente hace commits ni subidas a git**: el código queda en el árbol de trabajo y los commits los haces tú con los mensajes que propone el PM.

```mermaid
flowchart LR
    U([Usuario])
    subgraph CIRCUITO [Circuito de agentes]
        PM["PM<br/>planifica y orquesta"]
        ARQ["Arquitecto<br/>contrato y ADR"]
        DEV["Developer<br/>implementa"]
        QA["QA<br/>verifica"]
    end
    GIT[("Git · main<br/>solo escribes tú")]

    U -->|petición| PM
    PM -->|tarea ARQ| ARQ
    ARQ -->|contrato + Resultado| PM
    PM -->|tarea API, WEB u OPS| DEV
    DEV -->|código sin commit + entrega| PM
    PM -->|tarea entregada| QA
    QA -->|veredicto + bugs| PM
    PM -->|si APROBADO: tarea done y commit sugerido| U
    U -->|revisas, commiteas y subes| GIT
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
    participant G as Git (solo tú)

    U->>PM: Petición
    PM->>PM: Precondición: api/ y web/ sin cambios ajenos
    PM->>PM: Plan en tasks/slug.json y .md
    PM->>ARQ: Tarea ARQ-001
    ARQ-->>PM: Contrato + ADR + Resultado
    alt Decisión de negocio o ADR pendiente
        PM-->>U: Pregunta y se detiene
    else Contrato aprobable
        PM->>PM: Estado aprobado y replanifica (sin commit)
    end
    loop Cada tarea OPS, API o WEB
        PM->>PM: Instantánea de git status
        PM->>DEV: Implementa la tarea (con informe de QA si es reintento)
        DEV-->>PM: Código sin commit + entrega-ID.md + Resultado
        PM->>QA: Verifica la tarea
        QA-->>PM: qa-ID.md + veredicto + bugs
        alt APROBADO
            PM->>PM: Puertas del PM, tarea done y commit sugerido
        else RECHAZADO
            PM->>PM: attempts + 1 (sin rollback)
            Note over PM,DEV: Reintento sobre el árbol de trabajo con el informe de QA (máximo 3 intentos)
        end
    end
    PM->>QA: Tareas QA de integración
    PM-->>U: Resumen, ficheros por tarea y commits sugeridos
    U->>G: Revisas, commiteas y subes
```

## 3. Bucle de una tarea (aprobación, reintento y paradas)

```mermaid
flowchart TD
    A([Tarea desbloqueada]) --> B{"api/ y web/ sin cambios ajenos?"}
    B -->|no| S1([Parar y avisar al usuario])
    B -->|sí| C["status: in_progress<br/>guarda instantánea de git status"]
    C --> D["Developer implementa<br/>lee qa-ID.md si es reintento"]
    D --> E{"Resultado del Developer"}
    E -->|bloqueado o pregunta| S2([Parar y preguntar])
    E -->|ok| F["status: in_qa"]
    F --> G["QA verifica y escribe qa-ID.md"]
    G --> H{"Veredicto"}

    H -->|APROBADO| I{"Puertas del PM en verde?"}
    I -->|no| S3([Parar y avisar])
    I -->|sí| J["status: done"]
    J --> K["Anota ficheros y commit sugerido<br/>para el resumen (no lo ejecuta)"]
    K --> N([Siguiente tarea])

    H -->|RECHAZADO| T["status: rejected<br/>attempts + 1 (sin rollback)"]
    T --> V{"attempts menor que 3?"}
    V -->|sí| C
    V -->|no| W["status: blocked"]
    W --> S5([Parar y avisar<br/>los cambios quedan en el árbol])

    classDef stop fill:#fde2e2,stroke:#c0392b,color:#7b1d1d
    classDef ok fill:#e2f5e6,stroke:#2e8b57,color:#14532d
    class S1,S2,S3,S5 stop
    class N,J,K ok
```

## 4. Estados de una tarea

```mermaid
stateDiagram-v2
    [*] --> todo
    todo --> in_progress: Developer invocado
    todo --> blocked: dependencia bloqueada
    in_progress --> in_qa: entrega lista
    in_progress --> blocked: bloqueo o pregunta
    in_qa --> done: QA APROBADO, commit sugerido
    in_qa --> rejected: QA RECHAZADO
    rejected --> in_progress: reintento sobre el árbol de trabajo
    rejected --> blocked: 3 intentos agotados
    blocked --> in_progress: desbloqueada
    done --> [*]
```

## 5. Qué pasa con el código

Ningún agente hace commits ni subidas. Todo el código queda sin commit en el árbol de trabajo hasta que lo revisas y lo commiteas tú.

```mermaid
flowchart LR
    W["Código sin commit<br/>árbol de trabajo"]
    W -->|QA APROBADO y puertas OK| D["Tarea done<br/>y commit sugerido"]
    W -->|QA RECHAZADO| R["Developer corrige<br/>sobre el árbol (sin rollback)"]
    R -->|reintento| W
    D -->|lo ejecutas tú| C["git commit y push<br/>historial"]
```

Para todos los agentes está prohibido cualquier `git` de escritura (`add`, `commit`, `push`, `pull`, `fetch`, `restore`, `clean`, `reset`, `revert`, `rebase`, `checkout`, `stash`…). Solo se permite git de lectura (`status`, `diff`, `log`, `show`, `rev-parse`).

## 6. Comportamiento interno de cada agente

### PM
```mermaid
flowchart LR
    A["Leer README, AGENTS y código"] --> B["Plan: épica, historias y tareas<br/>tasks/slug.json y .md"]
    B --> C{"Solo planificar?"}
    C -->|sí| D([Entrega el plan y para])
    C -->|no| E["Orquestar el circuito<br/>subagentes (git solo lectura)"]
    E --> F["Actualizar estados<br/>en tasks/slug.json"]
    F --> G([Resumen final y commits sugeridos])
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
    B -->|sí| C["Leer qa-ID.md<br/>corregir sobre el árbol de trabajo"]
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
| **Misión** | Planifica, orquesta y propone el commit | Diseña el contrato antes de codificar | Implementa la tarea | Verifica con evidencia |
| **Entrada** | Petición del usuario | Tarea `ARQ-*` | Tarea `API/WEB/OPS-*` + contrato aprobado (+ `qa-ID.md` si reintento) | Entrega del Developer |
| **Salida** | `tasks/` y commits sugeridos (no ejecutados) | `contracts/<slug>.md`, `contracts/adr/` | Código, tests unitarios, `entrega-ID.md` | `qa-ID.md`, `BUG-NNN`, veredicto |
| **Herramientas** | read, search, edit, execute, todo, agent | read, search, edit, todo | read, search, edit, execute, todo | read, search, edit, execute, todo |
| **Git** | Solo lectura | No (sin terminal) | Solo lectura | Solo lectura |
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
| 3 intentos fallidos de una tarea | Marca `blocked`, deja los cambios en el árbol de trabajo y avisa |
| Puerta del PM en rojo o fichero fuera de alcance o prohibido | Para y avisa |

## 10. Cómo usarlo

1. Elige el agente **PM** en el selector de chat.
2. Describe lo que quieres. Añade "solo planifica" si no quieres que ejecute el circuito.
3. Antes del primer uso, deja `api/` y `web/` sin cambios ajenos pendientes (los de tareas ya aprobadas de la épica no cuentan).
4. Al terminar, revisa `git status` y ejecuta tú los commits sugeridos y la subida.
