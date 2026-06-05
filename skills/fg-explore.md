---
name: fg-explore
description: Produce el mapa del cambio activo consultando los MCP tools de CodeGraph. Genera exploracion.md reutilizable por /fg-design. Fase 0 independiente — puede correr antes de /fg-plan.
when_to_apply: El dev invoca /fg-explore como fase 0 de un cambio nuevo, o en cualquier momento durante un cambio activo. El orquestador ya creó o nombró la carpeta del cambio (kebab-case) antes de invocar esta skill. No se requiere que /fg-plan haya corrido previamente.
---

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, E)

# /fg-explore

## Propósito

Centralizar la exploración del codebase que hoy está duplicada en `/fg-plan`, `/fg-design` y `legacy-impact-analyzer`. Dado un cambio activo, consulta CodeGraph con los MCP tools reales en pasada ordenada y produce `docs/auditoria/cambios/<cambio>/exploracion.md` — un mapa reutilizable con archivos afectados reales, consumidores, acoplamientos ocultos y señales fuertes para el orquestador.

El mapa no es efímero: vive en disco dentro del expediente del cambio para trazabilidad y para que `/fg-design` (3c — diferido) lo use como fuente primaria en lugar de re-explorar.

## Cuándo aplicarla

- Como **fase 0 independiente**: el orquestador invoca `/fg-explore` antes de `/fg-plan` cuando quiere un mapa del cambio antes de diseñar. La carpeta del cambio ya existe (creada por el orquestador); `/fg-plan` corre después si el dev lo desea.
- Directamente por el dev: `/fg-explore` en cualquier momento durante un cambio activo.

## Proceso

### 1. Cargar contexto y config

Ejecutar las secciones A y E de `fg-phase-common.md`:

- Leer `docs/auditoria/config.yaml` (reglas de TDD, PR size, módulos transversales si aplica).
- Ejecutar el GATE de re-detección lazy (`forge.bootstrap.needs_detection`).
- Verificar idempotencia según Sección E antes de generar cualquier artefacto.

### 2. Resolver el cambio activo

Identificar la carpeta del cambio activo bajo `docs/auditoria/cambios/`.

**Condición de avance**: debe existir la carpeta `docs/auditoria/cambios/<cambio>/`. La descripción o alcance del cambio se recibe como input semántico del orquestador; si existe `README.md` en la carpeta, puede usarse como fuente complementaria pero **no es obligatorio**.

Si no existe ningún cambio activo o no se puede identificar la carpeta:

- Preguntar al dev: "¿Cuál es el cambio activo? (ej: `2026-05-feat-login-usuarios`)"
- Si el dev no puede especificarlo, abortar con mensaje claro:
  > "No se encontró ninguna carpeta de cambio activo bajo `docs/auditoria/cambios/`. El orquestador debe crear la carpeta del cambio antes de invocar `/fg-explore`."
- **MUST NOT** generar ningún artefacto parcial antes de resolver este gate.

Usar como entrada semántica para la pasada de CodeGraph: la descripción del cambio recibida del orquestador; si existe `README.md`, complementar con sus secciones Qué, Por qué, Alcance.

### 3. Consultar CodeGraph en pasada ordenada

Invocar los MCP tools de CodeGraph **en este orden**, pasando la descripción/alcance del cambio (recibida del orquestador, complementada con `README.md` si existe) como entrada semántica:

**3.1 Exploración semántica del área**

Invocar `mcp__codegraph__codegraph_explore` con la descripción del cambio como query.
Objetivo: identificar los módulos y subsistemas semánticamente relacionados con el cambio.

**3.2 Búsqueda de símbolos por nombre**

Invocar `mcp__codegraph__codegraph_search` con los nombres de entidades concretas mencionadas en el README.
Objetivo: mapear clases, funciones o módulos nominados explícitamente.

**3.3 Ubicación y detalle de símbolos**

Invocar `mcp__codegraph__codegraph_files` para obtener la estructura de archivos y módulos relacionados.
Invocar `mcp__codegraph__codegraph_node` para obtener el detalle de símbolos concretos identificados en 3.1–3.2.
Objetivo: construir la lista de archivos afectados reales (sección 2 del mapa).

**3.4 Consumidores y blast radius**

Invocar `mcp__codegraph__codegraph_callers` para cada símbolo principal: quién lo llama.
Invocar `mcp__codegraph__codegraph_callees` para entender de qué depende el símbolo afectado.
Invocar `mcp__codegraph__codegraph_impact` para calcular el blast radius transitivo.
Objetivo: poblar sección 3 (consumidores) y calcular señales fuertes para sección 5.

**3.5 Panorama del índice (condicional)**

Invocar `mcp__codegraph__codegraph_status` si el contexto del codebase es desconocido o si algún tool de los pasos anteriores retornó vacío/error.
Objetivo: diagnosticar si el índice está disponible y qué cobertura tiene.

**Manejo de errores en la pasada**:

