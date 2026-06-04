# Módulo Strict TDD — fase review (validación)

> Este módulo se carga **únicamente** cuando Strict TDD Mode está activo (`rules.implement.tdd: true` en `docs/auditoria/config.yaml` del proyecto). Está `false` por defecto — el equipo lo activa editando el config y commiteando el cambio.
> Si estás leyendo esto, la condición ya fue verificada. Aplicá cada instrucción.

## Filosofía de la verificación TDD

Cuando Strict TDD está activo, la verificación va más allá de "¿el código funciona?" — la pregunta es "¿el código fue construido correctamente?". O sea: ¿se siguió TDD realmente? La fase de implement reportó evidencia TDD; tu trabajo es validarla contra la realidad.

## Paso 5a: TDD Compliance Check (incluye Assertion Quality Audit)

> **Fuente de la evidencia TDD**: `/fg-implement` persiste la tabla de evidencia en disco como `evidencia-tdd.md` dentro de la carpeta del cambio al cerrar cada batch (completo o parcial). Si el cambio requirió múltiples batches, el archivo acumula todas las filas mergeadas. Esta es la fuente primaria y garantiza que la evidencia sobreviva entre sesiones.

Verificar que TDD se siguió leyendo la evidencia de la fuente disponible:

```
Leer evidencia TDD (fuente en orden de prioridad):
├── 1. docs/auditoria/cambios/<cambio>/evidencia-tdd.md (fuente primaria — en disco).
├── 2. Envelope de retorno de /fg-implement en la sesión activa (fuente secundaria, mismo ciclo).
├── 3. tareas.md del cambio (fallback final).
├── 4. Si ninguna fuente está disponible → Flag: CRITICAL — evidencia TDD no encontrada.
│
Encontrar la tabla "Evidencia del ciclo TDD":
├── PARA CADA fila de tarea:
│   ├── Columna RED:
│   │   ├── Debe decir "✅ Escrito".
│   │   ├── Verificar: el archivo de test EXISTE en el codebase.
│   │   └── Flag: CRITICAL si el archivo de test no existe.
│   │
│   ├── Columna GREEN:
│   │   ├── Debe decir "✅ Pasó".
│   │   ├── Cross-referenciar con resultados del paso 5b:
│   │   │   └── El archivo de test listado debe PASAR cuando lo corras.
│   │   └── Flag: CRITICAL si el test falla ahora (¿realmente estaba verde?).
│   │
│   ├── Columna TRIANGULATE:
│   │   ├── Si "✅ N cases" → verificar que N test cases existen en el archivo.
│   │   ├── Si "➖ Single" → verificar que el spec realmente tiene un solo scenario para la tarea.
│   │   └── Flag: WARNING si el spec tiene múltiples scenarios pero solo hay 1 test case.
│   │
│   ├── Columna SAFETY NET:
│   │   ├── Si "✅ N/N" → los tests existentes se corrieron antes de modificar (bien).
│   │   ├── Si "N/A (new)" → verificar que el archivo fue realmente NUEVO.
│   │   └── Flag: WARNING si el archivo fue modificado pero safety net dice "N/A".
│   │
│   └── Columna REFACTOR:
│       ├── No es verificable estrictamente (calidad subjetiva).
│       └── Saltar verificación, confiar en el reporte.
│
├── Si NO se encuentra tabla "Evidencia del ciclo TDD":
│   └── Flag: CRITICAL — la fase implement no reportó evidencia TDD.
│       (Strict TDD estaba activo pero implement no siguió el protocolo).
│
└── Resumen: "{N}/{total} tareas tienen evidencia TDD completa".
```

## Paso 5: Test Layer Validation

Clasificar TODOS los archivos de test relacionados al cambio por su layer:

```
Scan archivos de test creados/modificados por este cambio:
├── Clasificar cada archivo:
│   ├── Unit test: testea una función/clase aislada.
│   │   └── Indicadores: no render(), no page., no llamadas HTTP, dependencias mockeadas.
│   ├── Integration test: testea interacción de componentes o comportamiento de usuario.
│   │   └── Indicadores: render(), screen., userEvent., imports de testing-library.
│   ├── E2E test: testea el sistema entero a través de browser/HTTP reales.
│   │   └── Indicadores: page.goto(), imports playwright/cypress, browser context.
│   └── Desconocido: no se puede clasificar → reportar tal cual.
│
├── Reportar distribución:
│   ├── Unit: {N} tests en {N} archivos.
│   ├── Integration: {N} tests en {N} archivos.
│   ├── E2E: {N} tests en {N} archivos.
│   └── Total: {N} tests.
│
├── Cross-referenciar con capabilities:
│   ├── Si hay integration tests pero los tools no están en capabilities → ¿cómo?
│   ├── Si hay E2E tests pero los tools no están en capabilities → ¿cómo?
│   └── Flag: WARNING si tests usan tools no detectados en capabilities.
│
└── Para cada spec scenario: notar qué layer lo cubre.
    └── Flag: SUGGESTION si lógica de negocio crítica solo tiene unit tests
        (solo si hay integration/E2E disponibles).
```

## Paso 5d: Cobertura de archivos cambiados

Cuando hay tool de coverage disponible, reportar cobertura para archivos CAMBIADOS específicamente:

```
SI hay tool de coverage (de capabilities cacheadas):
├── Correr: {test_command} --coverage (o equivalente).
├── Parsear el reporte de coverage.
├── Filtrar a SOLO archivos creados o modificados en este cambio
│   (lista de archivos de la tabla "Files Changed" del apply-progress).
├── Reportar por archivo:
│   ├── Path del archivo.
│   ├── % de cobertura de líneas.
│   ├── % de cobertura de branches (si disponible).
│   ├── Rangos de líneas no cubiertas (líneas específicas, no solo %).
│   └── Flag por archivo:
│       ├── ≥ 95% → ✅ Excelente.
│       ├── ≥ 80% → ⚠️ Aceptable.
│       └── < 80% → ⚠️ Bajo (listar líneas no cubiertas).
├── Reportar agregado:
│   ├── Cobertura promedio de archivos cambiados.
│   ├── Total de líneas no cubiertas en archivos cambiados.
│   └── Comparar contra threshold si está configurado.
└── Flag: WARNING si algún archivo cambiado < 80% cobertura.

SI NO hay tool de coverage:
└── Reportar: "Análisis de coverage saltado — no se detectó tool de coverage."
    (NO es falla — simplemente no está disponible).
```

## Paso 5e: Métricas de calidad

Correr quality checks SOLO en archivos cambiados, SOLO si hay tools disponibles:

```
Leer quality tools de capabilities cacheadas:

SI hay linter:
├── Correr linter en archivos cambiados solamente.
├── Reportar: errores y warnings.
└── Flag: WARNING para errors, SUGGESTION para warnings.

SI hay type checker:
├── Correr type checker (usualmente whole-project, no per-file).
├── Filtrar output a archivos cambiados.
├── Reportar: errors de tipo en archivos cambiados.
└── Flag: WARNING para type errors.

SI no hay ninguno:
└── Reportar: "Quality metrics saltado — no se detectaron tools."
```

## Extensión del template del reporte

Cuando Strict TDD Mode está activo, tu reporte de verificación DEBE incluir estas secciones adicionales:

```markdown
### TDD Compliance
| Check | Resultado | Detalles |
|-------|-----------|----------|
| Evidencia TDD reportada | ✅ / ❌ | {Encontrada en evidencia-tdd.md / envelope de sesión / tareas.md / Ausente} |
| Todas las tareas tienen tests | ✅ / ❌ | {N}/{total} tareas tienen archivos de test |
| RED confirmado (tests existen) | ✅ / ⚠️ | {N}/{total} archivos de test verificados |
| GREEN confirmado (tests pasan) | ✅ / ❌ | {N}/{total} tests pasan en ejecución |
| Triangulación adecuada | ✅ / ⚠️ / ➖ | {N} tareas trianguladas / {N} single-case |
| Safety Net para archivos modificados | ✅ / ⚠️ | {N}/{total} archivos modificados con safety net |

**TDD Compliance**: {N}/{total} checks pasaron.

---

### Distribución de test layers
| Layer | Tests | Archivos | Tools |
|-------|-------|----------|-------|
| Unit | {N} | {N} | {tool} |
| Integration | {N} | {N} | {tool o "no instalado"} |
| E2E | {N} | {N} | {tool o "no instalado"} |
| **Total** | **{N}** | **{N}** | |

---

### Cobertura de archivos cambiados
| Archivo | Líneas % | Branches % | Líneas no cubiertas | Rating |
|---------|----------|------------|---------------------|--------|
| `path/to/file.ext` | 95% | 90% | — | ✅ Excelente |
| `path/to/other.ext` | 82% | 75% | L45-48, L62 | ⚠️ Aceptable |
| `path/to/new.ext` | 100% | 100% | — | ✅ Excelente |

**Cobertura promedio de archivos cambiados**: {N}%
{o "Análisis de coverage saltado — no se detectó tool de coverage"}

---

### Calidad de assertions
| Archivo | Línea | Assertion | Issue | Severidad |
|---------|-------|-----------|-------|-----------|
| ... | ... | ... | ... | ... |

**Calidad de assertions**: {N} CRITICAL, {N} WARNING
{o "✅ Todas las assertions verifican comportamiento real"}

---

### Quality Metrics
**Linter**: ✅ Sin errors / ⚠️ {N} warnings / ❌ {N} errors / ➖ No disponible
**Type Checker**: ✅ Sin errors / ❌ {N} errors / ➖ No disponible
```

## Paso 5f: Assertion Quality Audit (MANDATORY)

Scanear TODOS los archivos de test creados o modificados por este cambio y buscar assertions triviales/sin sentido:

```
PARA CADA archivo de test relacionado al cambio:
├── Leer el contenido.
├── Buscar BANNED patterns:
│   ├── Tautologías: expect(true).toBe(true), assert True, expect(1).toBe(1).
│   ├── Empty checks huérfanos: expect(result).toEqual([]) o assert len(result) == 0
│   │   └── A MENOS que haya un test compañero con mismo setup que asserte NON-EMPTY.
│   ├── Type-only assertions solas: toBeDefined(), not.toBeNull(), typeof checks
│   │   └── OK si están COMBINADAS con value assertions en el mismo test.
│   ├── Assertions que nunca call código de producción (no function call, no render, no request).
│   ├── Ghost loops: assertions adentro de for/forEach sobre resultados de queryAll/filter
│   │   └── Chequear si la collection puede estar vacía — si sí, las assertions NUNCA CORREN.
│   │       Flag: CRITICAL — un loop sobre array vacío es test que SIEMPRE pasa.
│   ├── Ciclo TDD incompleto: test pasa porque las precondiciones impiden que el código corra
│   │   └── Ej: testear comportamiento de un componente que nunca se renderiza por estado.
│   │       Flag: CRITICAL — el test debe setear condiciones donde el code path SÍ se ejercita.
│   ├── Smoke-test-only: render() + toBeInTheDocument() sin behavioral assertions
│   │   └── "Renders sin crash" NO es test válido — debe asertar QUÉ se renderizó.
│   │       Flag: WARNING — smoke tests no cuentan para cobertura TDD.
│   ├── Acoplamiento a detalles de implementación: assertions sobre CSS classes, estado interno, mock call counts
│   │   └── expect(el.className).toContain("text-xs") o expect(mock.calls.length).toBe(3)
│   │       Flag: WARNING — los tests deben asertar comportamiento, no implementación.
│   └── Ratio mock/assertion: contar vi.mock() calls vs expect() calls por archivo
│       └── Si mocks > 2× assertions → Flag: WARNING — "Mock-heavy test ({N} mocks, {N} assertions)".
│           Recomendar: extraer lógica a función pura o mover a layer más alto.
│
├── Para cada violación encontrada:
│   ├── Registrar: archivo, línea, la assertion, por qué es trivial.
│   └── Clasificar:
│       ├── CRITICAL: tautología (expect(true).toBe(true)) — test prueba NADA.
│       ├── CRITICAL: assertion sin call al código de producción — test no ejercita nada.
│       ├── CRITICAL: ghost loop — assertions en loop sobre collection posiblemente vacía.
│       ├── WARNING: empty collection sin compañero non-empty.
│       ├── WARNING: type-only assertion sin value assertion.
│       ├── WARNING: smoke-test-only — render + toBeInTheDocument sin behavioral check.
│       ├── WARNING: CSS class / implementation detail assertion.
│       └── WARNING: mock-heavy test (mocks > 2× assertions) — layer equivocado.
│
├── Chequear calidad de triangulación:
│   ├── Contar test cases distintos por comportamiento.
│   ├── Si solo hay 1 test case para comportamiento con múltiples spec scenarios:
│   │   └── Flag: WARNING — "Triangulación insuficiente para {comportamiento}".
│   ├── Si todos los test cases assertan el MISMO tipo de valor (ej: todos chequean empty arrays):
│   │   └── Flag: WARNING — "Sin variación en expectativas de test — todos assertan empty/trivial".
│   └── Un comportamiento bien triangulado tiene tests asertando valores DIFERENTES.
│
└── Resumen: "{N} assertions triviales encontradas en {N} archivos".
```

### Tabla del Assertion Quality Report

Incluir esta tabla en el reporte de verificación cuando se encuentran issues:

```markdown
### Calidad de assertions
| Archivo | Línea | Assertion | Issue | Severidad |
|---------|-------|-----------|-------|-----------|
| `path/test.ts` | 15 | `expect(true).toBe(true)` | Tautología — no prueba nada | CRITICAL |
| `path/test.ts` | 23 | `expect(result).toEqual([])` | Empty sin compañero non-empty | WARNING |
| `path/test.ts` | 31 | `expect(result).toBeDefined()` | Type-only — sin value asertado | WARNING |

**Calidad de assertions**: {N} CRITICAL, {N} WARNING
```

Si no se encontraron issues, reportar: "**Calidad de assertions**: ✅ Todas las assertions verifican comportamiento real".

## Reglas (Strict TDD Verify)

- SIEMPRE buscar la tabla "Evidencia del ciclo TDD" — primero en `evidencia-tdd.md` de la carpeta del cambio (fuente primaria en disco), luego en el envelope de sesión de `/fg-implement`, luego en `tareas.md`. Es el artifact primario.
- SIEMPRE cross-referenciar archivos de test reportados contra ejecución real — no confiar ciegamente en el reporte.
- SIEMPRE correr el Assertion Quality Audit (paso 5f) — tests triviales son PEORES que tests ausentes.
- Si no se encuentra tabla de evidencia TDD en ninguna fuente disponible, flag como CRITICAL — el protocolo no se siguió.
- Si se encuentran tautologías (expect(true).toBe(true)), flag como CRITICAL — DEBEN reescribirse.
- Cobertura y quality metrics son INFORMATIVOS, NO bloqueantes — flag como WARNING, nunca CRITICAL.
- Distribución de test layers es informativa — solo SUGGESTION.
- NO arreglar issues — solo reportar. El orquestador decide.
- Si tools de coverage/quality no están disponibles, decirlo limpio y seguir — nunca flagear tools ausentes como falla.
