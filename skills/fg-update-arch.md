---
name: fg-update-arch
description: Mantiene actualizada la documentación permanente del proyecto en docs/arquitectura/ a partir de los cambios estructurales. Lee architecture actual + cambios cerrados marcados como estructurales + topología del código vía CodeGraph. Propone diff por archivo, NO todo-o-nada. El dev acepta cada propuesta individualmente.
when_to_apply: Sugerida por /fg-review cuando detecta cambios estructurales en un cambio que se está cerrando. También invocable manualmente cuando el dev quiere consolidar varios cambios pendientes en una sola actualización de arquitectura.
---

> Cargar antes: `skills/_shared/fg-phase-common.md` (secciones A, B, E)

# /fg-update-arch

## Propósito

Mantener la documentación permanente del sistema (`docs/arquitectura/`) sincronizada con la realidad del código. Sin esto, la doc se vuelve obsoleta en 3 meses y nadie le cree.

A diferencia del `README.md`, `diseño.md`, `tareas.md` y `decisiones.md` por cambio (que son episódicos), `docs/arquitectura/` describe **cómo es el sistema HOY**, evoluciona lento y es lo que un dev nuevo lee para entender el proyecto.

## Cuándo aplicarla

- **Sugerida automáticamente por `/fg-review`** cuando detecta cambios estructurales (nuevas dependencias, módulos top-level nuevos, cambios en módulos transversales, migraciones de BD).
- **Invocable manualmente** cuando el dev siente que la arquitectura quedó atrás (típicamente después de varios cambios chicos que en conjunto reorganizaron una parte del sistema).

## Carga obligatoria

- Verificar que existe el detector de cambios estructurales (`forge/structural_detector.py`).
- Verificar que CodeGraph está disponible y el índice está fresco.

## Proceso

### 1. Leer el estado actual de la arquitectura

- Si existe `docs/arquitectura/`: leer `overview.md`, `stack.md`, y los ADRs en `decisions/`.
- Si NO existe (primer uso de `/fg-update-arch`): crearla con templates vacíos y marcarlos como "a llenar a partir del análisis de este uso".

### 2. Identificar los cambios estructurales a consolidar

Dos modos:

**Modo a) Modo "cambio único" (cuando `/fg-review` invoca)**:
- Solo se procesa el cambio que está cerrando (su `README.md` con `structural: true` en el frontmatter).

**Modo b) Modo "consolidación" (invocación manual)**:
- Listar los cambios cerrados en `docs/auditoria/cambios/` cuyo frontmatter tenga `structural: true` y que no hayan sido consolidados todavía (marca opcional en frontmatter: `arch_synced: false`).
- Procesar todos en orden cronológico.

Si el dev quiere precisión, puede pasar argumentos explícitos: `/fg-update-arch desde-fecha 2026-04-01` o `/fg-update-arch cambio 2026-05-feat-login-usuarios`.

### 3. Consultar CodeGraph para reconciliar la topología

Para cada cambio estructural a procesar, identificar con CodeGraph:

- Módulos top-level nuevos.
- Entidades de dominio nuevas (clases, structs, types).
- Cambios en dependencias internas (qué módulo llama a qué).
- Cambios en módulos marcados como transversales (config `modulos-transversales.yaml`).

Para cambios en dependencias externas, leer el diff de los archivos de manifiesto (`requirements.txt`, `package.json`, `go.mod`, etc.) del commit cerrado.

Para cambios de schema BD, leer el diff de los archivos de migración.

### 4. Generar propuestas de actualización por archivo

**Reglas para distribuir cambios**:

| Naturaleza del cambio | Va a |
|---|---|
| Nueva dependencia externa o cambio de versión | `stack.md` (sección "Dependencias") |
| Cambio del motor de BD o versión | `stack.md` (sección "Almacenamiento") |
| Nuevo módulo top-level o reorganización de módulos | `overview.md` (sección "Estructura general") |
| Nueva integración con sistema externo | `overview.md` (sección "Integraciones") |
| Decisión que va a influir muchos cambios futuros | **ADR nuevo** en `decisions/` |
| Cambio que invalida un ADR existente | **Marcar ADR existente como `superseded-by`** + nuevo ADR |

### 5. Heurística para "crear ADR vs actualizar overview/stack"

Crear ADR cuando:

- La decisión va a condicionar el código de varios módulos en el futuro (no solo el módulo donde se aplicó).
- Hay alternativas razonables que fueron consideradas y descartadas — el ADR documenta el por qué.
- Si en 6 meses alguien pregunta "por qué hacen X así", la respuesta natural es "porque decidimos Y, mirá el ADR Z".

Actualizar `overview.md` o `stack.md` cuando:

- Es un hecho descriptivo del sistema actual (qué dependencias usamos, qué módulos hay, cómo están organizados).
- No requiere justificar la elección, solo describir lo que es.

### 6. Presentar las propuestas al dev como diff por archivo

**Nunca todo-o-nada**. Cada propuesta se presenta independiente:

```
=== Propuesta 1: actualizar docs/arquitectura/stack.md ===
Sección: Dependencias

+ - bcrypt 4.0.1 (hashing de passwords, agregado en 2026-05-feat-login-usuarios)
+ - python-jose 3.3.0 (JWT, agregado en 2026-05-feat-login-usuarios)

¿Aceptar [a], editar [e], rechazar [r]?

=== Propuesta 2: crear docs/arquitectura/decisions/001-auth-jwt.md ===

# ADR 001 — Autenticación con JWT en vez de sesiones por cookie

## Contexto
[...]

## Decisión
Usamos JWT firmados con secret rotativo para autenticación stateless.

## Alternativas consideradas
- Sesiones por cookie con store en Redis
- OAuth2 con provider externo

## Consecuencias
[...]

¿Aceptar [a], editar [e], rechazar [r]?
```

### 7. Para cada propuesta aceptada

- Aplicar el cambio al archivo correspondiente.
- Si es un ADR nuevo: usar el siguiente número en secuencia (`001`, `002`, etc.).
- Si es un ADR que supersede a otro: marcar el viejo con `superseded-by: ADR-NNN`.

Si el dev edita la propuesta antes de aceptar, aplicar la versión editada.

Si el dev rechaza, no aplicar y registrar que se decidió no incluir ese cambio en arquitectura (opcionalmente, agregar nota en el cambio original).

### 8. Marcar los cambios procesados

Para cada cambio del que se extrajeron actualizaciones, agregar al frontmatter del `README.md`:

```yaml
---
structural: true
arch_synced: true
arch_synced_at: <YYYY-MM-DD>
---
```

Esto evita que el próximo `/fg-update-arch` los reprocese.

### 9. Reportar al dev

- Cantidad de propuestas presentadas, aceptadas, editadas y rechazadas.
- Lista de ADRs creados o modificados.
- Sugerir hacer commit de los cambios a `docs/arquitectura/`.

## Reglas

### Siempre

- Propuestas independientes, una por archivo afectado.
- Usar CodeGraph para reconciliar topología (no inventar relaciones).
- Heurística clara para ADR vs overview/stack.
- Marcar cambios procesados con `arch_synced: true` para no reprocessar.
- Idempotente: re-correr no propone los mismos cambios si ya fueron aceptados.

### Preguntar

- Cuando hay ambigüedad sobre si una decisión amerita ADR o solo update de overview.
- Cuando dos cambios estructurales sugieren updates conflictivos al mismo archivo.

### Nunca

- Aplicar cambios sin que el dev acepte cada propuesta individualmente.
- Sobrescribir un ADR existente (los ADRs son inmutables — si la decisión cambió, se crea un ADR nuevo que supersede al viejo).
- Inventar consecuencias o alternativas para los ADRs — basarse en el `diseño.md` y `decisiones.md` del cambio.
- En modo bootstrap (durante `/fg-setup`), `overview.md` y `stack.md` se crean a partir de la conversación de visión del sistema. `/fg-update-arch` es el mecanismo para reconciliar la documentación con código existente, no para inicializarla.

## Envelope de retorno

```yaml
status: success | partial
executive_summary: 1-2 oraciones de lo que se consolidó
proposals_total: <N>
proposals_accepted: <N>
proposals_edited: <N>
proposals_rejected: <N>
adrs_created:
  - <ADR-NNN — título>
adrs_superseded:
  - <ADR-NNN viejo — superseded por ADR-NNN nuevo>
files_updated:
  - docs/arquitectura/overview.md
  - docs/arquitectura/stack.md
  - <otros>
changes_marked_synced:
  - <YYYY-MM-tipo-nombre del cambio>
suggested_commit: true (si hubo cambios aplicados)
```