- Si un tool específico falla o retorna error: marcar esa sección del mapa con `[no disponible — error en mcp__codegraph__codegraph_<tool>]` y continuar con los tools que sí responden.
- Si `mcp__codegraph__codegraph_status` reporta índice vacío o no responde: pasar directamente al **paso 4 — modo degradado**.
- Nunca abortar la ejecución completa por fallo de un tool individual.

### 4. Aplicar criterio de modo exposición (acoplamientos no obvios)

Con los datos de consumidores obtenidos en el paso 3.4, detectar dependencias ocultas aplicando el criterio:

- Un símbolo tiene consumidores vía `mcp__codegraph__codegraph_callers` / `mcp__codegraph__codegraph_impact` que **no estaban contemplados en el alcance inicial del README**.
- Un archivo parece no afectado por nombre pero sí aparece en el blast radius por dependencia estructural.
- Módulos de uso transversal (configuración, autenticación, logging, manejo de errores) que aparecen en el impact graph.

Documentar cada dependencia oculta encontrada: símbolo/módulo → razón por la que está afectado.
Si no se detectan: registrar "Ninguno detectado con el nivel actual de análisis."

### 4.5 Consultar Context7 para librerías externas detectadas (TRIGGER A — selectivo)

**Gate de nivel**: este paso se ejecuta SOLO cuando el orquestador ya determinó el nivel del cambio como `rapido` o `completo` (aplicando `orchestrator-rule.md`). En cambios de nivel `libre` NO se consulta Context7 (preserva el cupo de 1000 req/mes).

**Condición de activación**: al construir la sección 2 (archivos afectados reales), si alguno de los archivos afectados contiene imports o dependencias de **librerías externas** (no código del propio repo), activar este paso.

**Procedimiento** (una vez por ejecución, deduplicado, máximo 2-3 librerías):

1. Identificar librerías externas únicas presentes en los archivos afectados (deduplicar nombres exactos).
2. Para cada librería (hasta 3), ejecutar el par de llamadas:
   - `mcp__context7__resolve-library-id` con el nombre de la librería → obtener el ID canónico.
   - `mcp__context7__get-library-docs` con el ID y una query centrada en lo que el cambio usa de esa librería.
3. Anexar los resultados al mapa como subsección opcional bajo el nombre **"Docs de librerías externas (Context7)"**.
4. Si Context7 no responde o devuelve error de cuota: marcar `[no disponible — error en Context7]` y **continuar** (la indisponibilidad de Context7 NUNCA bloquea el mapa).

**Privacidad**: solo viajan el nombre de la librería y la query de documentación. El código del dev, rutas de archivos e identificadores del proyecto **nunca** salen del entorno local. El backend es closed-source Upstash.

### 5. Calcular bloque de señales fuertes

Con los datos de los pasos 3.4 y 4, calcular los 4 campos del bloque de señales fuertes:

| Campo | Cómo calcularlo |
|-------|-----------------|
| `consumidores` | Conteo de consumidores directos retornados por `mcp__codegraph__codegraph_callers` / `mcp__codegraph__codegraph_impact` |
| `blast_radius` | `chico` (≤ 3 consumidores directos, sin transversales) / `mediano` (4-10 o 1 transversal) / `grande` (> 10 o ≥ 2 transversales) |
| `toca_transversales` | `true` si algún módulo en el impact graph está en `config/modulos-transversales.yaml`; `false` en caso contrario |
| `nivel_sugerido` | `rapido` si blast_radius=chico AND toca_transversales=false; `completo` en cualquier otro caso |

**Bajo degradación graceful** (CodeGraph no disponible):

```yaml
consumidores: desconocido
blast_radius: desconocido
toca_transversales: false
nivel_sugerido: completo
```

Los 4 campos son **obligatorios en todo caso** — bajo degradación se usan valores conservadores, nunca se omite la sección.

### 6. Escribir `exploracion.md`

Crear `docs/auditoria/cambios/<cambio>/exploracion.md` desde `templates/exploracion.md`.

**Idempotencia (Sección E de `fg-phase-common.md`)**:

Si `exploracion.md` ya existe para el cambio activo:

- NO sobrescribir silenciosamente.
- Mostrar al dev:
  > "Ya existe `exploracion.md` para `<cambio>`. ¿Qué querés hacer?
  > 1. **Regenerar** — reemplazar con el mapa actualizado (esta ejecución).
  > 2. **Conservar** — mantener el existente, abortar esta ejecución.
  > 3. **Abortar** — revisar el existente manualmente antes de decidir."
- Si el dev elige Regenerar: sobrescribir con el mapa nuevo.
- Si el dev elige Conservar o Abortar: retornar `status: success` (con nota en `risks`) sin modificar el archivo.

**Contenido del archivo** (poblar las 6 secciones de `templates/exploracion.md`):

