# Módulo Strict TDD — fase implement

> Este módulo se carga **únicamente** cuando Strict TDD Mode está activo (`/fg-setup` detectó test runner en el proyecto).
> Si estás leyendo esto, ya se verificaron las dos condiciones. Aplicá cada instrucción.

## Filosofía TDD

TDD no es testing. TDD es **diseño de software guiado por tests**. Escribís un test que describe lo que el código DEBERÍA hacer, después escribís el código mínimo para que sea real. Los tests diseñan la API, los contratos, el comportamiento. El código es side effect de los tests.

### Las tres leyes

1. **NO escribir código de producción** sin un test fallando.
2. **NO escribir más test** que el necesario para fallar.
3. **NO escribir más código** que el necesario para pasar el test.

## Ciclo TDD

Para CADA tarea del checklist, aplicá este ciclo estrictamente:

```
PARA CADA TAREA:
├── 0. SAFETY NET (solo si modificás archivos existentes)
│   ├── Correr tests existentes de los archivos que vas a modificar.
│   ├── Capturar baseline: "{N} tests pasan".
│   ├── Si alguno FALLA → STOP, reportar como "pre-existing failure"
│   │   (NO arreglar fallas pre-existentes — reportar al orquestador).
│   └── Esta baseline prueba que no rompiste lo que ya funcionaba.
│
├── 1. UNDERSTAND
│   ├── Leer la descripción de la tarea.
│   ├── Leer los scenarios relevantes del spec (son tus criterios de aceptación).
│   ├── Leer las decisiones del design (CONDICIONAN tu approach).
│   ├── Leer código existente y patrones de tests (replicar el estilo).
│   └── Decidir test layer (ver "Elegir test layer" abajo).
│
├── 2. RED — Escribir un test fallando PRIMERO
│   ├── Escribir el test que describe el comportamiento esperado del spec.
│   ├── Preferir funciones puras cuando se pueda (sin side effects = fácil de testear).
│   ├── El test DEBE referenciar código de producción que NO existe aún
│   │   (esto garantiza el fallo — no hace falta ejecutar para confirmarlo).
│   ├── Si la función/clase ya existe:
│   │   └── Escribir test para el NUEVO comportamiento que aún no está implementado.
│   └── GATE: NO avanzar a GREEN sin el test escrito.
│
├── 3. GREEN — Escribir el código MÍNIMO para pasar
│   ├── Implementar SOLO lo que el test fallando necesita.
│   ├── Fake It es VÁLIDO acá (return hardcodeado está OK).
│   ├── EJECUTAR tests → debe PASAR.
│   │   ├── ✅ Pasó → avanzar a TRIANGULATE o REFACTOR.
│   │   └── ❌ Falló → arreglar la implementación, NO el test.
│   └── GATE: NO avanzar sin GREEN confirmado por ejecución.
│
├── 4. TRIANGULATE (MANDATORY para la mayoría de tareas)
│   ├── DEFAULT: triangulación es REQUERIDA. Necesitás razón fuerte para saltarla.
│   ├── Agregar un segundo test case con inputs/outputs DIFERENTES.
│   ├── EJECUTAR tests → si el Fake It se rompe (hardcoded ya no funciona):
│   │   └── Generalizar a lógica real (esto es todo el punto).
│   ├── Repetir hasta que TODOS los scenarios del spec estén cubiertos.
│   ├── Cada pasada de triangulación: escribir test → correr → arreglar implementación.
│   ├── MÍNIMO: al menos 2 test cases por comportamiento (happy + edge case).
│   │   ├── Un test con datos que producen un resultado NO-TRIVIAL.
│   │   └── Un test con datos que ejercitan un PATH DISTINTO del código.
│   ├── CUIDADO con GREENs que pasan trivialmente:
│   │   ├── Si el test pasa porque el componente/elemento no se renderiza → NO es GREEN real.
│   │   ├── Si el test pasa porque el loop itera 0 veces → NO es GREEN real.
│   │   ├── Si el test pasa porque el setup no dispara el code path → NO es GREEN real.
│   │   └── Un GREEN real significa: código de producción CORRIÓ y produjo el output esperado.
│   ├── Saltar triangulación SOLO cuando TODAS estas son ciertas:
│   │   ├── La tarea es puramente estructural (config, constante, export de type).
│   │   ├── Hay literalmente UN solo output posible (sin branching, sin lógica).
│   │   └── Notás explícitamente "Triangulación skipped: {razón}" en la evidencia.
│   └── GATE: todos los scenarios del spec para esta tarea deben tener tests antes de REFACTOR.
│
├── 5. REFACTOR — Mejorar sin cambiar comportamiento
│   ├── Extraer constantes (eliminar magic numbers).
│   ├── Extraer funciones (reducir complejidad ciclomática).
│   ├── Mejorar naming, eliminar duplicación.
│   ├── Empujar hacia funciones puras donde sea posible.
│   ├── Aplicar Boy Scout Rule: dejar el código más limpio que como lo encontraste.
│   ├── EJECUTAR tests después de CADA paso de refactor → deben SEGUIR PASANDO.
│   │   ├── ✅ Siguen verdes → refactor es safe, continuar.
│   │   └── ❌ Falla → REVERTIR ese paso, intentar uno más chico.
│   └── GATE: tests verdes después de CADA cambio de refactor.
│
├── 6. Marcar tarea completa [x]
└── 7. Notar cualquier desviación o issue descubierto.
```

## Elegir test layer

Basado en testing capabilities cacheadas en engram (`forge/testing-capabilities/{project}`), elegí el test layer apropiado para cada tarea:

```
Determinar layer por QUÉ hace la tarea:
├── Lógica pura, función utility, cálculo, transformación de datos
│   └── Unit test (siempre disponible si hay test runner).
│
├── Render de componente, interacción usuario, cambios de estado
│   ├── SI hay tools de integration → Integration test.
│   └── SI NO → Unit test con mocks (degradar gracefully).
│
├── Flujo multi-componente, interacción API, comportamiento context/provider
│   ├── SI hay tools de integration → Integration test.
│   └── SI NO → Unit test con mocks.
│
├── Flujo de negocio crítico, user journey completo, navegación cross-page
│   ├── SI hay tools de E2E → E2E test.
│   ├── SI NO pero hay integration → Integration test.
│   └── SI NO hay ninguno → Unit test (degradar gracefully).
│
└── Default: Unit test (siempre el fallback).
```

**Regla clave**: usar el layer MÁS ALTO disponible que encaje con la tarea. Pero NUNCA saltar una tarea porque un layer no esté disponible — degradar al siguiente layer disponible.

## Ejecución de tests

Detectar el test runner desde testing capabilities cacheadas:

```
Leer comando del runner desde:
├── Capabilities cacheadas → test_runner.command (más rápido — ya detectado).
└── Fallback: detectar de manifiestos del stack.

Al ejecutar tests durante TDD:
├── Correr SOLO el archivo de test relevante, no la suite entera.
│   ├── JS/TS: {runner} {test-file-path} (ej: pnpm vitest run src/utils/tax.test.ts)
│   ├── Python: pytest {test-file-path}
│   ├── Go: go test ./{package}/... -run {TestName}
│   └── Adaptar a la CLI del runner.
├── Esto mantiene el ciclo RÁPIDO.
└── Las corridas de suite completa se hacen en /fg-review, no acá.
```

## Preferencia por funciones puras

Al escribir código de producción en GREEN/TRIANGULATE, preferí funciones puras:

```
✅ PREFERIR (pura — fácil de testear):
function calculateDiscount(price: number, quantity: number): number {
  return quantity >= 5 ? price * quantity * 0.1 : 0
}

❌ EVITAR (impura — difícil de testear):
function calculateDiscount(item: Item) {
  globalState.lastDiscount = item.price * 0.1  // side effect
  updateDOM()                                   // side effect
  return globalState.lastDiscount
}
```

**Por qué**: las funciones puras son determinísticas (mismo input → mismo output), no tienen side effects, y son trivialmente testeables. TDD naturalmente te empuja a funciones puras — abrazar eso.

## Approval Testing (para refactor de código existente)

Cuando una tarea es REFACTOR de código existente (no escribir código nuevo):

```
ANTES de tocar código de producción:
├── 1. Identificar el comportamiento actual a preservar.
├── 2. Escribir "approval tests" que capturen el comportamiento actual:
│   ├── Llamar la función con inputs conocidos.
│   ├── Asertar los outputs ACTUALES (aunque sean feos o estén mal).
│   └── Estos tests documentan lo que el código hace AHORA.
├── 3. Correr approval tests → deben PASAR (describen la realidad actual).
├── 4. AHORA refactorizar el código de producción.
├── 5. Correr approval tests de nuevo → deben SEGUIR PASANDO.
│   ├── ✅ Pasan → refactor preservó el comportamiento.
│   └── ❌ Fallan → refactor rompió algo, revertir.
└── 6. Si el spec dice que el comportamiento debe CAMBIAR:
    ├── Actualizar el approval test para reflejar el NUEVO comportamiento esperado.
    ├── Correr → test FALLA (RED — nuevo comportamiento no implementado aún).
    └── Implementar el nuevo comportamiento → GREEN.
```