1. **Área del cambio** — resumen semántico del output de `mcp__codegraph__codegraph_explore`.
2. **Archivos afectados reales** — paths de `mcp__codegraph__codegraph_files` + `mcp__codegraph__codegraph_node` con marca nuevo/modificado.
3. **Consumidores / blast radius** — tabla de consumidores de `mcp__codegraph__codegraph_callers` + `mcp__codegraph__codegraph_impact`.
4. **Acoplamientos no obvios** — dependencias ocultas detectadas en paso 4.
5. **Señales fuertes** — bloque YAML calculado en paso 5, entre delimitadores `<!-- señales_fuertes: inicio -->` / `<!-- señales_fuertes: fin -->`.
6. **Resumen de riesgo** — síntesis de 2-4 oraciones combinando secciones 3, 4 y 5.

Las secciones no disponibles por degradación deben contener la marca correspondiente, no quedar vacías.

### 7. Retornar envelope

Completar el envelope de retorno con todos los campos base de Sección B más los campos extendidos de `/fg-explore`.

Ver sección **Envelope de retorno** al final de este archivo.

## Degradación graceful

Cuando CodeGraph no está indexado o disponible, `/fg-explore` **MUST NOT bloquear el flujo del dev**.

**Política de degradación**:

| Situación | Comportamiento |
|-----------|----------------|
| `mcp__codegraph__codegraph_status` reporta índice vacío | Pasar a modo degradado completo: todas las secciones con `[sin datos — CodeGraph no indexado]` |
| `mcp__codegraph__codegraph_status` no responde | Idem — asumir no indexado |
| Tool individual falla (ej: `mcp__codegraph__codegraph_callers`) | Marcar esa sección: `[no disponible — error en mcp__codegraph__codegraph_callers]` y continuar |
| Índice disponible pero sin resultados para el cambio | Registrar "Sin resultados para el área del cambio" en la sección afectada |

**Retorno bajo degradación**: `status: partial`. El campo `risks` MUST describir qué secciones quedaron incompletas y por qué.

**NEVER** retornar `status: blocked` solo porque CodeGraph no está disponible. Solo retornar `blocked` si falta el cambio activo (gate del paso 2).

## Reglas

### Siempre

- Ejecutar el gate del paso 2 antes de generar cualquier artefacto: sin carpeta del cambio activo, no avanzar.
- Usar los tool names reales de CodeGraph: `mcp__codegraph__codegraph_explore`, `mcp__codegraph__codegraph_search`, `mcp__codegraph__codegraph_files`, `mcp__codegraph__codegraph_node`, `mcp__codegraph__codegraph_callers`, `mcp__codegraph__codegraph_callees`, `mcp__codegraph__codegraph_impact`, `mcp__codegraph__codegraph_status`. No usar narrativa vaga como "consultar CodeGraph" sin el nombre del tool.
- Respetar la idempotencia (paso 6): si `exploracion.md` ya existe, preguntar antes de sobrescribir.
- Incluir los 4 campos del bloque de señales fuertes en toda ejecución — con valores conservadores bajo degradación.
- Retornar `status: partial` (nunca `blocked`) cuando CodeGraph no está disponible.
- Escribir `exploracion.md` en español.

### Preguntar

- Cuándo no hay cambio activo claro: cuál es el cambio sobre el que explorar.
- Cuándo `exploracion.md` ya existe: si regenerar, conservar, o abortar.
- Cuándo el blast radius detectado sea grande y no esperado por el dev: confirmar antes de cerrar.

### Nunca

- Generar un artefacto parcial antes de resolver el gate del paso 2 (sin carpeta del cambio activo).
- Retornar `status: blocked` solo por indisponibilidad de CodeGraph.
- Sobrescribir `exploracion.md` existente sin confirmación explícita del dev.
- Omitir la sección de señales fuertes ni dejar los 4 campos sin valor.
- Usar nombres narrativos de tools en lugar de los nombres reales `mcp__codegraph__codegraph_*`.
- Abortar silenciosamente por fallo de un tool individual — degradar y continuar.
- Consultar Context7 en cambios de nivel `libre` ni para librerías del propio repo (solo librerías externas, solo niveles `rapido`/`completo`).
- Exigir que `/fg-plan` haya corrido previamente — `/fg-explore` es fase 0 independiente.

## Punto de integración diferido (documentación)

**3c — Consumo en fg-design** (diferido):

`skills/fg-design.md` paso 2 deberá chequear si existe `exploracion.md` antes de re-consultar CodeGraph; si existe, usarlo como fuente primaria (complementar, no duplicar). La unificación del criterio de "dependencia oculta" con `agents/legacy-impact-analyzer.md` también es 3c.

## Envelope de retorno

```yaml
status: success | partial | blocked
executive_summary: <1-2 oraciones de lo que se exploró y encontró>
artifacts:
  - docs/auditoria/cambios/<cambio>/exploracion.md (creado | regenerado | preservado)
mapa_path: docs/auditoria/cambios/<cambio>/exploracion.md
senales_fuertes:
  consumidores: <N | desconocido>
  blast_radius: chico | mediano | grande | desconocido
  toca_transversales: true | false
  nivel_sugerido: rapido | completo
next_recommended: /fg-design
risks: None | <descripción de limitaciones — secciones parciales, CodeGraph no disponible, etc.>
skill_resolution: paths-injected | fallback-registry | fallback-path | none
```