## Extensión del envelope de retorno

Cuando Strict TDD Mode está activo, tu envelope DEBE incluir esta sección:

```markdown
### Evidencia del ciclo TDD
| Tarea | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|-------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1 | `path/test.ext` | Unit | ✅ 5/5 | ✅ Escrito | ✅ Pasó | ✅ 3 cases | ✅ Limpio |
| 1.2 | `path/test.ext` | Integration | N/A (new) | ✅ Escrito | ✅ Pasó | ➖ Single | ✅ Limpio |

### Resumen de tests
- **Total tests escritos**: {N}
- **Total tests pasando**: {N}
- **Layers usados**: Unit ({N}), Integration ({N}), E2E ({N})
- **Approval tests** (refactor): {N} o "Ninguno — no hubo tareas de refactor"
- **Funciones puras creadas**: {N}
```

**Definición de columnas**:
- **Safety Net**: tests pre-existentes corridos antes de modificar archivos. "N/A (new)" para archivos nuevos.
- **RED**: test escrito primero, referencia código que no existe. Siempre "✅ Escrito".
- **GREEN**: tests ejecutados y pasando después de la implementación mínima. Debe mostrar resultado de ejecución.
- **TRIANGULATE**: test cases adicionales para forzar lógica real. "➖ Single" si el spec tiene un solo scenario.
- **REFACTOR**: código mejorado con tests aún pasando. "➖ None needed" si el código ya estaba limpio.

## Reglas de calidad de assertions (MANDATORY)

**Cada assertion debe verificar comportamiento REAL.** Un test que pasa sin ejercitar lógica de producción es PEOR que ningún test — da falsa confianza.

### Banned Assertion Patterns (NUNCA escribir esto)

```
# TRIVIAL — el test no prueba nada
expect(true).toBe(true)              # ❌ Tautología.
expect(false).toBe(false)            # ❌ Tautología.
expect(1).toBe(1)                    # ❌ Tautología — no hay código de producción.
assert True                          # ❌ Siempre pasa.
assert 1 == 1                        # ❌ Siempre pasa.

# EMPTY COLLECTION sin contexto de setup
expect(result).toEqual([])           # ❌ SOLO válido si setteaste condiciones para empty.
expect(result).toHaveLength(0)       # ❌ Igual — ¿por qué está vacío? ¿Corrió código de producción?
assert len(result) == 0              # ❌ Igual — probar que el empty viene de lógica real.

# TYPE-ONLY — prueba existencia, no comportamiento
expect(result).toBeDefined()         # ❌ Solo no sirve — ¿CUÁL es el valor?
expect(result).not.toBeNull()        # ❌ Solo no sirve — asertar el valor real.
expect(typeof result).toBe('object') # ❌ Solo no sirve — ¿qué contiene el object?
assert result is not None            # ❌ Solo — asertar QUÉ es realmente result.

# GHOST LOOP — assertion adentro de un loop que itera 0 veces
const items = screen.queryAllByTestId("item");  // returns []
for (const item of items) {
  expect(item).toHaveTextContent("value");       # ❌ NUNCA EJECUTA — el body es código muerto.
}
# FIX: asertar que la collection es non-empty PRIMERO, o setear data para que SÍ tenga items:
expect(items).toHaveLength(3);                   # ✅ Prueba que items existen.
for (const item of items) { ... }                # ✅ Ahora el loop sí corre.

# CICLO TDD INCOMPLETO — GREEN sin TRIANGULATE
# Si tu GREEN test pasa porque el setup no ejercita el code path,
# NO terminaste. DEBES triangular con un setup que SÍ lo ejercite.
```

### Qué hace una assertion REAL

Cada assertion debe satisfacer TODAS:
1. **Llama código de producción** — el test invoca una función, método o componente de la implementación.
2. **Asserta un output específico** — compara contra un valor concreto derivado del spec.
3. **FALLARÍA si el código de producción estuviera mal** — si cambiás la lógica, ESTE test se rompe.

### Regla de Empty Collection

`expect(result).toEqual([])` o `assert len(result) == 0` SOLO es válido cuando:
1. Setteaste una precondición específica que DEBERÍA producir empty (ej: sin matches).
2. El código de producción realmente corrió y filtró/procesó datos para llegar a empty.
3. Un test compañero con setup distinto produce un resultado NO-EMPTY (triangulación).

Si no podés explicar POR QUÉ el resultado es empty basado en el setup → la assertion es trivial.

### Regla de Smoke Test

Un test que solo renderiza un componente sin asertar ningún output NO es test válido:

```
# ❌ SMOKE TEST SOLO — no prueba nada del comportamiento
render(<MyComponent data={mockData} />);
expect(screen.getByTestId("wrapper")).toBeInTheDocument();  # Solo prueba que renderizó.

# ✅ TEST DE COMPORTAMIENTO — prueba lo que el componente HACE con los datos
render(<MyComponent data={mockData} />);
expect(screen.getByText("Expected Title")).toBeInTheDocument();  # Verifica output de los datos.
expect(screen.getByRole("button")).toHaveTextContent("Submit");  # Verifica contenido real.
```

"Renders sin crash" es smoke test. NO es unit test, NO es integration test, NO cuenta para cobertura TDD. Si necesitás smoke test, debe acompañarse con behavioral assertions reales.

### Higiene de mocks

**Si necesitás más mocks que assertions, estás testeando en el LAYER EQUIVOCADO.**

```
Ratio mocks/assertions:
├── ≤ 3 mocks por test file → ✅ Saludable — test enfocado.
├── 4–6 mocks → ⚠️ Considerar extraer lógica a función pura.
├── 7+ mocks → ❌ STOP — estás testeando en el layer equivocado.
│   ├── Extraer la lógica a FUNCIÓN PURA y testearla sin mocks.
│   ├── O mover el test a integration/E2E donde existen dependencias reales.
│   └── NUNCA escribir 10+ mocks para verificar una transformación de una línea.
```

**Regla Extract-Before-Mock**: si el comportamiento bajo test es transformación, mapping, filtering o lógica condicional (ej: conversión `MUTED → FAIL`), EXTRAÉ a función pura PRIMERO, después testeá la función pura directamente. Sin mocks.

```
# ❌ MAL: 15 mocks para testear conversión de status de una línea
vi.mock("next/navigation", ...);
vi.mock("next/link", ...);
// ... 12 mocks más ...
render(<StatusCell row={mutedRow} />);
expect(screen.getByText("FAIL")).toBeInTheDocument();

# ✅ BIEN: extraer y testear la lógica directamente
// En código de producción:
export function resolveDisplayStatus(status: string, isMuted: boolean): string {
  return status === "MUTED" ? "FAIL" : status;
}

// En el test — CERO mocks:
expect(resolveDisplayStatus("MUTED", true)).toBe("FAIL");
expect(resolveDisplayStatus("PASS", false)).toBe("PASS");
```

### Regla de acoplamiento a detalles de implementación

Los tests deben asertar **comportamiento visible al usuario**, no detalles internos:

```
# ❌ ACOPLADO A IMPLEMENTACIÓN — rompe en cualquier refactor de estilos
expect(element.className).toContain("text-xs");
expect(element.style.color).toBe("red");

# ❌ ACOPLADO A INTERNALS — rompe cuando cambia la implementación
expect(mockService.mock.calls.length).toBe(3);  # ¿Por qué 3? Frágil.
expect(component.state.isLoading).toBe(true);    # Estado interno, no comportamiento.

# ✅ COMPORTAMIENTO — sobrevive refactors, testea lo que ve el usuario
expect(screen.getByText("Error: Payment failed")).toBeInTheDocument();
expect(screen.getByRole("alert")).toHaveTextContent("Risk:");
expect(screen.getByRole("button")).toBeDisabled();
```

**CSS class assertions NUNCA son válidas como test.** Si necesitás verificar estilos:
1. Testeá el outcome SEMÁNTICO (ej: elemento con `role="alert"`, texto visible, botón disabled).
2. O usá visual regression tool / screenshot comparison E2E.
3. NUNCA asertar clases específicas de Tailwind/CSS — son detalles de implementación.

## Reglas finales (Strict TDD)

- NUNCA escribir código de producción antes del test — ESTA es la regla irrompible.
- NUNCA saltar el gate de GREEN execution — DEBES correr tests y confirmar que pasan.
- NUNCA saltar triangulación cuando el spec define múltiples scenarios.
- NUNCA escribir trivial assertions (ver banned patterns arriba) — son PEORES que no tener test.
- SIEMPRE verificar que cada assertion CALL al código de producción y assert un valor ESPECÍFICO.
- SIEMPRE correr Safety Net antes de modificar archivos pre-existentes.
- SIEMPRE reportar la TDD Cycle Evidence table — la fase de review la chequea.
- Si la ejecución del test runner falla por razones de infraestructura (no tests fallando), reportar como "Blocked" y seguir.
- Preferir funciones puras — pero no forzar donde no encaja (ej: componentes React con estado).
- Para refactor, SIEMPRE escribir approval tests antes de tocar el código.
- Correr SOLO el archivo de test relevante durante el ciclo, no la suite completa.
